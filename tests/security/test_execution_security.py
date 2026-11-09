"""
Security tests for test execution runner (BRAH-SEC-004).
Verifies that pytest flag injection and path traversal via the 'target' parameter
are rejected with ValueError.
"""
from pathlib import Path
import pytest

from brahmastra.application.use_cases.execution_use_cases import run_project_tests


def test_flag_injection_rejected():
    """Verify that options/flags starting with '-' in target are blocked."""
    with pytest.raises(ValueError, match="Invalid test target"):
        run_project_tests(target="--override-ini=addopts=--capture=no")

    with pytest.raises(ValueError, match="Invalid test target"):
        run_project_tests(target="-o")

    with pytest.raises(ValueError, match="Invalid test target"):
        run_project_tests(target="--help")


def test_path_traversal_target_rejected(tmp_path: Path):
    """Verify that path traversal targets escaping working_dir are blocked."""
    with pytest.raises(ValueError, match="Invalid test target"):
        run_project_tests(target="../../etc/passwd", working_dir=tmp_path)
