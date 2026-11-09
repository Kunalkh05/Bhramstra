"""
Security policy engine for evaluating shell commands prior to execution.
"""
import re
from pathlib import Path
from typing import List, Pattern

from brahmastra.domain.patch.models import CommandRiskLevel, ShellCommandAction


class CommandPolicyEngine:
    """
    Evaluates shell commands for destructive patterns, privilege escalation,
    and dangerous system calls.
    """

    DANGEROUS_PATTERNS: List[Pattern] = [
        re.compile(r"\brm\s+(-[rfRF]{1,4}\s+)?(/|~|\*|\.\.)"),
        re.compile(r"\b(sudo|su)\b"),
        re.compile(r"\b(mkfs|fdisk|dd\s+if=)"),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # fork bomb
        re.compile(r"\b(curl|wget)\s+[^|]+\|\s*(sh|bash|zsh)"),   # remote script execution
        re.compile(r"\bchmod\s+(-[rR]\s+)?(777|a\+[rwx]{3})"),
        re.compile(r">\s*/dev/(sd|hd|nvme)"),
    ]

    SENSITIVE_TARGET_PATTERNS: List[Pattern] = [
        re.compile(r"(\.env|\.git/config|\.netrc|\.aws/|id_rsa|id_ecdsa|id_ed25519|\.ssh/|/etc/shadow|/etc/master\.passwd)"),
    ]

    SAFE_COMMAND_PREFIXES: List[str] = [
        "ls",
        "git status",
        "git diff",
        "git log",
        "pwd",
        "whoami",
        "which",
        "pytest",
        "python -m pytest",
        "python --version",
        "brahmastra",
    ]

    @classmethod
    def evaluate(cls, command: str, working_dir: Path, explanation: str = "") -> ShellCommandAction:
        """
        Analyzes a shell command and determines its risk level.
        """
        cleaned_cmd = command.strip()

        # 1. Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(cleaned_cmd):
                return ShellCommandAction(
                    command=cleaned_cmd,
                    explanation=explanation or "Dangerous command detected; may modify system or delete files.",
                    working_dir=working_dir,
                    risk_level=CommandRiskLevel.DANGEROUS,
                    requires_explicit_override=True,
                )

        # 1b. Check for sensitive file inspection/disclosure targets
        for pattern in cls.SENSITIVE_TARGET_PATTERNS:
            if pattern.search(cleaned_cmd):
                return ShellCommandAction(
                    command=cleaned_cmd,
                    explanation=explanation or "Potentially sensitive file disclosure or credential access target detected.",
                    working_dir=working_dir,
                    risk_level=CommandRiskLevel.DANGEROUS,
                    requires_explicit_override=True,
                )

        # 2. Check for known safe read-only prefixes
        is_safe = any(cleaned_cmd.startswith(prefix) for prefix in cls.SAFE_COMMAND_PREFIXES)
        if is_safe and not any(op in cleaned_cmd for op in [">", "|", "&&", ";"]):
            return ShellCommandAction(
                command=cleaned_cmd,
                explanation=explanation or "Safe read-only or inspection command.",
                working_dir=working_dir,
                risk_level=CommandRiskLevel.SAFE_READ,
                requires_explicit_override=False,
            )

        # 3. Default to MODERATE (e.g. build commands, git commit, pip install)
        return ShellCommandAction(
            command=cleaned_cmd,
            explanation=explanation or "Command may modify files or environment.",
            working_dir=working_dir,
            risk_level=CommandRiskLevel.MODERATE,
            requires_explicit_override=False,
        )
