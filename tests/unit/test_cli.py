"""
Unit tests for CLI shell, help, version, and doctor diagnostics.
"""

from typer.testing import CliRunner
from brahmastra import __version__
from brahmastra.cli.app import app


def test_cli_help(cli_runner: CliRunner):
    """Verify that --help exits cleanly and displays description."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "BRAHMASTRA" in result.output
    assert "doctor" in result.output


def test_cli_no_args_shows_help(cli_runner: CliRunner):
    """Verify running brahmastra without arguments displays help / usage."""
    result = cli_runner.invoke(app, [])
    # typer no_args_is_help defaults to code 0 or 2 depending on version; output should have usage
    assert "Usage" in result.output or "brahmastra" in result.output


def test_cli_version_flag(cli_runner: CliRunner):
    """Verify that --version outputs the correct version."""
    result = cli_runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_short_version_flag(cli_runner: CliRunner):
    """Verify that -v outputs the correct version."""
    result = cli_runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_doctor(cli_runner: CliRunner):
    """Verify that doctor command executes diagnostics table."""
    result = cli_runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "BRAHMASTRA System Health Check" in result.output
    assert "Python Version" in result.output
    assert "Operating System" in result.output
    assert "CPU Architecture" in result.output
    assert "SQLite Engine" in result.output
