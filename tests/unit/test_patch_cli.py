"""
Unit tests for brahmastra patch CLI commands.
"""
from pathlib import Path
from typer.testing import CliRunner
import pytest

from brahmastra.cli.app import app

runner = CliRunner()


def test_patch_cli_help():
    """Verify brahmastra patch --help output."""
    result = runner.invoke(app, ["patch", "--help"])
    assert result.exit_code == 0
    assert "Review unified diffs" in result.output
    assert "preview" in result.output
    assert "apply" in result.output
    assert "eval-cmd" in result.output


def test_patch_cli_preview(tmp_path: Path):
    """Verify preview command generates diff without modifying files."""
    orig_file = tmp_path / "hello.py"
    orig_file.write_text("print('hello')\n", encoding="utf-8")

    repl_file = tmp_path / "hello_new.py"
    repl_file.write_text("print('hello world')\n", encoding="utf-8")

    result = runner.invoke(app, ["patch", "preview", str(orig_file), str(repl_file), "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Proposed Diff" in result.output
    assert "+1 / -1 lines" in result.output

    # Original file must remain unmodified
    assert orig_file.read_text(encoding="utf-8") == "print('hello')\n"


def test_patch_cli_apply_auto_approve(tmp_path: Path):
    """Verify apply --yes modifies the target file."""
    orig_file = tmp_path / "calc.py"
    orig_file.write_text("def add(a, b): return a\n", encoding="utf-8")

    repl_file = tmp_path / "calc_new.py"
    repl_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")

    result = runner.invoke(app, ["patch", "apply", str(orig_file), str(repl_file), "--yes", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Patch successfully applied" in result.output
    assert orig_file.read_text(encoding="utf-8") == "def add(a, b): return a + b\n"


def test_patch_cli_apply_rejection(tmp_path: Path):
    """Verify rejecting prompt leaves original file unmodified."""
    orig_file = tmp_path / "stable.py"
    orig_file.write_text("STABLE = True\n", encoding="utf-8")

    repl_file = tmp_path / "unstable.py"
    repl_file.write_text("STABLE = False\n", encoding="utf-8")

    # Simulate typing 'n' to prompt
    result = runner.invoke(app, ["patch", "apply", str(orig_file), str(repl_file), "--root", str(tmp_path)], input="n\n")
    assert result.exit_code == 0
    assert "Patch rejected by user" in result.output
    assert orig_file.read_text(encoding="utf-8") == "STABLE = True\n"


def test_patch_cli_eval_cmd_safe_approved():
    """Verify evaluating safe command with --yes approves."""
    result = runner.invoke(app, ["patch", "eval-cmd", "pytest -v", "--yes"])
    assert result.exit_code == 0
    assert "SAFE_READ" in result.output
    assert "Command approved for execution" in result.output


def test_patch_cli_eval_cmd_dangerous_blocked():
    """Verify evaluating dangerous command blocks auto-approval."""
    result = runner.invoke(app, ["patch", "eval-cmd", "rm -rf /", "--yes"])
    assert result.exit_code == 0
    assert "DANGEROUS" in result.output
    assert "DENIED: Highly dangerous command cannot be auto-approved" in result.output
