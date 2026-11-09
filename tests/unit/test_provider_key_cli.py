"""
CLI integration tests for brahmastra provider and brahmastra key commands.
"""

import pytest
import respx
from typer.testing import CliRunner
from brahmastra.cli.app import app


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Ensure tests run against an isolated storage path and in-memory vault."""
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")


@respx.mock
def test_provider_cli_flow(cli_runner: CliRunner):
    """Verify provider add, list, and test commands."""
    respx.get("https://openrouter.ai/api/v1/models").respond(
        status_code=200,
        json={"data": []},
    )

    # 1. Add organization first
    cli_runner.invoke(app, ["org", "add", "default-org"])

    # 2. Add provider account
    res = cli_runner.invoke(app, ["provider", "add", "openrouter", "or-main", "--desc", "Main OpenRouter"])
    assert res.exit_code == 0
    assert "Registered provider account 'or-main'" in res.output

    # 3. List providers
    res = cli_runner.invoke(app, ["provider", "list"])
    assert res.exit_code == 0
    assert "or-main" in res.output
    assert "openrouter" in res.output

    # 4. Test provider (initially no credentials)
    res = cli_runner.invoke(app, ["provider", "test", "or-main"])
    assert res.exit_code == 0
    assert "Credentials registered: 0" in res.output
    assert "Status:  HEALTHY" in res.output


def test_key_cli_flow(cli_runner: CliRunner):
    """Verify key add, list, test, rotate, revoke, and remove commands."""
    # Register org and provider account
    cli_runner.invoke(app, ["org", "add", "test-org"])
    cli_runner.invoke(app, ["provider", "add", "openrouter", "or-acc"])

    # 1. Add key non-interactively via stdin
    res = cli_runner.invoke(
        app,
        ["key", "add", "or-acc", "primary-key"],
        input="sk-or-v1-secret12345678\n",
    )
    assert res.exit_code == 0
    assert "Credential 'primary-key' saved securely in OS Vault" in res.output
    assert "vault:brahmastra:openrouter:or-acc:primary-key" in res.output
    # Ensure raw secret is NOT in output
    assert "sk-or-v1-secret12345678" not in res.output
    assert "sk-o...5678" in res.output

    # 2. List keys
    res = cli_runner.invoke(app, ["key", "list"])
    assert res.exit_code == 0
    assert "primary-key" in res.output
    assert "ACTIVE" in res.output

    # 3. Test key
    res = cli_runner.invoke(app, ["key", "test", "primary-key", "--account", "or-acc"])
    assert res.exit_code == 0
    assert "is accessible in OS Vault" in res.output

    # 4. Rotate key
    res = cli_runner.invoke(
        app,
        ["key", "rotate", "primary-key", "--account", "or-acc"],
        input="sk-or-v1-new99998888\n",
    )
    assert res.exit_code == 0
    assert "rotated successfully" in res.output
    assert "sk-o...8888" in res.output

    # 5. Revoke key
    res = cli_runner.invoke(app, ["key", "revoke", "primary-key", "--account", "or-acc", "--force"])
    assert res.exit_code == 0
    assert "REVOKED" in res.output

    # 6. Remove key
    res = cli_runner.invoke(app, ["key", "remove", "primary-key", "--account", "or-acc", "--force"])
    assert res.exit_code == 0
    assert "permanently removed" in res.output
