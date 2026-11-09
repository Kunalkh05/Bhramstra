"""
CLI commands for Explainable Routing simulation and direct task execution.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from brahmastra.domain.routing.models import (
    RoutingConstraints,
    RoutingPreference,
)
from brahmastra.domain.providers.models import (
    GenerationRequest,
    ChatMessage,
    ModelCapability,
)
from brahmastra.application.use_cases.routing_use_cases import (
    resolve_route,
    execute_routed_request,
)
from brahmastra.infrastructure.config import get_active_org_name

console = Console()


def route_command(
    task: str = typer.Argument(..., help="Prompt or task to route"),
    org: Optional[str] = typer.Option(None, "--org", help="Target organization (defaults to active org)"),
    local_only: bool = typer.Option(False, "--local-only", "-l", help="Enforce local execution only (zero network)"),
    vision: bool = typer.Option(False, "--vision", help="Require vision/multimodal capabilities"),
    min_context: int = typer.Option(0, "--min-context", help="Minimum required context window in tokens"),
    cloud_first: bool = typer.Option(False, "--cloud-first", help="Prefer cloud models over local"),
    explain: bool = typer.Option(True, "--explain/--no-explain", help="Display full candidate evaluation matrix"),
):
    """
    Simulate and explain model routing resolution for a task without executing it.
    """

    target_org = org or get_active_org_name()
    if not target_org:
        console.print("[bold red]Error:[/bold red] No active organization set. Run 'brahmastra org switch <name>'.")
        raise typer.Exit(code=1)

    req_caps = []
    if vision:
        req_caps.append(ModelCapability.VISION)

    constraints = RoutingConstraints(
        require_local=local_only,
        require_capabilities=req_caps,
        min_context_window=min_context,
    )
    pref = RoutingPreference.CLOUD_FIRST if cloud_first else RoutingPreference.LOCAL_FIRST

    decision = resolve_route(target_org, constraints, pref)

    console.print(f"\n[bold cyan]BRAHMASTRA Routing Decision[/bold cyan] (Org: [bold green]{target_org}[/bold green])\n")
    if decision.selected_model_id:
        console.print(Panel(
            f"[bold green]Selected Model:[/bold green] {decision.selected_model_id}\n"
            f"[bold cyan]Provider Account:[/bold cyan] {decision.selected_account_name} ({decision.selected_provider})\n\n"
            f"[dim]{decision.explanation}[/dim]",
            title="Optimal Route",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]No Eligible Route Found[/bold red]\n\n"
            f"[yellow]{decision.explanation}[/yellow]",
            title="Routing Failure",
            border_style="red",
        ))

    if explain and decision.candidates_evaluated:
        console.print()
        table = Table(title="Candidate Evaluation Matrix", show_lines=True)
        table.add_column("Candidate Model", style="bold cyan")
        table.add_column("Provider", style="dim")
        table.add_column("Account", style="dim")
        table.add_column("Eligible", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Evaluation Notes", style="dim")

        for c in decision.candidates_evaluated:
            elig_mark = "[green]YES[/green]" if c.is_eligible else "[red]NO[/red]"
            table.add_row(
                c.model_id,
                c.provider,
                c.account_name,
                elig_mark,
                f"{c.score:.1f}",
                c.disqualification_reason or "[green]Met all constraints[/green]",
            )
        console.print(table)

    if decision.fallback_chain:
        console.print(f"\n[dim]Fallback Chain: {' -> '.join(decision.fallback_chain)}[/dim]\n")


def run_command_handler(
    task: str = typer.Argument(..., help="Prompt or task to execute"),
    org: Optional[str] = typer.Option(None, "--org", help="Target organization (defaults to active org)"),
    local_only: bool = typer.Option(False, "--local-only", "-l", help="Enforce local execution only"),
):
    """
    Execute a prompt using explainable routing and stream/display the result.
    """
    target_org = org or get_active_org_name()
    if not target_org:
        console.print("[bold red]Error:[/bold red] No active organization set. Run 'brahmastra org switch <name>'.")
        raise typer.Exit(code=1)

    constraints = RoutingConstraints(require_local=local_only)
    req = GenerationRequest(
        model="",  # Filled dynamically by router
        messages=[ChatMessage(role="user", content=task)],
    )

    console.print(f"[dim]Routing and executing task under organization '{target_org}'...[/dim]")
    try:
        response, decision = execute_routed_request(target_org, req, constraints)
        console.print(f"\n[bold green]Model:[/bold green] {decision.selected_model_id} via {decision.selected_account_name}\n")
        console.print(Panel(response.content, title="Model Output", border_style="cyan"))
        console.print(f"\n[dim]Tokens: {response.usage.total_tokens} ({response.usage.prompt_tokens} in, {response.usage.completion_tokens} out)[/dim]\n")
    except Exception as exc:
        console.print(f"[bold red]Execution Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
