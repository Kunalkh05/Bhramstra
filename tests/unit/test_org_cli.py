"""
CLI integration tests for brahmastra org commands.
"""

import pytest
from typer.testing import CliRunner
from brahmastra.cli.app import app


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Ensure every CLI test uses an isolated storage directory."""
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))


def test_org_cli_help(cli_runner: CliRunner):
    """Verify brahmastra org --help works and shows subcommands."""
    result = cli_runner.invoke(app, ["org", "--help"])
    assert result.exit_code == 0
    assert "add" in result.output
    assert "list" in result.output
    assert "switch" in result.output
    assert "current" in result.output
    assert "show" in result.output


def test_org_cli_lifecycle(cli_runner: CliRunner):
    """Verify add, list, current, switch, and show via CLI."""
    # 1. Initially empty
    res = cli_runner.invoke(app, ["org", "list"])
    assert res.exit_code == 0
    assert "No organizations found" in res.output

    # 2. Add personal org
    res = cli_runner.invoke(app, ["org", "add", "personal", "--desc", "Personal workspace"])
    assert res.exit_code == 0
    assert "Created organization 'personal'" in res.output

    # 3. Add work org
    res = cli_runner.invoke(app, ["org", "add", "work-corp"])
    assert res.exit_code == 0
    assert "Created organization 'work-corp'" in res.output

    # 4. Check current org (should be personal as first created)
    res = cli_runner.invoke(app, ["org", "current"])
    assert res.exit_code == 0
    assert "personal" in res.output

    # 5. List orgs
    res = cli_runner.invoke(app, ["org", "list"])
    assert res.exit_code == 0
    assert "personal" in res.output
    assert "work-corp" in res.output

    # 6. Switch to work-corp
    res = cli_runner.invoke(app, ["org", "switch", "work-corp"])
    assert res.exit_code == 0
    assert "Switched active profile to organization 'work-corp'" in res.output

    # 7. Check current org is now work-corp
    res = cli_runner.invoke(app, ["org", "current"])
    assert res.exit_code == 0
    assert "work-corp" in res.output

    # 8. Show org details
    res = cli_runner.invoke(app, ["org", "show", "work-corp"])
    assert res.exit_code == 0
    assert "work-corp" in res.output
    assert "Yes" in res.output  # is_active


def test_org_cli_duplicate_error(cli_runner: CliRunner):
    """Verify adding duplicate org prints error and exits with code 1."""
    res1 = cli_runner.invoke(app, ["org", "add", "my-org"])
    assert res1.exit_code == 0

    res2 = cli_runner.invoke(app, ["org", "add", "my-org"])
    assert res2.exit_code == 1
    assert "already exists" in res2.output


def test_org_cli_switch_nonexistent_error(cli_runner: CliRunner):
    """Verify switching to nonexistent org fails gracefully."""
    res = cli_runner.invoke(app, ["org", "switch", "nonexistent"])
    assert res.exit_code == 1
    assert "not found" in res.output
