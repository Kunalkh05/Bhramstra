"""
CLI commands for secure Credential lifecycle management (COM).
"""

from typing import Optional
import sys
import typer
from rich.console import Console
from rich.table import Table

from brahmastra.domain.credentials.models import CredentialCreate
from brahmastra.application.use_cases.credential_use_cases import (
    add_credential,
    list_credentials,
    verify_credential,
    rotate_credential,
    revoke_credential,
    remove_credential,
)
from brahmastra.infrastructure.config import get_active_org_name

key_app = typer.Typer(
    name="key",
    help="Secure multi-provider, multi-account credential management (COM).",
    no_args_is_help=True,
)

console = Console()


@key_app.command("add")
def key_add(
    account_name: str = typer.Argument(..., help="Target provider account name"),
    label: str = typer.Argument(..., help="Unique label for this credential (e.g. 'primary', 'backup')"),
    secret: Optional[str] = typer.Option(None, "--secret-stdin", help="Read secret from standard input (non-interactive)"),
):
    """
    Securely store a credential in the OS Vault.
    Never exposes secrets in command arguments.
    """
    if secret:
        raw_secret = secret.strip()
    elif not sys.stdin.isatty():
        raw_secret = sys.stdin.read().strip()
    else:
        raw_secret = typer.prompt("Enter API Key / Token (hidden)", hide_input=True)

    if not raw_secret:
        console.print("[bold red]Error:[/bold red] Secret cannot be empty.")
        raise typer.Exit(code=1)

    try:
        req = CredentialCreate(
            account_name=account_name,
            label=label,
            secret=raw_secret,
        )
        cred = add_credential(req)
        console.print(f"[bold green]✓ Credential '{cred.label}' saved securely in OS Vault[/bold green]")
        console.print(f"[dim]Vault Reference: {cred.vault_ref}[/dim]")
        console.print(f"[dim]Masked Preview:  {cred.masked_preview}[/dim]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@key_app.command("list")
def key_list(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Filter by provider account"),
    org: Optional[str] = typer.Option(None, "--org", help="Filter by assigned organization (defaults to active org)"),
):
    """
    List credentials with masked previews, vault references, and health states.
    """
    target_org = org or get_active_org_name()
    try:
        creds = list_credentials(account_name=account, org_name=target_org)
        if not creds:
            console.print("[yellow]No credentials found.[/yellow]")
            console.print("Run [bold cyan]brahmastra key add <account> <label>[/bold cyan] to register a credential.")
            return

        table = Table(title="Credentials (COM Vault)", show_lines=True)
        table.add_column("Account", style="bold cyan", no_wrap=True)
        table.add_column("Label", style="bold", no_wrap=True)
        table.add_column("Masked Preview", style="dim", no_wrap=True)
        table.add_column("Vault Reference", style="dim")
        table.add_column("Status", justify="center")
        table.add_column("Health", justify="center")
        table.add_column("Last Validated", style="dim")

        for c in creds:
            status_style = "green" if c.status.value == "ACTIVE" else "red"
            health_style = "green" if c.health_status.value == "HEALTHY" else "yellow"

            table.add_row(
                c.account_name,
                c.label,
                c.masked_preview,
                c.vault_ref,
                f"[{status_style}]{c.status.value}[/{status_style}]",
                f"[{health_style}]{c.health_status.value}[/{health_style}]",
                c.last_validated_at.strftime("%Y-%m-%d %H:%M") if c.last_validated_at else "Never",
            )

        console.print(table)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@key_app.command("test")
def key_test(
    label: str = typer.Argument(..., help="Credential label to test"),
    account: str = typer.Option(..., "--account", "-a", help="Provider account name"),
):
    """
    Verify that a credential exists and is accessible in the OS Vault.
    """
    try:
        valid = verify_credential(label=label, account_name=account)
        if valid:
            console.print(f"[bold green]✓ Credential '{label}' on account '{account}' is accessible in OS Vault.[/bold green]")
        else:
            console.print(f"[bold red]✗ Credential '{label}' on account '{account}' not found in OS Vault.[/bold red]")
            raise typer.Exit(code=1)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@key_app.command("rotate")
def key_rotate(
    label: str = typer.Argument(..., help="Credential label to rotate"),
    account: str = typer.Option(..., "--account", "-a", help="Provider account name"),
    secret: Optional[str] = typer.Option(None, "--secret-stdin", help="Read new secret from stdin"),
):
    """
    Rotate a credential with a new secret value in the OS Vault.
    """
    if secret:
        new_secret = secret.strip()
    elif not sys.stdin.isatty():
        new_secret = sys.stdin.read().strip()
    else:
        new_secret = typer.prompt("Enter NEW API Key / Token (hidden)", hide_input=True)

    if not new_secret:
        console.print("[bold red]Error:[/bold red] Secret cannot be empty.")
        raise typer.Exit(code=1)

    try:
        cred = rotate_credential(label=label, account_name=account, new_secret=new_secret)
        console.print(f"[bold green]✓ Credential '{cred.label}' rotated successfully in OS Vault.[/bold green]")
        console.print(f"[dim]New Preview: {cred.masked_preview}[/dim]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@key_app.command("revoke")
def key_revoke(
    label: str = typer.Argument(..., help="Credential label to revoke"),
    account: str = typer.Option(..., "--account", "-a", help="Provider account name"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
):
    """
    Revoke a credential. Revoked credentials cannot be used for inference.
    """
    if not force:
        confirm = typer.confirm(f"Revoke credential '{label}' on account '{account}'?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return

    try:
        cred = revoke_credential(label=label, account_name=account)
        console.print(f"[bold yellow]✓ Credential '{cred.label}' on account '{account}' marked as REVOKED.[/bold yellow]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@key_app.command("remove")
def key_remove(
    label: str = typer.Argument(..., help="Credential label to permanently delete"),
    account: str = typer.Option(..., "--account", "-a", help="Provider account name"),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
):
    """
    Permanently delete a credential from both the OS Vault and database metadata.
    """
    if not force:
        confirm = typer.confirm(f"Permanently DELETE credential '{label}' on account '{account}' from OS Vault?")
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            return

    try:
        remove_credential(label=label, account_name=account)
        console.print(f"[bold green]✓ Credential '{label}' permanently removed from OS Vault and database.[/bold green]")
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
