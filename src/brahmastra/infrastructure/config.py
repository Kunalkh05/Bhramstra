"""
Central configuration and storage path management.
"""

import json
import os
from pathlib import Path
from typing import Optional

# Default project storage root is the project's local .brahmastra directory
DEFAULT_PROJECT_DIR = Path("/Users/kunalkhande/Project /Bhramstra")
DEFAULT_STORAGE_DIR = DEFAULT_PROJECT_DIR / ".brahmastra"


def get_storage_dir() -> Path:
    """
    Get the configured storage directory.
    Uses BRAHMASTRA_HOME env var if set, otherwise defaults to project .brahmastra dir.
    """
    custom_home = os.environ.get("BRAHMASTRA_HOME")
    storage_dir = Path(custom_home) if custom_home else DEFAULT_STORAGE_DIR
    storage_dir.mkdir(parents=True, exist_ok=True)
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
    """Write the currently active organization name to local state."""
    state_file = get_state_file_path()
    data = {}
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["active_organization"] = name
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
