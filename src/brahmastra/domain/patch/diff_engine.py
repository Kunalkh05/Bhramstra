"""
Unified diff generation, path boundary validation, atomic patch application,
and rollback mechanisms.
"""
import difflib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional, Set, Tuple

from brahmastra.domain.patch.models import FilePatch, PatchStatus


class DiffEngine:
    """Engine for generating and applying unified diffs safely."""

    RESTRICTED_DIRECTORIES: Set[str] = {
        ".git",
        ".brahmastra",
        "__pycache__",
    }

    RESTRICTED_EXTENSIONS: Set[str] = {
        ".env",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".key",
    }

    @staticmethod
    def generate_unified_diff(
        original_content: str,
        new_content: str,
        filepath: str = "file",
    ) -> Tuple[str, int, int]:
        """
        Generates standard unified diff with line counts.
        Returns: (diff_text, lines_added, lines_removed)
        """
        orig_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{filepath}",
            tofile=f"b/{filepath}",
            lineterm="",
        )

        diff_lines = list(diff)
        diff_text = "".join(diff_lines)

        lines_added = 0
        lines_removed = 0
        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        return diff_text, lines_added, lines_removed

    @classmethod
    def validate_safe_path(cls, target_path: Path, root_dir: Path) -> Path:
        """
        Validates target path is strictly within the allowed root directory
        and does not target restricted paths or perform path traversal.
        """
        resolved_root = root_dir.resolve()
        resolved_target = (resolved_root / target_path).resolve() if not target_path.is_absolute() else target_path.resolve()

        # 1. Path traversal boundary check
        try:
            rel_path = resolved_target.relative_to(resolved_root)
        except ValueError:
            raise PermissionError(
                f"Path traversal detected: {target_path} resolves outside project root {resolved_root}"
            )

        # 2. Restricted directory check (.git, .brahmastra, etc.)
        for part in rel_path.parts:
            if part in cls.RESTRICTED_DIRECTORIES:
                raise PermissionError(
                    f"Modification of protected directory '{part}' is strictly forbidden."
                )

        # 3. Restricted extension / secret file check
        if resolved_target.name.startswith(".env") or resolved_target.suffix in cls.RESTRICTED_EXTENSIONS:
            raise PermissionError(
                f"Modification of protected configuration/secret file '{resolved_target.name}' is forbidden."
            )

        return resolved_target

    @classmethod
    def create_patch(
        cls,
        target_path: Path,
        new_content: str,
        root_dir: Path,
    ) -> FilePatch:
        """
        Validates path safety and creates a FilePatch object.
        """
        safe_path = cls.validate_safe_path(target_path, root_dir)
        original_content = ""
        if safe_path.exists():
            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                original_content = f.read()

        rel_path = str(safe_path.relative_to(root_dir.resolve()))
        diff_text, added, removed = cls.generate_unified_diff(
            original_content, new_content, rel_path
        )

        return FilePatch(
            target_path=safe_path,
            original_content=original_content,
            new_content=new_content,
            unified_diff=diff_text,
            lines_added=added,
            lines_removed=removed,
            status=PatchStatus.PENDING,
        )

    @classmethod
    def apply_patch(cls, patch: FilePatch, backup: bool = True) -> Path:
        """
        Applies a patch atomically with rollback backup creation.
        """
        target = patch.target_path
        backup_path: Optional[Path] = None

        # Create parent directory if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        # Create temporary backup if original file exists
        if backup and target.exists():
            backup_fd, tmp_backup = tempfile.mkstemp(prefix="brahmastra_patch_bak_")
            os.close(backup_fd)
            backup_path = Path(tmp_backup)
            shutil.copy2(target, backup_path)
            patch.backup_path = backup_path

        # Atomic write: write to temp file first, then replace
        temp_target = target.with_suffix(f"{target.suffix}.tmp_patch")
        with open(temp_target, "w", encoding="utf-8") as f:
            f.write(patch.new_content)

        temp_target.replace(target)
        patch.status = PatchStatus.APPLIED
        return target

    @classmethod
    def rollback_patch(cls, patch: FilePatch) -> None:
        """
        Reverts an applied patch using the backup file or original content.
        """
        if patch.status != PatchStatus.APPLIED:
            return

        target = patch.target_path
        if patch.backup_path and patch.backup_path.exists():
            shutil.copy2(patch.backup_path, target)
            patch.backup_path.unlink(missing_ok=True)
        elif not patch.original_content:
            # File did not exist prior to patch; remove it
            target.unlink(missing_ok=True)
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(patch.original_content)

        patch.status = PatchStatus.ROLLED_BACK
