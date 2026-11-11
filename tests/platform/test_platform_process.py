"""
Platform-specific process management and child process termination tests.
"""
import sys
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from brahmastra.domain.execution.models import TestExecutionConfig
from brahmastra.domain.execution.test_runner import ControlledTestRunner, terminate_process_tree


def test_terminate_process_tree_posix():
    """Verify POSIX process tree termination uses killpg with SIGKILL."""
    if sys.platform == "win32":
        pytest.skip("POSIX process termination is not applicable on Windows")

    mock_proc = MagicMock()
    mock_proc.pid = 9999

    with patch("sys.platform", "darwin"), \
         patch("os.getpgid", return_value=9999, create=True) as mock_getpgid, \
         patch("os.killpg", create=True) as mock_killpg:
        terminate_process_tree(mock_proc)
        mock_getpgid.assert_called_once_with(9999)
        mock_killpg.assert_called_once_with(9999, signal.SIGKILL)


def test_terminate_process_tree_windows():
    """Verify Windows process tree termination uses taskkill /F /T /PID."""
    mock_proc = MagicMock()
    mock_proc.pid = 8888

    with patch("sys.platform", "win32"), \
         patch("subprocess.run") as mock_run:
        terminate_process_tree(mock_proc)
        mock_run.assert_called_once_with(
            ["taskkill", "/F", "/T", "/PID", "8888"],
            capture_output=True,
            check=False,
        )


def test_windows_creationflags_applied():
    """Verify CREATE_NEW_PROCESS_GROUP is passed on Windows."""
    with patch("sys.platform", "win32"), \
         patch("subprocess.Popen") as mock_popen:
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = ("ok", "")
        mock_instance.returncode = 0
        mock_popen.return_value = mock_instance

        config = TestExecutionConfig(
            command=["python", "--version"],
            working_dir=Path.cwd(),
            timeout_seconds=5.0,
        )
        ControlledTestRunner.run(config)
        kwargs = mock_popen.call_args[1]
        assert "creationflags" in kwargs
        assert kwargs["creationflags"] == 0x00000200


def test_posix_preexec_fn_applied():
    """Verify os.setsid is passed as preexec_fn on POSIX."""
    if sys.platform == "win32":
        pytest.skip("POSIX test")

    with patch("subprocess.Popen") as mock_popen:
        mock_instance = MagicMock()
        mock_instance.communicate.return_value = ("ok", "")
        mock_instance.returncode = 0
        mock_popen.return_value = mock_instance

        config = TestExecutionConfig(
            command=["python", "--version"],
            working_dir=Path.cwd(),
            timeout_seconds=5.0,
        )
        ControlledTestRunner.run(config)
        kwargs = mock_popen.call_args[1]
        assert kwargs.get("preexec_fn") is not None


def test_live_timeout_terminates_child_process(tmp_path):
    """Live test confirming timeout triggers process termination and does not hang."""
    # Command that sleeps for 10 seconds with a 0.5s timeout
    config = TestExecutionConfig(
        command=[sys.executable, "-c", "import time; time.sleep(10)"],
        working_dir=tmp_path,
        timeout_seconds=0.5,
    )
    result = ControlledTestRunner.run(config)
    assert result.timed_out is True
    assert result.passed is False
    assert result.duration_seconds < 3.0
