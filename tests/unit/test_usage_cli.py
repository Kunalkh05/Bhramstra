"""
CLI integration tests for brahmastra usage command.
"""

import pytest
from typer.testing import CliRunner
from brahmastra.cli.app import app
from brahmastra.domain.observability.models import UsageRecordCreate
from brahmastra.application.use_cases.usage_use_cases import record_usage


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAHMASTRA_HOME", str(tmp_path))
    monkeypatch.setenv("BRAHMASTRA_VAULT", "memory")


def test_usage_cli_empty(cli_runner: CliRunner):
    """Verify brahmastra usage displays empty state gracefully."""
    cli_runner.invoke(app, ["org", "add", "empty-org"])
    res = cli_runner.invoke(app, ["usage"])
    assert res.exit_code == 0
    assert "No usage recorded yet" in res.output


def test_usage_cli_with_records(cli_runner: CliRunner):
    """Verify brahmastra usage renders aggregate tables and details."""
    cli_runner.invoke(app, ["org", "add", "active-org"])
    cli_runner.invoke(app, ["provider", "add", "openrouter", "acc-demo"])

    record_usage(
        UsageRecordCreate(
            org_name="active-org",
            account_name="acc-demo",
            model_id="gpt-4o",
            prompt_tokens=150,
            completion_tokens=75,
            cost_micro_usd=2500,
            latency_ms=310.5,
        )
    )

    # 1. Standard summary
    res = cli_runner.invoke(app, ["usage"])
    assert res.exit_code == 0
    assert "BRAHMASTRA Usage Report" in res.output
    assert "Total Tokens" in res.output
    assert "225" in res.output
    assert "gpt-4o" in res.output

    # 2. Detailed log
    res_detail = cli_runner.invoke(app, ["usage", "--details"])
    assert res_detail.exit_code == 0
    assert "Recent Requests" in res_detail.output
    assert "310.5 ms" in res_detail.output
