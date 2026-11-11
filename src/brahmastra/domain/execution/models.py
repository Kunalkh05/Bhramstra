"""
Domain models for controlled test execution, sandboxing, and bounded retries.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


@dataclass
class TestExecutionConfig:
    """Configuration for controlled test execution in isolated subprocess."""
    __test__ = False
    command: List[str]
    working_dir: Path
    timeout_seconds: float = 30.0
    env_overrides: Dict[str, str] = field(default_factory=dict)
    strip_sensitive_env: bool = True
    max_retries: int = 3


@dataclass
class TestResult:
    """Execution telemetry and diagnostics for a test run."""
    __test__ = False
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    passed: bool = False
    failed_tests: List[str] = field(default_factory=list)
    error_summary: str = ""
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RetrySession:
    """Tracks state and results across bounded retry attempts."""
    max_attempts: int
    attempts_made: int = 0
    results: List[TestResult] = field(default_factory=list)
    resolved: bool = False
    final_diagnosis: str = ""
