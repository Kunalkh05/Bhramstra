"""
Unit tests for diff generation, path boundary validation, and rollback.
"""
from pathlib import Path
import pytest

from brahmastra.domain.patch.diff_engine import DiffEngine
from brahmastra.domain.patch.models import PatchStatus


def test_generate_unified_diff():
    """Verify unified diff calculation with line additions and removals."""
    orig = "def foo():\n    return 1\n"
    new = "def foo():\n    return 2\n    # new comment\n"

    diff_text, added, removed = DiffEngine.generate_unified_diff(orig, new, "test.py")
    assert "--- a/test.py" in diff_text
    assert "+++ b/test.py" in diff_text
    assert "-    return 1" in diff_text
    assert "+    return 2" in diff_text
    assert "+    # new comment" in diff_text
    assert added == 2
    assert removed == 1


def test_validate_safe_path_success(tmp_path: Path):
    """Verify safe paths within root dir are accepted."""
    sub_dir = tmp_path / "src" / "module.py"
    resolved = DiffEngine.validate_safe_path(Path("src/module.py"), root_dir=tmp_path)
    assert resolved == sub_dir.resolve()


def test_validate_safe_path_traversal_blocked(tmp_path: Path):
    """Verify path traversal (escaping root) raises PermissionError."""
    with pytest.raises(PermissionError, match="Path traversal detected"):
        DiffEngine.validate_safe_path(Path("../outside.py"), root_dir=tmp_path)

    with pytest.raises(PermissionError, match="Path traversal detected"):
        DiffEngine.validate_safe_path(Path("/etc/passwd"), root_dir=tmp_path)


def test_validate_safe_path_restricted_dirs_blocked(tmp_path: Path):
    """Verify modifying .git or .brahmastra raises PermissionError."""
    with pytest.raises(PermissionError, match="protected directory"):
        DiffEngine.validate_safe_path(Path(".git/config"), root_dir=tmp_path)

    with pytest.raises(PermissionError, match="protected directory"):
        DiffEngine.validate_safe_path(Path(".brahmastra/brahmastra.db"), root_dir=tmp_path)


def test_validate_safe_path_restricted_extensions_blocked(tmp_path: Path):
    """Verify modifying .env or .db raises PermissionError."""
    with pytest.raises(PermissionError, match="protected configuration"):
        DiffEngine.validate_safe_path(Path(".env"), root_dir=tmp_path)

    with pytest.raises(PermissionError, match="protected configuration"):
        DiffEngine.validate_safe_path(Path("secrets.key"), root_dir=tmp_path)


def test_apply_patch_and_rollback_existing_file(tmp_path: Path):
    """Verify applying patch creates backup and rollback restores original content."""
    target_file = tmp_path / "app.py"
    target_file.write_text("v1 = 100\n", encoding="utf-8")

    patch = DiffEngine.create_patch(
        target_path=target_file,
        new_content="v1 = 200\nv2 = 300\n",
        root_dir=tmp_path,
    )
    assert patch.status == PatchStatus.PENDING

    # Apply patch
    DiffEngine.apply_patch(patch, backup=True)
    assert patch.status == PatchStatus.APPLIED
    assert target_file.read_text(encoding="utf-8") == "v1 = 200\nv2 = 300\n"
    assert patch.backup_path is not None
    assert patch.backup_path.exists()

    # Rollback
    DiffEngine.rollback_patch(patch)
    assert patch.status == PatchStatus.ROLLED_BACK
    assert target_file.read_text(encoding="utf-8") == "v1 = 100\n"


def test_apply_patch_and_rollback_new_file(tmp_path: Path):
    """Verify creating a new file via patch and rolling back removes the file."""
    new_file = tmp_path / "new_module.py"
    assert not new_file.exists()

    patch = DiffEngine.create_patch(
        target_path=new_file,
        new_content="def new_func(): pass\n",
        root_dir=tmp_path,
    )

    DiffEngine.apply_patch(patch, backup=True)
    assert new_file.exists()
    assert new_file.read_text(encoding="utf-8") == "def new_func(): pass\n"

    DiffEngine.rollback_patch(patch)
    assert not new_file.exists()
