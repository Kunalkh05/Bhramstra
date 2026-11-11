"""
Platform-specific tests for configuration and storage directories across macOS, Linux, and Windows.
"""
import platform
import stat
from pathlib import Path
import pytest

from brahmastra.infrastructure.config import (
    get_storage_dir,
    get_db_path,
    get_state_file_path,
    get_user_data_dir,
    set_active_org_name,
    get_active_org_name,
)


def test_no_hardcoded_developer_paths():
    """Verify that no hardcoded developer paths exist in the module constants."""
    import brahmastra.infrastructure.config as config_mod
    assert not hasattr(config_mod, "DEFAULT_STATIC_PROJECT_DIR")
    for key, val in vars(config_mod).items():
        if not key.startswith("__") and isinstance(val, (str, Path)):
            assert "kunalkhande" not in str(val).lower()


def test_macos_user_data_directory(monkeypatch):
    """Verify macOS standard user data directory resolution."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    fake_home = Path("/Users/testuser")
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("BRAHMASTRA_HOME", raising=False)

    data_dir = get_user_data_dir()
    assert data_dir == fake_home / "Library" / "Application Support" / "brahmastra"


def test_linux_xdg_data_directory_custom(monkeypatch):
    """Verify Linux respects XDG_DATA_HOME when set."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/custom/xdg/data")
    monkeypatch.delenv("BRAHMASTRA_HOME", raising=False)

    data_dir = get_user_data_dir()
    assert data_dir == Path("/custom/xdg/data/brahmastra")


def test_linux_xdg_data_directory_default(monkeypatch):
    """Verify Linux defaults to ~/.local/share/brahmastra when XDG_DATA_HOME is unset."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    fake_home = Path("/home/testuser")
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("BRAHMASTRA_HOME", raising=False)

    data_dir = get_user_data_dir()
    assert data_dir == fake_home / ".local" / "share" / "brahmastra"


def test_windows_localappdata_directory(monkeypatch):
    """Verify Windows standard LOCALAPPDATA directory resolution."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", "/custom/win/localappdata")
    monkeypatch.delenv("BRAHMASTRA_HOME", raising=False)

    data_dir = get_user_data_dir()
    assert data_dir == Path("/custom/win/localappdata/brahmastra")


def test_windows_localappdata_fallback_when_env_missing(monkeypatch):
    """Verify Windows falls back cleanly to ~/AppData/Local when LOCALAPPDATA is unset."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    fake_home = Path(r"C:\Users\testuser")
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("BRAHMASTRA_HOME", raising=False)

    data_dir = get_user_data_dir()
    assert data_dir == fake_home / "AppData" / "Local" / "brahmastra"


def test_storage_dir_with_spaces_and_unicode(tmp_path, monkeypatch):
    """Verify paths containing spaces and Unicode characters function properly."""
    unicode_dir = tmp_path / "Projet d'IA — Über Developer 🚀"
    monkeypatch.setenv("BRAHMASTRA_HOME", str(unicode_dir))

    storage_dir = get_storage_dir()
    assert storage_dir == unicode_dir
    assert storage_dir.exists()

    db_path = get_db_path()
    assert db_path == unicode_dir / "brahmastra.db"

    state_path = get_state_file_path()
    assert state_path == unicode_dir / "state.json"

    set_active_org_name("unicode-org-⚡")
    assert get_active_org_name() == "unicode-org-⚡"


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX file permission test")
def test_posix_secure_permissions(tmp_path, monkeypatch):
    """Verify secure POSIX permissions (0700 dir, 0600 file) on state.json and storage dir."""
    secure_dir = tmp_path / "secure_store"
    monkeypatch.setenv("BRAHMASTRA_HOME", str(secure_dir))

    storage_dir = get_storage_dir()
    # Directory should have 0700 permissions
    dir_mode = stat.S_IMODE(storage_dir.stat().st_mode)
    assert dir_mode == 0o700

    set_active_org_name("secure-org")
    state_file = get_state_file_path()
    assert state_file.exists()
    file_mode = stat.S_IMODE(state_file.stat().st_mode)
    assert file_mode == 0o600
