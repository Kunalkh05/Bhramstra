"""
Application use cases for controlled test execution and bounded retry sessions.
"""
from pathlib import Path
import sys
from typing import Callable, Optional

from brahmastra.domain.execution.models import (
    RetrySession,
    TestExecutionConfig,
    TestResult,
)
from brahmastra.domain.execution.retry_loop import BoundedRetryManager
from brahmastra.domain.execution.test_runner import ControlledTestRunner


def run_project_tests(
    target: Optional[str] = None,
    timeout_seconds: float = 30.0,
    working_dir: Optional[Path] = None,
    strip_sensitive_env: bool = True,
) -> TestResult:
    """
    Executes project tests inside a tightly controlled subprocess.
    """
    cwd = (working_dir or Path.cwd()).resolve()

    cmd = [sys.executable, "-m", "pytest", "-v"]
    if target:
        cleaned_target = target.strip()
        if cleaned_target.startswith("-"):
            raise ValueError(f"Invalid test target '{target}': Flag or option injection detected (BRAH-SEC-004).")

        file_part = cleaned_target.split("::")[0].strip()
        if file_part:
            resolved_target = (cwd / file_part).resolve()
            if not resolved_target.is_relative_to(cwd):
                raise ValueError(
                    f"Invalid test target '{target}': Path traversal outside working directory detected (BRAH-SEC-004)."
                )

        cmd.extend(["--", cleaned_target])

    config = TestExecutionConfig(
        command=cmd,
        working_dir=cwd,
        timeout_seconds=timeout_seconds,
        strip_sensitive_env=strip_sensitive_env,
    )

    return ControlledTestRunner.run(config)


def run_verification_with_retries(
    target: Optional[str] = None,
    max_retries: int = 3,
    timeout_seconds: float = 30.0,
    working_dir: Optional[Path] = None,
    fix_fn: Optional[Callable[[int, TestResult], bool]] = None,
) -> RetrySession:
    """
    Executes tests with bounded autonomous retry attempts.
    """
    manager = BoundedRetryManager(max_retries=max_retries)

    def _execute() -> TestResult:
        return run_project_tests(
            target=target,
            timeout_seconds=timeout_seconds,
            working_dir=working_dir,
        )

    return manager.run_bounded_loop(test_fn=_execute, fix_fn=fix_fn)
