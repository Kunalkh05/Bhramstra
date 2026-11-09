"""
Unit tests for brahmastra analyze CLI command.
"""
import json
from pathlib import Path
from typer.testing import CliRunner
import pytest

from brahmastra.cli.app import app

runner = CliRunner()


def test_analyze_cli_help():
    """Verify brahmastra analyze --help output."""
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "Perform static analysis" in result.output
    assert "--depth" in result.output
    assert "--security" in result.output
    assert "--json" in result.output


def test_analyze_cli_execution_on_temp_repo(tmp_path: Path):
    """Verify execution of analyze command on a test repository."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("class Server:\n    pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project\nOverview\n", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "Codebase Analysis" in result.output
    assert "Total Files: 2" in result.output
    assert "Server" not in result.output or "Code Symbols" in result.output
    assert "Repository is fully indexed" in result.output


def test_analyze_cli_json_output(tmp_path: Path):
    """Verify analyze --json emits valid machine-readable JSON."""
    src_file = tmp_path / "script.py"
    src_file.write_text("def main():\n    print('hello')\n", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_files"] == 1
    assert data["languages"][0]["language"] == "Python"
    assert data["estimated_tokens"] > 0
    assert "files" in data


def test_analyze_cli_nonexistent_target_fails():
    """Verify analyze fails gracefully on invalid path."""
    result = runner.invoke(app, ["analyze", "/nonexistent/test/path/brahmastra_abc"])
    assert result.exit_code == 1
    assert "Target path does not exist" in result.output
