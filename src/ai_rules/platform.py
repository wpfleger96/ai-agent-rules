"""Platform detection and path helpers for Windows/Unix compatibility."""

from __future__ import annotations

import os
import platform as _platform

from enum import Enum
from functools import lru_cache
from pathlib import Path


class Platform(Enum):
    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    WSL = "wsl"

    @property
    def display_name(self) -> str:
        return {
            Platform.MACOS: "macOS",
            Platform.LINUX: "Linux",
            Platform.WINDOWS: "Windows",
            Platform.WSL: "WSL",
        }[self]

    @property
    def is_unix_like(self) -> bool:
        return self in (Platform.MACOS, Platform.LINUX, Platform.WSL)


@lru_cache(maxsize=1)
def detect_platform() -> Platform:
    system = _platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    if system == "windows":
        return Platform.WINDOWS
    if system == "linux":
        release = _platform.uname().release.lower()
        if "microsoft" in release or os.environ.get("WSL_DISTRO_NAME"):
            return Platform.WSL
        return Platform.LINUX
    return Platform.LINUX


def is_platform(target: Platform) -> bool:
    return detect_platform() == target


def get_appdata_dir() -> Path:
    """Return %APPDATA% on Windows, falling back to the standard default if unset."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


def get_uv_tools_dir() -> Path:
    """Return the platform-appropriate uv tools directory.

    Honors UV_TOOL_DIR env var if set (uv's official override).
    Windows default: %APPDATA%/uv/data/tools
    Unix default:    $XDG_DATA_HOME/uv/tools (fallback ~/.local/share/uv/tools)
    """
    override = os.environ.get("UV_TOOL_DIR")
    if override:
        return Path(override)
    if is_platform(Platform.WINDOWS):
        return get_appdata_dir() / "uv" / "data" / "tools"
    data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(data_home) / "uv" / "tools"


def get_lib_path_fragment(python_version: str) -> str:
    """Return site-packages path fragment.

    Windows: Lib/site-packages
    Unix: lib/{python_version}/site-packages
    """
    if is_platform(Platform.WINDOWS):
        return str(Path("Lib") / "site-packages")
    return str(Path("lib") / python_version / "site-packages")


def get_default_editor() -> str:
    """Return platform-appropriate default editor."""
    return "notepad" if is_platform(Platform.WINDOWS) else "vi"


def get_goose_config_dir() -> Path:
    """Return Goose config directory.

    Windows: %APPDATA%/Block/goose/config
    Unix: ~/.config/goose (tilde path -- callers expand as needed)
    """
    if is_platform(Platform.WINDOWS):
        return get_appdata_dir() / "Block" / "goose" / "config"
    return Path("~/.config/goose")


def get_statusline_config_dir() -> Path:
    """Return Statusline config directory.

    Windows: %APPDATA%/claude-statusline
    Unix: ~/.config/claude-statusline (tilde path -- callers expand as needed)
    """
    if is_platform(Platform.WINDOWS):
        return get_appdata_dir() / "claude-statusline"
    return Path("~/.config/claude-statusline")
