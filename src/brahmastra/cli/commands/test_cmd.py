"""
CLI command for controlled test execution and verification.
"""
from typing import Optional
import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from brahmastra.application.use_cases.execution_use_cases import run_project_tests

console = Console()
err_console = Console(stderr=True)


def test_command(
    target: Optional[str] = typer.Argument(
        None, help="Optional test path or file (e.g., 'tests/unit/test_cli.py')."
    ),
    timeout: float = typer.Option(
        30.0, "--timeout", "-t", help="Maximum execution timeout in seconds."
    ),
    no_strip: bool = typer.Option(
        False, "--no-strip", help="Do not strip sensitive environment variables."
    ),
) -> None:
    """
    Execute tests in an isolated, sandboxed subprocess with strict timeouts.
    """
    console.print(f"[bold cyan]Running controlled test suite...[/bold cyan] [dim](Timeout: {timeout}s)[/dim]")

    result = run_project_tests(
        target=target,
        timeout_seconds=timeout,
        strip_sensitive_env=not no_strip,
    )

    if result.timed_out:
        err_console.print(
            Panel(
                f"[bold red]EXECUTION TIMEOUT:[/bold red] Test process exceeded {timeout}s limit and was forcefully terminated.",
                title="[bold red]Sandbox Violation[/bold red]",
                box=ROUNDED,
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    if result.passed:
        console.print(
            f"[bold green]✓ All tests passed successfully[/bold green] [dim]({result.duration_seconds}s)[/dim]"
        )
    else:
        # Failure table
        fail_table = Table(box=ROUNDED, show_header=True, header_style="bold red")
        fail_table.add_column("Failed Test Target", style="bold white", width=55)
        fail_table.add_column("Status", style="bold red", width=12)

        if result.failed_tests:
            for ft in result.failed_tests:
                fail_table.add_row(ft, "FAILED")
            console.print(fail_table)

        if result.error_summary:
            console.print(
                Panel(
                    result.error_summary,
                    title="[bold red]Test Failure Diagnosis[/bold red]",
                    box=ROUNDED,
                    border_style="red",
                )
            )

        err_console.print(
            f"[bold red]✗ Test suite failed with exit code {result.exit_code}[/bold red] [dim]({result.duration_seconds}s)[/dim]"
        )
        raise typer.Exit(code=result.exit_code or 1)
