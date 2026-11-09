"""
CLI commands for model evaluation suites and benchmark scorecards.
"""
import json
from typing import Optional
import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from brahmastra.application.use_cases.evaluation_use_cases import (
    evaluate_model_on_suite,
    export_benchmark_report_as_dict,
    list_benchmark_suites,
)

eval_app = typer.Typer(help="Run reproducible model benchmarks and evaluation scorecards.")
console = Console()
err_console = Console(stderr=True)


@eval_app.command("list")
def list_suites_command():
    """List all available benchmark evaluation suites."""
    suites = list_benchmark_suites()
    table = Table(box=ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Suite ID", style="bold white", width=16)
    table.add_column("Name", style="bold cyan", width=28)
    table.add_column("Tasks", justify="right", width=8)
    table.add_column("Description", style="dim", width=40)

    for s in suites:
        table.add_row(s.suite_id, s.name, str(len(s.tasks)), s.description)

    console.print(table)


@eval_app.command("run")
def run_benchmark_command(
    suite_id: str = typer.Argument("core", help="Benchmark suite identifier."),
    model: str = typer.Option("qwen2.5-coder:latest", "--model", "-m", help="Target model ID to evaluate."),
    provider: str = typer.Option("ollama", "--provider", "-p", help="Provider adapter (e.g., 'ollama', 'openrouter')."),
    org: Optional[str] = typer.Option(None, "--org", help="Target organization for credentials/accounting."),
    json_output: bool = typer.Option(False, "--json", help="Output scorecard as JSON."),
):
    """
    Run evaluation benchmark against target model and produce reproducible scorecard.
    """
    if not json_output:
        console.print(f"[bold cyan]Running benchmark suite '{suite_id}' against model '{model}'...[/bold cyan]")

    try:
        report = evaluate_model_on_suite(
            suite_id=suite_id,
            model_id=model,
            provider_name=provider,
            org_name=org,
        )
    except Exception as e:
        err_console.print(f"[bold red]Evaluation failed:[/bold red] {e}")
        raise typer.Exit(code=1)

    if json_output:
        data = export_benchmark_report_as_dict(report)
        typer.echo(json.dumps(data, indent=2))
        return

    # Task Results Table
    results_table = Table(box=ROUNDED, show_header=True, header_style="bold cyan")
    results_table.add_column("Task ID", style="bold white", width=26)
    results_table.add_column("Status", width=12)
    results_table.add_column("Latency", justify="right", width=14)
    results_table.add_column("Tokens", justify="right", width=12)
    results_table.add_column("Cost (µ$)", justify="right", width=12)

    for r in report.task_results:
        status_badge = "[bold green]PASS[/bold green]" if r.passed else "[bold red]FAIL[/bold red]"
        results_table.add_row(
            r.task_id,
            status_badge,
            f"{r.latency_ms:.1f} ms",
            str(r.prompt_tokens + r.completion_tokens),
            f"{r.cost_micro_usd:,}",
        )

    console.print(results_table)

    # Scorecard Panel
    rate_color = "green" if report.pass_rate >= 80.0 else ("yellow" if report.pass_rate >= 50.0 else "red")
    scorecard_text = (
        f"[bold]Target Model:[/bold] [bold cyan]{report.model_id}[/bold cyan] ({provider})\n"
        f"[bold]Pass Rate:[/bold] [{rate_color}]{report.passed_tasks}/{report.total_tasks} ({report.pass_rate}%)[/{rate_color}]\n"
        f"[bold]Average Latency:[/bold] {report.avg_latency_ms:.1f} ms\n"
        f"[bold]Total Tokens:[/bold] {report.total_tokens:,}\n"
        f"[bold]Total Cost:[/bold] {report.total_cost_micro_usd:,} micro-USD (${report.total_cost_micro_usd / 1_000_000:.6f})"
    )

    console.print(
        Panel(
            scorecard_text,
            title="[bold cyan]Model Evaluation Scorecard[/bold cyan]",
            box=ROUNDED,
            border_style=rate_color,
        )
    )
