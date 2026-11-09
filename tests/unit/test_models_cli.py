"""
CLI integration tests for brahmastra models list command.
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


def test_models_cli_help(cli_runner: CliRunner):
    """Verify brahmastra models --help shows usage."""
    res = cli_runner.invoke(app, ["models", "--help"])
    assert res.exit_code == 0
    assert "list" in res.output


@respx.mock
def test_models_list_cli(cli_runner: CliRunner):
    """Verify brahmastra models list queries providers and renders table."""
    # 1. Register organization and account
    cli_runner.invoke(app, ["org", "add", "dev-org"])
    cli_runner.invoke(app, ["provider", "add", "ollama", "my-ollama", "--endpoint", "http://localhost:11434"])

    # 2. Mock Ollama tags endpoint
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={
            "models": [
                {
                    "name": "llama3:latest",
                    "details": {"parameter_size": "8.0B", "family": "llama"},
                }
            ]
        },
    )

    # 3. Invoke CLI command
    res = cli_runner.invoke(app, ["models", "list"])
    assert res.exit_code == 0
    assert "Available Models" in res.output
    assert "llama3:latest" in res.output
    assert "ollama" in res.output
    assert "Local" in res.output
