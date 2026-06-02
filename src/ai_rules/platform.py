"""Platform detection and path helpers for Windows/Unix compatibility."""

import os
import sys

from pathlib import Path


def is_windows() -> bool:
    """Return True when running on native Windows (not WSL)."""
    return sys.platform == "win32"


def get_appdata_dir() -> Path:
    """Return %APPDATA% on Windows. Raises RuntimeError if unset."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA environment variable not set")
    return Path(appdata)


def get_uv_tools_dir() -> Path:
    """Return the platform-appropriate uv tools directory.

    Honors UV_TOOL_DIR env var if set (uv's official override).
    Windows default: %APPDATA%/uv/data/tools
    Unix default:    $XDG_DATA_HOME/uv/tools (fallback ~/.local/share/uv/tools)
    """
    override = os.environ.get("UV_TOOL_DIR")
    if override:
        return Path(override)
    if is_windows():
        return get_appdata_dir() / "uv" / "data" / "tools"
    data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(data_home) / "uv" / "tools"


def get_lib_path_fragment(python_version: str) -> str:
    """Return site-packages path fragment.

    Windows: Lib/site-packages
    Unix: lib/{python_version}/site-packages
    """
    if is_windows():
        return str(Path("Lib") / "site-packages")
    return str(Path("lib") / python_version / "site-packages")


def get_default_editor() -> str:
    """Return platform-appropriate default editor."""
    return "notepad" if is_windows() else "vi"


def get_goose_config_dir() -> Path:
    """Return Goose config directory.

    Windows: %APPDATA%/Block/goose/config
    Unix: ~/.config/goose (tilde path -- callers expand as needed)
    """
    if is_windows():
        return get_appdata_dir() / "Block" / "goose" / "config"
    return Path("~/.config/goose")


def get_statusline_config_dir() -> Path:
    """Return Statusline config directory.

    Windows: %APPDATA%/claude-statusline
    Unix: ~/.config/claude-statusline (tilde path -- callers expand as needed)
    """
    if is_windows():
        return get_appdata_dir() / "claude-statusline"
    return Path("~/.config/claude-statusline")
