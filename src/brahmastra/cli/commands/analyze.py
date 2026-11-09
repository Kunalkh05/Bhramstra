"""
CLI command for read-only repository inspection and codebase analysis.
"""
import json
from pathlib import Path
from typing import Optional
import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from brahmastra.application.use_cases.analysis_use_cases import (
    analyze_repository,
    export_report_as_dict,
)

app = typer.Typer(help="Read-only repository inspection and codebase analysis.")
console = Console()
err_console = Console(stderr=True)


def analyze_command(
    path: Optional[str] = typer.Argument(
        ".", help="Target repository directory or file path."
    ),
    depth: int = typer.Option(
        5, "--depth", "-d", help="Maximum directory traversal depth."
    ),
    security: bool = typer.Option(
        True, "--security/--no-security", help="Scan for credential and secret leaks."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output analysis report as JSON."
    ),
    export: Optional[str] = typer.Option(
        None, "--export", "-e", help="Optional path to save JSON analysis report."
    ),
) -> None:
    """
    Perform static analysis, architectural mapping, AST inspection,
    and credential leak detection. Strictly read-only.
    """
    target = Path(path or ".").resolve()
    if not target.exists():
        err_console.print(f"[bold red]Error:[/bold red] Target path does not exist: {target}")
        raise typer.Exit(code=1)

    try:
        report = analyze_repository(
            target_path=target,
            max_depth=depth,
            scan_secrets=security,
        )
    except Exception as e:
        err_console.print(f"[bold red]Analysis failed:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Handle JSON export or stdout
    if json_output:
        report_data = export_report_as_dict(report)
        typer.echo(json.dumps(report_data, indent=2))
        return

    if export:
        export_path = Path(export).resolve()
        report_data = export_report_as_dict(report)
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
            console.print(f"[bold green]✓[/bold green] Analysis report exported to [dim]{export_path}[/dim]")
        except Exception as ex:
            err_console.print(f"[bold red]Failed to export report:[/bold red] {ex}")

    # Determine primary language
    primary_lang = "None"
    primary_pct = 0.0
    if report.languages:
        primary_lang = report.languages[0].language
        primary_pct = report.languages[0].percentage

    # Render summary header
    console.print(f"[bold cyan]Codebase Analysis:[/bold cyan] [dim]{target}[/dim]")
    console.print(
        f"Total Files: [bold]{report.total_files}[/bold] | "
        f"Lines of Code: [bold]{report.total_lines:,}[/bold] | "
        f"Primary Language: [bold cyan]{primary_lang}[/bold cyan] ({primary_pct}%)"
    )
    console.print()

    # Metric Table
    metric_table = Table(box=ROUNDED, show_header=True, header_style="bold cyan")
    metric_table.add_column("Metric", style="bold", width=22)
    metric_table.add_column("Value", style="magenta", width=16)
    metric_table.add_column("Assessment", style="dim", width=42)

    # 1. Architecture Style
    metric_table.add_row("Architecture Style", "Modular", report.architecture_assessment)

    # 2. Token Footprint
    token_k = f"{report.estimated_tokens / 1000:.1f}k"
    if report.estimated_tokens > 200_000:
        token_assessment = "Exceeds 200k context; requires slicing"
    elif report.estimated_tokens > 64_000:
        token_assessment = "Fits within 128k context window"
    else:
        token_assessment = "Readily ingestible into standard context"
    metric_table.add_row("Token Footprint", token_k, token_assessment)

    # 3. Secret Scan
    if report.security_findings:
        secret_val = f"[bold red]{len(report.security_findings)} leaks[/bold red]"
        secret_assessment = "[bold red]ACTION REQUIRED: Review detected keys[/bold red]"
    else:
        secret_val = "[bold green]Clean[/bold green]"
        secret_assessment = "0 hardcoded keys detected"
    metric_table.add_row("Secret Scan", secret_val, secret_assessment)

    # 4. AST Symbols
    symbol_count = len(report.all_symbols)
    metric_table.add_row("Code Symbols", f"{symbol_count} found", "Classes, methods & top-level functions")

    console.print(metric_table)

    # Language breakdown table if multiple
    if len(report.languages) > 1:
        lang_table = Table(box=ROUNDED, show_header=True, header_style="bold cyan")
        lang_table.add_column("Language", style="bold", width=18)
        lang_table.add_column("Files", justify="right", width=10)
        lang_table.add_column("Lines", justify="right", width=12)
        lang_table.add_column("Share", justify="right", width=10)

        for lstat in report.languages[:6]:
            lang_table.add_row(
                lstat.language,
                str(lstat.file_count),
                f"{lstat.lines_of_code:,}",
                f"{lstat.percentage:.1f}%",
            )
        console.print(lang_table)

    # Security alerts callout if findings exist
    if report.security_findings:
        finding_rows = []
        for finding in report.security_findings[:5]:
            finding_rows.append(
                f"• [bold red]{finding.rule_name}[/bold red] at [dim]{finding.file_path}:{finding.line_number}[/dim] -> {finding.masked_snippet}"
            )
        alert_body = "\n".join(finding_rows)
        console.print(
            Panel(
                alert_body,
                title="[bold red]Security Alerts: Potential Credentials Detected[/bold red]",
                border_style="red",
                box=ROUNDED,
            )
        )

    # Final readiness banner
    if report.security_findings:
        console.print("[bold red]⚠ Repository scan flagged security risks. Remediate credentials before inference.[/bold red]")
    else:
        console.print("[bold green]✓ Repository is fully indexed and ready for agent tasks.[/bold green]")
