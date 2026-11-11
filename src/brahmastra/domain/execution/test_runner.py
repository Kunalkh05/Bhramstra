"""
Controlled subprocess test runner with environment sanitization, process group
timeout management, and test failure parsing.
"""
import os
import re
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set

from brahmastra.domain.execution.models import TestExecutionConfig, TestResult


def terminate_process_tree(proc: subprocess.Popen) -> None:
    """
    Terminates the subprocess and all descendant child processes cleanly.
    - On Windows: Uses taskkill /F /T /PID to recursively kill process tree.
    - On POSIX: Uses os.killpg to signal the entire process group with SIGKILL.
    """
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        try:
            if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class ControlledTestRunner:
    """Executes tests under strict timeouts, isolated environments, and failure monitoring."""

    PRESERVED_SYSTEM_ENV: Set[str] = {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "TERM",
        "SYSTEMROOT",
        "COMSPEC",
    }

    SENSITIVE_KEY_PATTERNS: List[re.Pattern] = [
        re.compile(r".*(?:KEY|SECRET|TOKEN|PASS|CREDENTIAL|AUTH).*", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_environment(
        cls,
        base_env: Dict[str, str],
        strip_sensitive: bool = True,
        overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Creates an isolated environment by stripping sensitive keys unless explicitly preserved.
        """
        sanitized: Dict[str, str] = {}
        for k, v in base_env.items():
            if not strip_sensitive or k in cls.PRESERVED_SYSTEM_ENV:
                sanitized[k] = v
                continue

            # Check if variable matches sensitive regex patterns
            is_sensitive = any(pattern.match(k) for pattern in cls.SENSITIVE_KEY_PATTERNS)
            if not is_sensitive:
                sanitized[k] = v

        # Enforce deterministic Python behavior
        sanitized["PYTHONUNBUFFERED"] = "1"
        sanitized["PYTHONDONTWRITEBYTECODE"] = "1"
        sanitized["BRAHMASTRA_VAULT"] = "memory"  # Prevent tests touching real macOS Keychain

        if overrides:
            sanitized.update(overrides)

        return sanitized

    @classmethod
    def run(cls, config: TestExecutionConfig) -> TestResult:
        """
        Executes test suite with strict process-group timeout and output capture.
        """
        sanitized_env = cls.sanitize_environment(
            base_env=dict(os.environ),
            strip_sensitive=config.strip_sensitive_env,
            overrides=config.env_overrides,
        )

        start_time = time.perf_counter()
        timed_out = False
        stdout_str = ""
        stderr_str = ""
        exit_code = -1

        try:
            popen_kwargs: Dict[str, Any] = {
                "cwd": str(config.working_dir),
                "env": sanitized_env,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            elif hasattr(os, "setsid"):
                popen_kwargs["preexec_fn"] = os.setsid

            proc = subprocess.Popen(config.command, **popen_kwargs)
            stdout_str, stderr_str = proc.communicate(timeout=config.timeout_seconds)
            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_tree(proc)
            stdout_str, stderr_str = proc.communicate()
            exit_code = -signal.SIGKILL if hasattr(signal, "SIGKILL") else -1

        except Exception as ex:
            if "proc" in locals():
                terminate_process_tree(proc)
            stderr_str = f"Execution failed: {str(ex)}"
            exit_code = 1

        duration = time.perf_counter() - start_time
        passed = (exit_code == 0) and not timed_out
        failed_tests = cls._parse_failed_tests(stdout_str + "\n" + stderr_str)
        error_summary = cls._extract_error_summary(stdout_str + "\n" + stderr_str, timed_out)

        return TestResult(
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_seconds=round(duration, 3),
            timed_out=timed_out,
            passed=passed,
            failed_tests=failed_tests,
            error_summary=error_summary,
        )

    @classmethod
    def _parse_failed_tests(cls, output: str) -> List[str]:
        """Parses individual failed test names from pytest output."""
        failed: List[str] = []
        pattern = re.compile(r"^FAILED\s+([^\s]+)", re.MULTILINE)
        for match in pattern.finditer(output):
            failed.append(match.group(1))
        return failed

    @classmethod
    def _extract_error_summary(cls, output: str, timed_out: bool) -> str:
        """Extracts brief summary of failures for diagnosis."""
        if timed_out:
            return "Test execution exceeded strict process timeout and was killed."

        # Search for pytest summary lines (e.g., '=== FAILURES ===' or 'short test summary info')
        lines = output.splitlines()
        summary_lines = []
        capturing = False
        for line in lines:
            if "short test summary info" in line:
                capturing = True
                continue
            if capturing and line.startswith("==="):
                break
            if capturing and line.strip():
                summary_lines.append(line.strip())

        if summary_lines:
            return "\n".join(summary_lines[:5])
        return "Tests completed without summary."
