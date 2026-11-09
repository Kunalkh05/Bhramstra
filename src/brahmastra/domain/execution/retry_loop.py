"""
Bounded retry manager for autonomous test verification and diagnosis.
"""
from typing import Callable, Optional

from brahmastra.domain.execution.models import RetrySession, TestResult


class BoundedRetryManager:
    """
    Manages bounded test-fix-verify iterations with strict loop termination.
    Prevents runaway token or process consumption.
    """

    def __init__(self, max_retries: int = 3):
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        self.max_retries = max_retries

    def run_bounded_loop(
        self,
        test_fn: Callable[[], TestResult],
        fix_fn: Optional[Callable[[int, TestResult], bool]] = None,
    ) -> RetrySession:
        """
        Executes test verification with bounded retries.
        - test_fn: executes tests and returns TestResult
        - fix_fn: optional remediation callback receiving (attempt_number, last_test_result).
                  Returns True if fix was applied, False if gave up.
        """
        session = RetrySession(max_attempts=self.max_retries)

        for attempt in range(1, self.max_retries + 1):
            session.attempts_made = attempt
            result = test_fn()
            session.results.append(result)

            if result.passed:
                session.resolved = True
                session.final_diagnosis = f"All tests passed successfully on attempt {attempt}."
                return session

            # If tests failed and we have retries remaining, attempt fix
            if attempt < self.max_retries and fix_fn is not None:
                fix_succeeded = fix_fn(attempt, result)
                if not fix_succeeded:
                    session.final_diagnosis = f"Remediation hook declined or failed on attempt {attempt}."
                    break
            elif attempt == self.max_retries:
                session.final_diagnosis = (
                    f"Exhausted maximum retry budget ({self.max_retries} attempts). "
                    f"Remaining failures: {len(result.failed_tests)} test(s)."
                )

        return session
