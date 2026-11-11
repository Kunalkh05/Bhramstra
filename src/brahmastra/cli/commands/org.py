"""
CLI commands for Organization management.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from brahmastra.domain.organizations.models import OrganizationCreate
from brahmastra.application.use_cases.org_use_cases import (
    create_organization,
    list_organizations,
    get_organization,
    get_active_organization,
    switch_active_organization,
)

org_app = typer.Typer(
    name="org",
    help="Manage organization profiles and workspace isolation.",
    no_args_is_help=True,
)

console = Console()


@org_app.command("add")
def org_add(
    name: str = typer.Argument(..., help="Unique organization identifier (e.g. 'personal', 'company')"),
    desc: Optional[str] = typer.Option(None, "--desc", "-d", help="Optional description of the organization"),
):
    """
    Create a new organization workspace.
    """
    try:
        req = OrganizationCreate(name=name, description=desc)
        org = create_organization(req)
        console.print(f"[bold green]✓ Created organization '{org.name}'[/bold green]")
        if org.is_active:
            console.print("[dim]Set as current active organization.[/dim]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@org_app.command("list")
def org_list():
    """
    List all organizations and show the currently active profile.
    """
    orgs = list_organizations()
    if not orgs:
        console.print("[yellow]No organizations found.[/yellow]")
        console.print("Run [bold cyan]brahmastra org add <name>[/bold cyan] to create your first workspace profile.")
        return

    table = Table(title="Organizations", show_lines=True)
    table.add_column("Active", justify="center", style="bold green", width=8)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description", style="dim")
    table.add_column("Created At", style="dim")

    for org in orgs:
        active_mark = "✓ *" if org.is_active else ""
        table.add_row(
            active_mark,
            org.name,
            org.description or "—",
            org.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@org_app.command("current")
def org_current():
    """
    Display the currently active organization.
    """
    active = get_active_organization()
    if not active:
        console.print("[yellow]No active organization currently set.[/yellow]")
        console.print("Run [bold cyan]brahmastra org list[/bold cyan] or [bold cyan]brahmastra org switch <name>[/bold cyan].")
        return

    console.print(f"Active Organization: [bold green]{active.name}[/bold green]")
    if active.description:
        console.print(f"[dim]{active.description}[/dim]")


@org_app.command("switch")
def org_switch(
    name: str = typer.Argument(..., help="Name of the organization to activate"),
):
    """
    Switch active organization context.
    """
    try:
        org = switch_active_organization(name)
        console.print(f"[bold green]✓ Switched active profile to organization '{org.name}'[/bold green]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@org_app.command("show")
def org_show(
    name: str = typer.Argument(..., help="Name of the organization to inspect"),
):
    """
    Show details for a specific organization.
    """
    try:
        org = get_organization(name)
        table = Table(title=f"Organization: {org.name}", show_header=False)
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")

        table.add_row("ID", str(org.id))
        table.add_row("Name", org.name)
        table.add_row("Description", org.description or "—")
        table.add_row("Is Active", "[green]Yes[/green]" if org.is_active else "No")
        table.add_row("Created At", org.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Updated At", org.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC"))

        console.print(table)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
