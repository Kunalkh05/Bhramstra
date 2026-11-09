"""
Unit tests for brahmastra eval CLI commands.
"""
from unittest.mock import patch
from typer.testing import CliRunner
import pytest

from brahmastra.cli.app import app
from brahmastra.domain.evaluation.models import BenchmarkReport, TaskEvalResult

runner = CliRunner()


def test_eval_cli_help():
    """Verify brahmastra eval --help."""
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "Run reproducible model benchmarks" in result.output
    assert "list" in result.output
    assert "run" in result.output


def test_eval_cli_list():
    """Verify brahmastra eval list displays suites."""
    result = runner.invoke(app, ["eval", "list"])
    assert result.exit_code == 0
    assert "core" in result.output
    assert "Core Developer" in result.output


def test_eval_cli_run_mocked():
    """Verify brahmastra eval run displays scorecard."""
    mock_report = BenchmarkReport(
        suite_id="core",
        model_id="mock-coder",
        total_tasks=2,
        passed_tasks=2,
        pass_rate=100.0,
        total_tokens=130,
        total_cost_micro_usd=130,
        avg_latency_ms=105.0,
        task_results=[
            TaskEvalResult(
                task_id="core-fibonacci",
                model_id="mock-coder",
                passed=True,
                response_text="def fibonacci(n): pass",
                latency_ms=100.0,
                cost_micro_usd=65,
            ),
            TaskEvalResult(
                task_id="core-bugfix",
                model_id="mock-coder",
                passed=True,
                response_text="s[::-1]",
                latency_ms=110.0,
                cost_micro_usd=65,
            ),
        ],
    )

    with patch("brahmastra.cli.commands.eval_cmd.evaluate_model_on_suite", return_value=mock_report):
        result = runner.invoke(app, ["eval", "run", "core", "--model", "mock-coder"])
        assert result.exit_code == 0
        assert "Model Evaluation Scorecard" in result.output
        assert "100.0%" in result.output
        assert "core-fibonacci" in result.output
        assert "PASS" in result.output
