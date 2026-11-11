"""
CLI commands for tracking and inspecting AI token usage and costs.
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from brahmastra.application.use_cases.usage_use_cases import (
    get_usage_summary,
    list_usage_records,
)
from brahmastra.infrastructure.config import get_active_org_name

usage_app = typer.Typer(
    name="usage",
    help="Inspect AI token usage, request latency, and financial costs.",
    no_args_is_help=False,
)

console = Console()


@usage_app.callback(invoke_without_command=True)
def usage_main(
    ctx: typer.Context,
    org: Optional[str] = typer.Option(None, "--org", help="Filter by organization (defaults to active org)"),
    details: bool = typer.Option(False, "--details", "-d", help="Show recent request log entries"),
):
    """
    Display usage overview, token accounting, and cost summary.
    """
    if ctx.invoked_subcommand is not None:
        return

    target_org = org or get_active_org_name()
    try:
        summary = get_usage_summary(org_name=target_org)
        console.print("\n[bold cyan]BRAHMASTRA Usage Report[/bold cyan]")
        if target_org:
            console.print(f"Organization: [bold green]{target_org}[/bold green]\n")
        else:
            console.print("[dim]Scope: All Organizations[/dim]\n")

        if summary.total_requests == 0:
            console.print("[yellow]No usage recorded yet for this organization.[/yellow]")
            console.print("[dim]Token usage will be recorded automatically when generating requests.[/dim]\n")
            return

        # Summary Metrics Table
        metrics_table = Table(title="Aggregate Metrics", show_header=False)
        metrics_table.add_column("Metric", style="bold cyan")
        metrics_table.add_column("Value")

        metrics_table.add_row("Total Requests", f"{summary.total_requests:,}")
        metrics_table.add_row("Prompt Tokens", f"{summary.total_prompt_tokens:,}")
        metrics_table.add_row("Completion Tokens", f"{summary.total_completion_tokens:,}")
        metrics_table.add_row("Total Tokens", f"[bold green]{summary.total_tokens:,}[/bold green]")
        metrics_table.add_row("Tracked Cost (USD)", f"${summary.total_cost_usd:.6f}")

        console.print(metrics_table)

        # Model Breakdown
        if summary.models:
            console.print()
            model_table = Table(title="Usage by Model", show_lines=True)
            model_table.add_column("Model ID", style="bold cyan")
            model_table.add_column("Requests", justify="right")
            model_table.add_column("Prompt Tokens", justify="right")
            model_table.add_column("Completion Tokens", justify="right")
            model_table.add_column("Total Tokens", justify="right", style="green")
            model_table.add_column("Cost (USD)", justify="right")

            for m in summary.models:
                model_table.add_row(
                    m.model_id,
                    f"{m.requests:,}",
                    f"{m.prompt_tokens:,}",
                    f"{m.completion_tokens:,}",
                    f"{m.total_tokens:,}",
                    f"${m.cost_usd:.6f}",
                )
            console.print(model_table)

        # Detailed Log
        if details:
            records = list_usage_records(org_name=target_org, limit=20)
            if records:
                console.print()
                detail_table = Table(title="Recent Requests (Last 20)", show_lines=True)
                detail_table.add_column("Timestamp", style="dim")
                detail_table.add_column("Account", style="bold")
                detail_table.add_column("Model", style="bold cyan")
                detail_table.add_column("Tokens", justify="right")
                detail_table.add_column("Latency", justify="right")
                detail_table.add_column("Cost", justify="right")

                for r in records:
                    lat_str = f"{r.latency_ms:.1f} ms" if r.latency_ms is not None else "—"
                    detail_table.add_row(
                        r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        r.account_name,
                        r.model_id,
                        f"{r.total_tokens:,}",
                        lat_str,
                        f"${r.cost_usd:.6f}",
                    )
                console.print(detail_table)

        console.print("\n[dim]* Note: Local models (Ollama) and unbilled requests have $0.00 cost. Unknown provider rates are not fabricated.[/dim]\n")

    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
