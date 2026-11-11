"""
Security policy engine for evaluating shell commands prior to execution.
"""
import re
import shlex
from pathlib import Path
from typing import List, Pattern, Set

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
        # Windows destructive commands and download cradles
        re.compile(r"\b(del|erase)\s+.*(/[sS]|/[qQ]|\*|[A-Za-z]:\\)", re.IGNORECASE),
        re.compile(r"\b(rmdir|rd)\s+.*(/[sS]|/[qQ])", re.IGNORECASE),
        re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
        re.compile(r"\breg\s+(delete|add)\b", re.IGNORECASE),
        re.compile(r"\bcertutil\s+(-urlcache|-decode)\b", re.IGNORECASE),
        re.compile(r"\b(powershell|pwsh)\b.*(-enc|-encodedcommand|-e\b|invoke-webrequest|iwr|downloadstring)", re.IGNORECASE),
        re.compile(r"\bbitsadmin\s+/transfer\b", re.IGNORECASE),
    ]

    SENSITIVE_TARGET_PATTERNS: List[Pattern] = [
        re.compile(
            r"(\.env|\.git/config|\.netrc|\.aws/|id_rsa|id_ecdsa|id_ed25519|\.ssh/|"
            r"/etc/shadow|/etc/master\.passwd|secrets?\.(json|yaml|yml)|credentials?\.(json|yaml|yml)|"
            r"\.npmrc|\.pypirc|production\.key|\.key$|\.pem$|"
            r"\bSAM\b|\bSYSTEM\b|\bSECURITY\b|\bntds\.dit\b)",
            re.IGNORECASE,
        ),
    ]

    SAFE_COMMAND_PREFIXES: List[str] = [
        "ls",
        "dir",
        "git status",
        "git diff",
        "git log",
        "pwd",
        "whoami",
        "which",
        "where",
        "pytest",
        "python -m pytest",
        "python --version",
        "brahmastra",
    ]

    SAFE_EXECUTABLES: Set[str] = {
        "ls",
        "dir",
        "pwd",
        "whoami",
        "which",
        "where",
        "where.exe",
        "pytest",
        "brahmastra",
    }

    SAFE_GIT_SUBCOMMANDS: Set[str] = {
        "status",
        "diff",
        "log",
        "branch",
    }

    UNSAFE_SHELL_METACHARS: Pattern = re.compile(r"[\$`\n\r><|&;(){}\!%^]")

    @classmethod
    def evaluate(cls, command: str, working_dir: Path, explanation: str = "") -> ShellCommandAction:
        """
        Analyzes a shell command and determines its risk level.
        Enforces token-based allowlisting, exact executable matching, and disqualifies
        any commands containing shell operators, substitution, redirection, or compound logic (BRAH-SEC-003).
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

        # 1b. Check for sensitive file inspection/disclosure targets (raw & quote-normalized)
        normalized_cmd = re.sub(r"[\"'\\]", "", cleaned_cmd)
        for pattern in cls.SENSITIVE_TARGET_PATTERNS:
            if pattern.search(cleaned_cmd) or pattern.search(normalized_cmd):
                return ShellCommandAction(
                    command=cleaned_cmd,
                    explanation=explanation or "Potentially sensitive file disclosure or credential access target detected.",
                    working_dir=working_dir,
                    risk_level=CommandRiskLevel.DANGEROUS,
                    requires_explicit_override=True,
                )

        # 1c. Check for shell metacharacters, substitutions, compound operators, and newlines
        if cls.UNSAFE_SHELL_METACHARS.search(cleaned_cmd):
            return ShellCommandAction(
                command=cleaned_cmd,
                explanation=explanation or "Shell operators, substitutions, newlines, or compound commands detected.",
                working_dir=working_dir,
                risk_level=CommandRiskLevel.DANGEROUS,
                requires_explicit_override=True,
            )

        # 1d. Filesystem & symlink resolution check via shlex parsing
        try:
            tokens = shlex.split(cleaned_cmd)
        except ValueError:
            return ShellCommandAction(
                command=cleaned_cmd,
                explanation=explanation or "Malformed shell command with unbalanced quotes.",
                working_dir=working_dir,
                risk_level=CommandRiskLevel.DANGEROUS,
                requires_explicit_override=True,
            )

        if not tokens:
            return ShellCommandAction(
                command=cleaned_cmd,
                explanation="Empty command.",
                working_dir=working_dir,
                risk_level=CommandRiskLevel.SAFE_READ,
                requires_explicit_override=False,
            )

        # Inspect all argument tokens for sensitive targets and symlink escapes
        for token in tokens[1:]:
            if token.startswith("-"):
                continue
            target_path = Path(token) if Path(token).is_absolute() else (working_dir / token)
            try:
                if target_path.is_symlink() or target_path.exists():
                    canonical = target_path.resolve()
                    for pattern in cls.SENSITIVE_TARGET_PATTERNS:
                        if pattern.search(canonical.name) or pattern.search(str(canonical)):
                            return ShellCommandAction(
                                command=cleaned_cmd,
                                explanation=explanation or f"Command target resolves to sensitive file '{canonical.name}'.",
                                working_dir=working_dir,
                                risk_level=CommandRiskLevel.DANGEROUS,
                                requires_explicit_override=True,
                            )
            except (OSError, PermissionError):
                pass

        # 2. Check for exact token allowlisting for SAFE_READ
        executable = tokens[0]
        is_safe = False

        if executable in cls.SAFE_EXECUTABLES:
            is_safe = True
        elif executable == "git" and len(tokens) > 1 and tokens[1] in cls.SAFE_GIT_SUBCOMMANDS:
            is_safe = True
        elif executable == "python":
            if tokens[1:] == ["--version"] or tokens[1:3] == ["-m", "pytest"]:
                is_safe = True

        if is_safe:
            return ShellCommandAction(
                command=cleaned_cmd,
                explanation=explanation or "Safe read-only or inspection command.",
                working_dir=working_dir,
                risk_level=CommandRiskLevel.SAFE_READ,
                requires_explicit_override=False,
            )

        # 3. Default to MODERATE (e.g. build commands, git commit, pip install, lsof)
        return ShellCommandAction(
            command=cleaned_cmd,
            explanation=explanation or "Command may modify files or environment.",
            working_dir=working_dir,
            risk_level=CommandRiskLevel.MODERATE,
            requires_explicit_override=False,
        )
