"""
Unit tests for BoundedRetryManager termination and diagnosis.
"""
from brahmastra.domain.execution.models import TestResult
from brahmastra.domain.execution.retry_loop import BoundedRetryManager


def test_retry_manager_success_on_first_try():
    """Verify stops immediately when test passes on first try."""
    manager = BoundedRetryManager(max_retries=3)

    call_count = 0

    def mock_test():
        nonlocal call_count
        call_count += 1
        return TestResult(
            exit_code=0,
            stdout="PASSED",
            stderr="",
            duration_seconds=0.1,
            passed=True,
        )

    session = manager.run_bounded_loop(test_fn=mock_test)

    assert session.resolved is True
    assert session.attempts_made == 1
    assert call_count == 1
    assert len(session.results) == 1


def test_retry_manager_resolves_after_fix():
    """Verify manager re-tests after fix hook and succeeds."""
    manager = BoundedRetryManager(max_retries=3)

    is_fixed = False
    test_calls = 0
    fix_calls = 0

    def mock_test():
        nonlocal test_calls
        test_calls += 1
        return TestResult(
            exit_code=0 if is_fixed else 1,
            stdout="PASSED" if is_fixed else "FAILED",
            stderr="",
            duration_seconds=0.1,
            passed=is_fixed,
        )

    def mock_fix(attempt: int, result: TestResult) -> bool:
        nonlocal fix_calls, is_fixed
        fix_calls += 1
        is_fixed = True
        return True

    session = manager.run_bounded_loop(test_fn=mock_test, fix_fn=mock_fix)

    assert session.resolved is True
    assert session.attempts_made == 2
    assert test_calls == 2
    assert fix_calls == 1


def test_retry_manager_exhausts_retries():
    """Verify manager terminates cleanly without infinite loops when retries exhaust."""
    manager = BoundedRetryManager(max_retries=3)

    test_calls = 0

    def mock_failing_test():
        nonlocal test_calls
        test_calls += 1
        return TestResult(
            exit_code=1,
            stdout="",
            stderr="AssertionError",
            duration_seconds=0.1,
            passed=False,
            failed_tests=["tests/unit/test_broken.py::test_case"],
        )

    session = manager.run_bounded_loop(test_fn=mock_failing_test, fix_fn=lambda a, r: True)

    assert session.resolved is False
    assert session.attempts_made == 3
    assert test_calls == 3
    assert "Exhausted maximum retry budget (3 attempts)" in session.final_diagnosis
