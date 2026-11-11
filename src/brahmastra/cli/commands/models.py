"""
CLI commands for Model catalog inspection and discovery.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from brahmastra.application.use_cases.credential_use_cases import (
    list_provider_accounts,
)
from brahmastra.application.use_cases.model_registry_use_cases import (
    sync_models_for_account,
    get_cached_models,
)
from brahmastra.infrastructure.config import get_active_org_name

models_app = typer.Typer(
    name="models",
    help="Discover, sync, and inspect available models across providers.",
    no_args_is_help=True,
)

console = Console()


@models_app.command("list")
def models_list(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Filter by specific provider account"),
    org: Optional[str] = typer.Option(None, "--org", help="Filter by organization (defaults to active org)"),
    sync: bool = typer.Option(False, "--sync", "-s", help="Force refresh model catalog from remote provider"),
):
    """
    List available models from assigned provider accounts (cached by default).
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

        # Check if cached models exist and sync is not requested
        cached_models = get_cached_models(org_name=target_org, account_name=account)
        if cached_models and not sync:
            models_to_display = cached_models
            source_label = "[dim](Cached in SQLite)[/dim]"
        else:
            # Sync fresh from provider accounts
            console.print("[dim]Fetching live model catalog from providers...[/dim]")
            models_to_display = []
            for acc in accounts:
                try:
                    models = sync_models_for_account(acc.name)
                    models_to_display.extend(models)
                except Exception as p_err:
                    console.print(f"[yellow]Warning: Could not sync models for account '{acc.name}': {p_err}[/yellow]")
            source_label = "[dim](Synchronized from live providers)[/dim]"

        if not models_to_display:
            console.print("[yellow]No models available. Run 'brahmastra models sync' when providers are reachable.[/yellow]")
            return

        table = Table(title=f"Available Models {source_label}", show_lines=True)
        table.add_column("Model ID", style="bold cyan", no_wrap=True)
        table.add_column("Provider", style="bold", no_wrap=True)
        table.add_column("Context Window", justify="right")
        table.add_column("Capabilities", style="green")
        table.add_column("Location", justify="center")

        for m in models_to_display:
            caps = ", ".join([c.value for c in m.capabilities])
            loc = "[bold green]Local[/bold green]" if m.is_local else "[dim]Cloud[/dim]"
            table.add_row(
                m.id,
                m.provider,
                f"{m.context_window:,} tokens",
                caps,
                loc,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(models_to_display)} model(s) available.[/dim]\n")

    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@models_app.command("sync")
def models_sync(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account name to sync (default: all)"),
    org: Optional[str] = typer.Option(None, "--org", help="Filter by organization"),
):
    """
    Synchronize model catalogs from providers into SQLite registry.
    """
    target_org = org or get_active_org_name()
    try:
        accounts = list_provider_accounts(org_name=target_org)
        if account:
            accounts = [a for a in accounts if a.name == account]

        total_synced = 0
        for acc in accounts:
            try:
                models = sync_models_for_account(acc.name)
                console.print(f"[bold green]✓ Synced {len(models)} models for '{acc.name}'[/bold green]")
                total_synced += len(models)
            except Exception as exc:
                console.print(f"[bold red]✗ Failed to sync '{acc.name}':[/bold red] {exc}")

        console.print(f"\n[bold]Catalog sync complete. {total_synced} models cached in SQLite.[/bold]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
