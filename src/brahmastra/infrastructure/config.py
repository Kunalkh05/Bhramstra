"""
Central configuration and storage path management.
Cross-platform support for macOS, Linux, and Windows with secure permissions.
"""

import json
import os
import platform
from pathlib import Path
from typing import Optional


def get_user_data_dir() -> Path:
    """
    Resolve the OS-standard user data directory for BRAHMASTRA.
    - macOS: ~/Library/Application Support/brahmastra
    - Linux / POSIX: $XDG_DATA_HOME/brahmastra or ~/.local/share/brahmastra
    - Windows: %LOCALAPPDATA%\\brahmastra or ~/AppData/Local/brahmastra
    """
    sys_name = platform.system()
    if sys_name == "Windows":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "brahmastra"
        return Path.home() / "AppData" / "Local" / "brahmastra"
    elif sys_name == "Darwin":
        return Path.home() / "Library" / "Application Support" / "brahmastra"
    else:
        # Linux and other POSIX compliant systems (XDG Base Directory Specification)
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / "brahmastra"
        return Path.home() / ".local" / "share" / "brahmastra"


def secure_posix_permissions(path: Path, is_dir: bool = False) -> None:
    """Apply strict 0700 (directory) or 0600 (file) permissions on POSIX systems."""
    if os.name == "posix":
        try:
            mode = 0o700 if is_dir else 0o600
            os.chmod(path, mode)
        except OSError:
            pass


def resolve_project_root() -> Optional[Path]:
    """Dynamically resolve the project root directory from cwd or its ancestors."""
    try:
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
                return parent
    except Exception:
        pass
    return None


def get_storage_dir() -> Path:
    """
    Get the configured storage directory.
    Priority order:
    1. BRAHMASTRA_HOME environment variable (explicit override)
    2. Local workspace directory (.brahmastra) if inside a project
    3. OS-standard user application data directory
    """
    custom_home = os.environ.get("BRAHMASTRA_HOME")
    if custom_home:
        storage_dir = Path(custom_home)
    else:
        project_root = resolve_project_root()
        if project_root is not None:
            storage_dir = project_root / ".brahmastra"
        else:
            storage_dir = get_user_data_dir()

    storage_dir.mkdir(parents=True, exist_ok=True)
    secure_posix_permissions(storage_dir, is_dir=True)
    return storage_dir


def get_db_path() -> Path:
    """Get the SQLite database file path."""
    return get_storage_dir() / "brahmastra.db"


def get_state_file_path() -> Path:
    """Get the profile/state JSON file path."""
    return get_storage_dir() / "state.json"


def get_active_org_name() -> Optional[str]:
    """Read the currently active organization name from local state."""
    state_file = get_state_file_path()
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return data.get("active_organization")
    except Exception:
        return None


def set_active_org_name(name: Optional[str]) -> None:
    """Write the currently active organization name to local state with secure permissions."""
    state_file = get_state_file_path()
    data = {}
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["active_organization"] = name
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    secure_posix_permissions(state_file, is_dir=False)
