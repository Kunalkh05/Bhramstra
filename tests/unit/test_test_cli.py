"""
Unit tests for brahmastra test CLI command.
"""
from typer.testing import CliRunner
import pytest

from brahmastra.cli.app import app

runner = CliRunner()


def test_test_cli_help():
    """Verify brahmastra test --help output."""
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0
    assert "Execute tests in an isolated, sandboxed subprocess" in result.output
    assert "--timeout" in result.output


def test_test_cli_run_single_passing_test():
    """Verify brahmastra test on a known passing unit test."""
    result = runner.invoke(app, ["test", "tests/unit/test_cli.py", "--timeout", "10"])
    assert result.exit_code == 0
    assert "Running controlled test suite" in result.output
    assert "All tests passed successfully" in result.output


def test_test_cli_run_nonexistent_test():
    """Verify brahmastra test handles failed/missing test gracefully with error code."""
    result = runner.invoke(app, ["test", "tests/unit/nonexistent_test_target.py", "--timeout", "10"])
    assert result.exit_code != 0
    assert "Test suite failed" in result.output or "Failed Test Target" in result.output
