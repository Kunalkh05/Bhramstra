"""
CLI commands for Provider and ProviderAccount management.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from brahmastra.domain.credentials.models import ProviderAccountCreate
from brahmastra.application.use_cases.credential_use_cases import (
    register_provider_account,
    list_provider_accounts,
    list_credentials,
)
from brahmastra.infrastructure.config import get_active_org_name
from brahmastra.infrastructure.providers.factory import get_provider_adapter
from brahmastra.infrastructure.vault.factory import get_vault

provider_app = typer.Typer(
    name="provider",
    help="Manage AI providers and provider accounts.",
    no_args_is_help=True,
)

console = Console()


@provider_app.command("add")
def provider_add(
    provider_type: str = typer.Argument(..., help="Provider type (e.g. 'openrouter', 'ollama')"),
    account_name: str = typer.Argument(..., help="Unique account identifier (e.g. 'openrouter-prod')"),
    endpoint: Optional[str] = typer.Option(None, "--endpoint", "-e", help="Custom base API endpoint URL"),
    desc: Optional[str] = typer.Option(None, "--desc", "-d", help="Account description"),
    assign_org: Optional[str] = typer.Option(None, "--assign-org", help="Assign directly to organization (defaults to active org)"),
):
    """
    Register a new provider account and assign it to an organization.
    """
    target_org = assign_org or get_active_org_name()
    try:
        req = ProviderAccountCreate(
            name=account_name,
            provider_type=provider_type,
            endpoint=endpoint,
            description=desc,
        )
        account = register_provider_account(req, assign_to_org_name=target_org)
        console.print(f"[bold green]✓ Registered provider account '{account.name}' ({account.provider_type})[/bold green]")
        if account.assigned_org_names:
            console.print(f"[dim]Assigned to organization: {', '.join(account.assigned_org_names)}[/dim]")
        else:
            console.print("[yellow]Warning: Account is not assigned to any organization yet.[/yellow]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@provider_app.command("list")
def provider_list(
    org: Optional[str] = typer.Option(None, "--org", help="Filter accounts assigned to this organization (default: all)"),
):
    """
    List registered provider accounts and organization assignments.
    """
    try:
        accounts = list_provider_accounts(org_name=org)
        if not accounts:
            console.print("[yellow]No provider accounts found.[/yellow]")
            console.print("Run [bold cyan]brahmastra provider add <provider> <account_name>[/bold cyan] to register one.")
            return

        table = Table(title="Provider Accounts", show_lines=True)
        table.add_column("Account Name", style="bold cyan")
        table.add_column("Provider", style="bold")
        table.add_column("Endpoint", style="dim")
        table.add_column("Assigned Organizations", style="green")
        table.add_column("Description", style="dim")

        for acc in accounts:
            orgs_str = ", ".join(acc.assigned_org_names) if acc.assigned_org_names else "[red]Unassigned[/red]"
            table.add_row(
                acc.name,
                acc.provider_type,
                acc.endpoint or "Default",
                orgs_str,
                acc.description or "—",
            )

        console.print(table)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@provider_app.command("test")
def provider_test(
    account_name: str = typer.Argument(..., help="Name of provider account to verify"),
):
    """
    Verify configuration, credentials, and live endpoint connectivity for a provider account.
    """
    try:
        accounts = list_provider_accounts()
        acc = next((a for a in accounts if a.name == account_name), None)
        if not acc:
            console.print(f"[bold red]Error:[/bold red] Provider account '{account_name}' not found.")
            raise typer.Exit(code=1)

        creds = list_credentials(account_name=account_name)
        active_creds = [c for c in creds if c.status.value == "ACTIVE"]

        console.print(f"\n[bold cyan]Diagnostic Check for Account '{account_name}'[/bold cyan] ({acc.provider_type})")
        console.print(f"Endpoint: {acc.endpoint or 'Default'}")
        console.print(f"Credentials registered: {len(creds)} ({len(active_creds)} active)\n")

        secret = None
        if active_creds:
            vault = get_vault()
            # Extract secret for primary active key
            first_cred = active_creds[0]
            service_name = f"brahmastra:{acc.provider_type}"
            account_slot = f"{acc.name}:{first_cred.label}"
            secret = vault.get_secret(service_name, account_slot)

        # Execute live adapter health check
        adapter = get_provider_adapter(acc.provider_type, endpoint=acc.endpoint)
        health = adapter.health_check(secret=secret)

        health_color = "green" if health.status == "HEALTHY" else "red"
        console.print(f"Status:  [{health_color}]{health.status}[/{health_color}]")
        if health.latency_ms is not None:
            console.print(f"Latency: [bold]{health.latency_ms} ms[/bold]")
        if health.details:
            console.print(f"Details: [dim]{health.details}[/dim]\n")

    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
