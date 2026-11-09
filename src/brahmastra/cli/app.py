"""
Main CLI Application entrypoint for BRAHMASTRA AI.
"""

from typing import Optional
import typer
from rich.console import Console

from brahmastra import __version__
from brahmastra.cli.commands.doctor import run_doctor
from brahmastra.cli.commands.org import org_app

app = typer.Typer(
    name="brahmastra",
    help="BRAHMASTRA — Provider-independent AI orchestration platform & CLI coding assistant.",
    no_args_is_help=True,
    add_completion=False,
)

# Register sub-command groups
app.add_typer(org_app, name="org")

console = Console()


def version_callback(value: bool):
    """Callback to print version and exit."""
    if value:
        console.print(f"[bold cyan]BRAHMASTRA AI[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show BRAHMASTRA version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    BRAHMASTRA: Provider-independent AI orchestration and developer CLI assistant.
    """
    pass


@app.command(name="doctor")
def doctor_command():
    """
    Inspect local environment, OS, architecture, and system capabilities.
    """
    success = run_doctor()
    if not success:
        raise typer.Exit(code=1)


def main():
    """Main CLI entrypoint callable by console script."""
    app()


if __name__ == "__main__":
    main()
