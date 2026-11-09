"""
CLI commands for Model catalog inspection and discovery.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from brahmastra.application.use_cases.credential_use_cases import (
    list_provider_accounts,
    list_credentials,
)
from brahmastra.infrastructure.config import get_active_org_name
from brahmastra.infrastructure.providers.factory import get_provider_adapter
from brahmastra.infrastructure.vault.factory import get_vault
from brahmastra.domain.providers.exceptions import ProviderError

models_app = typer.Typer(
    name="models",
    help="Discover and inspect available models across providers.",
    no_args_is_help=True,
)

console = Console()


@models_app.command("list")
def models_list(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Filter by specific provider account"),
    org: Optional[str] = typer.Option(None, "--org", help="Filter by organization (defaults to active org)"),
):
    """
    List available models from assigned provider accounts.
    """
    target_org = org or get_active_org_name()
    try:
        accounts = list_provider_accounts(org_name=target_org)
        if account:
            accounts = [a for a in accounts if a.name == account]

        if not accounts:
            console.print("[yellow]No provider accounts found matching criteria.[/yellow]")
            console.print("Run [bold cyan]brahmastra provider list[/bold cyan] to inspect registered accounts.")
            return

        table = Table(title="Available Models", show_lines=True)
        table.add_column("Model ID", style="bold cyan", no_wrap=True)
        table.add_column("Account", style="dim", no_wrap=True)
        table.add_column("Provider", style="bold", no_wrap=True)
        table.add_column("Context Window", justify="right")
        table.add_column("Capabilities", style="green")
        table.add_column("Location", justify="center")

        vault = get_vault()
        total_models = 0

        for acc in accounts:
            creds = list_credentials(account_name=acc.name)
            active_creds = [c for c in creds if c.status.value == "ACTIVE"]

            secret = None
            if active_creds:
                c = active_creds[0]
                service_name = f"brahmastra:{acc.provider_type}"
                account_slot = f"{acc.name}:{c.label}"
                secret = vault.get_secret(service_name, account_slot)

            try:
                adapter = get_provider_adapter(acc.provider_type, endpoint=acc.endpoint)
                models = adapter.list_models(secret=secret)
                for m in models:
                    caps = ", ".join([c.value for c in m.capabilities])
                    loc = "[bold green]Local[/bold green]" if m.is_local else "[dim]Cloud[/dim]"
                    table.add_row(
                        m.id,
                        acc.name,
                        acc.provider_type,
                        f"{m.context_window:,} tokens",
                        caps,
                        loc,
                    )
                    total_models += 1
            except ProviderError as p_err:
                console.print(f"[yellow]Warning: Could not fetch models from account '{acc.name}': {p_err.message}[/yellow]")

        if total_models > 0:
            console.print(table)
            console.print(f"\n[dim]Total: {total_models} models available across {len(accounts)} account(s).[/dim]\n")
        else:
            console.print("[yellow]No models could be retrieved. Ensure providers are reachable and credentials are valid.[/yellow]")

    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
