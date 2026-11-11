"""
Unit tests for ControlledTestRunner environment sanitization, timeouts, and failure parsing.
"""
from pathlib import Path
import sys

from brahmastra.domain.execution.models import TestExecutionConfig
from brahmastra.domain.execution.test_runner import ControlledTestRunner


def test_sanitize_environment_strips_sensitive_keys():
    """Verify sensitive environment variables are stripped and safe system keys preserved."""
    dirty_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/Users/developer",
        "OPENAI_API_KEY": "sk-proj-super-secret-key",
        "ANTHROPIC_AUTH_TOKEN": "sk-ant-secret",
        "DATABASE_PASSWORD": "rootpassword",
        "SAFE_CUSTOM_VAR": "hello_world",
    }

    sanitized = ControlledTestRunner.sanitize_environment(dirty_env, strip_sensitive=True)

    # Safe system keys preserved
    assert sanitized["PATH"] == "/usr/bin:/bin"
    assert sanitized["HOME"] == "/Users/developer"
    assert sanitized["SAFE_CUSTOM_VAR"] == "hello_world"

    # Sensitive keys stripped
    assert "OPENAI_API_KEY" not in sanitized
    assert "ANTHROPIC_AUTH_TOKEN" not in sanitized
    assert "DATABASE_PASSWORD" not in sanitized

    # Injected defaults
    assert sanitized["PYTHONUNBUFFERED"] == "1"
    assert sanitized["BRAHMASTRA_VAULT"] == "memory"


def test_controlled_test_runner_timeout():
    """Verify runner kills long-running processes when timeout threshold is exceeded."""
    config = TestExecutionConfig(
        command=[sys.executable, "-c", "import time; time.sleep(5)"],
        working_dir=Path.cwd(),
        timeout_seconds=0.3,
    )

    result = ControlledTestRunner.run(config)
    assert result.timed_out is True
    assert result.passed is False
    assert result.duration_seconds >= 0.3
    assert "Test execution exceeded strict process timeout" in result.error_summary


def test_controlled_test_runner_successful_execution():
    """Verify runner captures exit code 0 and stdout for successful processes."""
    config = TestExecutionConfig(
        command=[sys.executable, "-c", "print('TEST_OUTPUT_OK')"],
        working_dir=Path.cwd(),
        timeout_seconds=5.0,
    )

    result = ControlledTestRunner.run(config)
    assert result.passed is True
    assert result.timed_out is False
    assert result.exit_code == 0
    assert "TEST_OUTPUT_OK" in result.stdout


def test_parse_failed_tests():
    """Verify parsing pytest output for failed test names."""
    sample_output = """
============================= test session starts ==============================
collected 3 items

tests/unit/test_foo.py::test_one PASSED
tests/unit/test_foo.py::test_two FAILED
tests/unit/test_bar.py::test_three FAILED

=================================== FAILURES ===================================
FAILED tests/unit/test_foo.py::test_two - AssertionError: 1 != 2
FAILED tests/unit/test_bar.py::test_three - ValueError: invalid input
========================= 2 failed, 1 passed in 0.12s ==========================
"""
    failed = ControlledTestRunner._parse_failed_tests(sample_output)
    assert len(failed) == 2
    assert "tests/unit/test_foo.py::test_two" in failed
    assert "tests/unit/test_bar.py::test_three" in failed
