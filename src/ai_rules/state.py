"""State management for ai-agent-rules."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

_STATE_DIR_NAME = ".ai-agent-rules"
_LEGACY_STATE_DIR_NAME = ".ai-rules"


def get_state_dir() -> Path:
    """Get the state directory, migrating from legacy path if needed."""
    home = Path.home()
    new_dir = home / _STATE_DIR_NAME
    if new_dir.exists():
        return new_dir

    old_dir = home / _LEGACY_STATE_DIR_NAME
    if old_dir.exists():
        old_dir.rename(new_dir)
        return new_dir

    return new_dir


def _get_state_file() -> Path:
    """Get the state file path."""
    return get_state_dir() / "state.yaml"


def get_state() -> dict[str, Any]:
    """Load state from file."""
    state_file = _get_state_file()
    if not state_file.exists():
        return {}

    try:
        with state_file.open() as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    """Save state to file."""
    state_file = _get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=True)


def get_active_profile() -> str | None:
    """Get the currently active profile."""
    state = get_state()
    return state.get("active_profile")


def set_active_profile(profile: str) -> None:
    """Set the active profile."""
    state = get_state()
    state["active_profile"] = profile
    state["last_install"] = datetime.now(UTC).isoformat()
    _save_state(state)
