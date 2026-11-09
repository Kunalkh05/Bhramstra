"""
CLI integration tests for brahmastra route and brahmastra run commands.
"""

import pytest
import respx
from typer.testing import CliRunner
from brahmastra.cli.app import app
from brahmastra.application.use_cases.model_registry_use_cases import sync_models_for_account


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")


@respx.mock
def test_routing_cli_explain(cli_runner: CliRunner):
    """Verify brahmastra route renders decision panel and evaluation matrix."""
    # 1. Setup org and provider
    cli_runner.invoke(app, ["org", "add", "my-org"])
    cli_runner.invoke(app, ["provider", "add", "ollama", "local-ollama", "--endpoint", "http://localhost:11434"])

    # 2. Mock Ollama tags and sync models
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={"models": [{"name": "qwen2.5-coder:7b", "details": {"parameter_size": "7.6B"}}]},
    )
    sync_models_for_account("local-ollama")

    # 3. Simulate route
    res = cli_runner.invoke(app, ["route", "Write a python function"])
    assert res.exit_code == 0
    assert "BRAHMASTRA Routing Decision" in res.output
    assert "qwen2.5-coder:7b" in res.output
    assert "Candidate Evaluation Matrix" in res.output
    assert "YES" in res.output


@respx.mock
def test_run_cli_execution(cli_runner: CliRunner):
    """Verify brahmastra run executes prompt through routed provider."""
    # 1. Setup
    cli_runner.invoke(app, ["org", "add", "exec-org"])
    cli_runner.invoke(app, ["provider", "add", "ollama", "acc-exec", "--endpoint", "http://localhost:11434"])

    # 2. Mock model list and chat generation
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={"models": [{"name": "llama3:latest", "details": {}}]},
    )
    respx.post("http://localhost:11434/api/chat").respond(
        status_code=200,
        json={
            "model": "llama3:latest",
            "message": {"role": "assistant", "content": "Def hello(): return True"},
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 8,
        },
    )
    sync_models_for_account("acc-exec")

    # 3. Run task
    res = cli_runner.invoke(app, ["run", "Implement hello function"])
    assert res.exit_code == 0
    assert "Routing and executing task" in res.output
    assert "Def hello(): return True" in res.output
    assert "Tokens: 18" in res.output
