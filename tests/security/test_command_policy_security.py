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
