"""
CLI command group for diff review, patch approval, and command execution gating.
"""
from pathlib import Path
from typing import Optional
import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from brahmastra.application.use_cases.patch_use_cases import (
    apply_approved_patch,
    evaluate_command_for_approval,
    propose_patch,
    rollback_patch_safely,
)
from brahmastra.domain.patch.models import CommandRiskLevel, PatchStatus

patch_app = typer.Typer(help="Review unified diffs, approve patches, and inspect command execution.")
console = Console()
err_console = Console(stderr=True)


def render_unified_diff(diff_text: str, filename: str = "") -> None:
    """Renders syntax-highlighted unified diff."""
    if not diff_text.strip():
        console.print("[dim]No changes detected (diff is empty).[/dim]")
        return
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
    header = f"Proposed Diff: [bold cyan]{filename}[/bold cyan]" if filename else "Proposed Diff"
    console.print(Panel(syntax, title=header, box=ROUNDED, border_style="cyan"))


def prompt_patch_approval(
    diff_text: str,
    target_path: Path,
    auto_approve: bool = False,
) -> bool:
    """
    Renders diff and prompts the user for explicit approval.
    """
    render_unified_diff(diff_text, str(target_path))
    if auto_approve:
        console.print("[bold yellow]Auto-approving patch due to --yes flag.[/bold yellow]")
        return True
    return Confirm.ask(f"Apply this patch to [bold cyan]{target_path}[/bold cyan]?", default=False)


def prompt_command_approval(
    command: str,
    explanation: str = "",
    auto_approve: bool = False,
) -> bool:
    """
    Evaluates shell command risk and prompts user for explicit approval.
    """
    action = evaluate_command_for_approval(command, explanation=explanation)
    risk_color = "green" if action.risk_level == CommandRiskLevel.SAFE_READ else ("yellow" if action.risk_level == CommandRiskLevel.MODERATE else "red")

    panel_content = (
        f"[bold]Command:[/bold] [bold white]{action.command}[/bold white]\n"
        f"[bold]Risk Level:[/bold] [{risk_color}]{action.risk_level.value}[/{risk_color}]\n"
        f"[bold]Explanation:[/bold] {action.explanation}"
    )
    console.print(
        Panel(
            panel_content,
            title="[bold yellow]Command Execution Approval Gate[/bold yellow]",
            box=ROUNDED,
            border_style=risk_color,
        )
    )

    if action.requires_explicit_override and auto_approve:
        console.print("[bold red]DENIED:[/bold red] Highly dangerous command cannot be auto-approved.")
        return False

    if auto_approve and action.risk_level != CommandRiskLevel.DANGEROUS:
        console.print("[bold yellow]Auto-approving command execution due to --yes flag.[/bold yellow]")
        return True

    return Confirm.ask(f"Execute this shell command?", default=False)


@patch_app.command("preview")
def preview_patch(
    target: str = typer.Argument(..., help="Target file path to modify."),
    replacement_file: str = typer.Argument(..., help="File containing new replacement content."),
    root: Optional[str] = typer.Option(None, "--root", "-r", help="Project root boundary directory."),
):
    """
    Preview unified diff between target file and replacement content without applying.
    """
    target_p = Path(target)
    repl_p = Path(replacement_file)

    if not repl_p.exists():
        err_console.print(f"[bold red]Error:[/bold red] Replacement file not found: {repl_p}")
        raise typer.Exit(code=1)

    with open(repl_p, "r", encoding="utf-8") as f:
        new_content = f.read()

    try:
        root_dir = Path(root).resolve() if root else None
        patch = propose_patch(target_path=target_p, new_content=new_content, root_dir=root_dir)
    except PermissionError as pe:
        err_console.print(f"[bold red]Security Violation:[/bold red] {pe}")
        raise typer.Exit(code=1)

    console.print(
        f"[bold cyan]File:[/bold cyan] {patch.target_path} | "
        f"[bold green]+{patch.lines_added}[/bold green] / "
        f"[bold red]-{patch.lines_removed}[/bold red] lines"
    )
    render_unified_diff(patch.unified_diff, str(patch.target_path))


@patch_app.command("apply")
def apply_patch_command(
    target: str = typer.Argument(..., help="Target file path to modify."),
    replacement_file: str = typer.Argument(..., help="File containing new replacement content."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Automatically approve without interactive prompt."),
    root: Optional[str] = typer.Option(None, "--root", "-r", help="Project root boundary directory."),
):
    """
    Generate unified diff, prompt for explicit human approval, and apply atomically.
    """
    target_p = Path(target)
    repl_p = Path(replacement_file)

    if not repl_p.exists():
        err_console.print(f"[bold red]Error:[/bold red] Replacement file not found: {repl_p}")
        raise typer.Exit(code=1)

    with open(repl_p, "r", encoding="utf-8") as f:
        new_content = f.read()

    try:
        root_dir = Path(root).resolve() if root else None
        patch = propose_patch(target_path=target_p, new_content=new_content, root_dir=root_dir)
    except PermissionError as pe:
        err_console.print(f"[bold red]Security Violation:[/bold red] {pe}")
        raise typer.Exit(code=1)

    approved = prompt_patch_approval(patch.unified_diff, patch.target_path, auto_approve=yes)
    if not approved:
        console.print("[yellow]Patch rejected by user. No files were modified.[/yellow]")
        raise typer.Exit(code=0)

    try:
        applied_path = apply_approved_patch(patch)
        console.print(f"[bold green]✓[/bold green] Patch successfully applied to [dim]{applied_path}[/dim]")
    except Exception as e:
        err_console.print(f"[bold red]Failed to apply patch:[/bold red] {e}")
        rollback_patch_safely(patch)
        raise typer.Exit(code=1)


@patch_app.command("eval-cmd")
def eval_cmd_command(
    command: str = typer.Argument(..., help="Shell command string to evaluate."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve non-dangerous commands."),
):
    """
    Evaluate command risk level and execute the approval confirmation gate.
    """
    approved = prompt_command_approval(command, auto_approve=yes)
    if approved:
        console.print("[bold green]✓ Command approved for execution.[/bold green]")
    else:
        console.print("[bold red]✗ Command execution was declined.[/bold red]")
