"""
Domain models for patches, diffs, and command execution approval.
"""
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class PatchStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"


class CommandStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class CommandRiskLevel(str, Enum):
    SAFE_READ = "SAFE_READ"
    MODERATE = "MODERATE"
    DANGEROUS = "DANGEROUS"


@dataclass
class FilePatch:
    """Represents a proposed file modification with a unified diff."""
    target_path: Path
    original_content: str
    new_content: str
    unified_diff: str
    lines_added: int = 0
    lines_removed: int = 0
    status: PatchStatus = PatchStatus.PENDING
    backup_path: Optional[Path] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ShellCommandAction:
    """Represents a proposed shell command requiring explicit human review."""
    command: str
    explanation: str
    working_dir: Path
    risk_level: CommandRiskLevel
    status: CommandStatus = CommandStatus.PENDING
    requires_explicit_override: bool = False
