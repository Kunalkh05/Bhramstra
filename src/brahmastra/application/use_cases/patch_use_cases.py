"""
Application use cases for patch lifecycle management, diff review,
and shell command execution gating.
"""
from pathlib import Path
from typing import Optional

from brahmastra.domain.patch.command_policy import CommandPolicyEngine
from brahmastra.domain.patch.diff_engine import DiffEngine
from brahmastra.domain.patch.models import FilePatch, ShellCommandAction


def get_default_project_root() -> Path:
    """Returns current working directory as default project root."""
    return Path.cwd().resolve()


def propose_patch(
    target_path: Path,
    new_content: str,
    root_dir: Optional[Path] = None,
) -> FilePatch:
    """
    Validates path boundaries and generates a FilePatch with unified diff.
    """
    root = (root_dir or get_default_project_root()).resolve()
    return DiffEngine.create_patch(target_path=target_path, new_content=new_content, root_dir=root)


def apply_approved_patch(patch: FilePatch, backup: bool = True) -> Path:
    """
    Applies an approved patch atomically with backup creation.
    """
    return DiffEngine.apply_patch(patch=patch, backup=backup)


def rollback_patch_safely(patch: FilePatch) -> None:
    """
    Rolls back an applied patch.
    """
    DiffEngine.rollback_patch(patch)


def evaluate_command_for_approval(
    command: str,
    working_dir: Optional[Path] = None,
    explanation: str = "",
) -> ShellCommandAction:
    """
    Evaluates shell command risk and constructs an actionable proposal.
    """
    cwd = (working_dir or get_default_project_root()).resolve()
    return CommandPolicyEngine.evaluate(
        command=command,
        working_dir=cwd,
        explanation=explanation,
    )
