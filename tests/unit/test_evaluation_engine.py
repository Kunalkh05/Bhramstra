"""
Unit tests for evaluation benchmarks, task pattern matching, and scorecard aggregation.
"""
from typing import List, Optional
import pytest

from brahmastra.domain.evaluation.benchmarks import get_benchmark_suite
from brahmastra.domain.evaluation.evaluator import EvaluationEngine
from brahmastra.domain.evaluation.models import EvalTask
from brahmastra.domain.providers.interface import ProviderInterface
from brahmastra.domain.providers.models import (
    GenerationRequest,
    GenerationResponse,
    GenerationUsage,
    HealthStatus,
    ModelInfo,
)


class MockProviderAdapter(ProviderInterface):
    """Mock provider adapter for reproducible deterministic evaluation tests."""

    def __init__(self, response_text: str):
        self.response_text = response_text
        self.call_count = 0

    @property
    def provider_type(self) -> str:
        return "mock"

    def generate(self, request: GenerationRequest, api_key: Optional[str] = None) -> GenerationResponse:
        self.call_count += 1
        return GenerationResponse(
            content=self.response_text,
            model=request.model,
            usage=GenerationUsage(prompt_tokens=25, completion_tokens=40, total_tokens=65),
        )

    def list_models(self, api_key: Optional[str] = None) -> List[ModelInfo]:
        return []

    def health_check(self, api_key: Optional[str] = None) -> HealthStatus:
        return HealthStatus(healthy=True, latency_ms=10.0)


def test_canonical_benchmark_suite_loading():
    """Verify canonical benchmark suite 'core' loads correctly."""
    suite = get_benchmark_suite("core")
    assert suite is not None
    assert suite.suite_id == "core"
    assert len(suite.tasks) >= 4
    task_ids = [t.task_id for t in suite.tasks]
    assert "core-fibonacci" in task_ids
    assert "core-bugfix-palindrome" in task_ids


def test_evaluate_task_pattern_match_success():
    """Verify evaluation task passes when expected regex patterns are matched."""
    task = EvalTask(
        task_id="test-fib",
        name="Fibonacci",
        prompt="Write fibonacci(n)",
        expected_patterns=[r"def\s+fibonacci\s*\(", r"return"],
    )

    valid_response = "def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)\n"
    adapter = MockProviderAdapter(valid_response)

    result = EvaluationEngine.evaluate_task(
        task=task,
        model_id="mock-coder",
        adapter=adapter,
    )

    assert result.passed is True
    assert result.prompt_tokens == 25
    assert result.completion_tokens == 40
    assert result.latency_ms >= 0.0
    assert result.cost_micro_usd == 65  # (25 + 40) * 1


def test_evaluate_task_pattern_match_failure():
    """Verify evaluation task fails when expected patterns are missing."""
    task = EvalTask(
        task_id="test-fib",
        name="Fibonacci",
        prompt="Write fibonacci(n)",
        expected_patterns=[r"def\s+fibonacci\s*\("],
    )

    # Missing the function def
    invalid_response = "Here is the code: print(42)"
    adapter = MockProviderAdapter(invalid_response)

    result = EvaluationEngine.evaluate_task(
        task=task,
        model_id="mock-coder",
        adapter=adapter,
    )

    assert result.passed is False
    assert result.error_message is None


def test_run_suite_aggregation():
    """Verify suite aggregation calculates pass rates, total tokens, and average latency."""
    suite = get_benchmark_suite("core")
    assert suite is not None

    # Response that satisfies all patterns in core tasks
    universal_response = (
        "def fibonacci(n): return n\n"
        "s[::-1]\n"
        "def extract_emails(text): return re.findall(r'@[a-zA-Z0-9]', text)\n"
        "def mask_key(key): return '[REDACTED]' if len(key) <= 8 else key[:4] + '[REDACTED]' + key[-4:]\n"
    )
    adapter = MockProviderAdapter(universal_response)

    report = EvaluationEngine.run_suite(
        suite=suite,
        model_id="mock-model",
        adapter=adapter,
    )

    assert report.total_tasks == len(suite.tasks)
    assert report.passed_tasks == len(suite.tasks)
    assert report.pass_rate == 100.0
    assert report.total_tokens == len(suite.tasks) * 65
    assert report.avg_latency_ms >= 0.0
