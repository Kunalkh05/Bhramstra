"""
Main CLI Application entrypoint for BRAHMASTRA AI.
"""

from typing import Optional
import typer
from rich.console import Console

from brahmastra import __version__
from brahmastra.cli.commands.doctor import run_doctor
from brahmastra.cli.commands.org import org_app
from brahmastra.cli.commands.provider import provider_app
from brahmastra.cli.commands.key import key_app
from brahmastra.cli.commands.models import models_app
from brahmastra.cli.commands.usage import usage_app
from brahmastra.cli.commands.route import route_command, run_command_handler
from brahmastra.cli.commands.analyze import analyze_command
from brahmastra.cli.commands.patch import patch_app
from brahmastra.cli.commands.test_cmd import test_command
from brahmastra.cli.commands.eval_cmd import eval_app

app = typer.Typer(
    name="brahmastra",
    help="BRAHMASTRA — Provider-independent AI orchestration platform & CLI coding assistant.",
    no_args_is_help=True,
    add_completion=False,
)

# Register sub-command groups
app.add_typer(org_app, name="org")
app.add_typer(provider_app, name="provider")
app.add_typer(key_app, name="key")
app.add_typer(models_app, name="models")
app.add_typer(usage_app, name="usage")
app.add_typer(patch_app, name="patch")
app.add_typer(eval_app, name="eval")

# Standalone top-level commands
app.command(name="route")(route_command)
app.command(name="run")(run_command_handler)
app.command(name="analyze")(analyze_command)
app.command(name="test")(test_command)

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
