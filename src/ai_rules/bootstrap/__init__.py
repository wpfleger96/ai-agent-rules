"""Bootstrap module for system-wide installation and upgrade functionality.

This module provides utilities for:
- Installing tools via uv (PyPI-based)
- Checking for and applying updates from PyPI

Designed to be self-contained and easily extractable for use in other projects.
"""

from .installer import (
    UV_NOT_FOUND_ERROR,
    ToolSource,
    ensure_recall_installed,
    ensure_statusline_installed,
    get_effective_install_source,
    get_tool_config_dir,
    get_tool_source,
    get_tool_version,
    install_tool,
    is_command_available,
    uninstall_tool,
)
from .updater import (
    ToolSpec,
    UpdateInfo,
    check_index_updates,
    check_tool_updates,
    get_tool_by_id,
    get_updatable_tools,
    perform_tool_upgrade,
)
from .version import is_newer, parse_version

__all__ = [
    "is_newer",
    "parse_version",
    "UV_NOT_FOUND_ERROR",
    "ToolSource",
    "ensure_recall_installed",
    "ensure_statusline_installed",
    "get_effective_install_source",
    "get_tool_config_dir",
    "get_tool_source",
    "get_tool_version",
    "install_tool",
    "is_command_available",
    "uninstall_tool",
    "ToolSpec",
    "UpdateInfo",
    "check_index_updates",
    "check_tool_updates",
    "get_tool_by_id",
    "get_updatable_tools",
    "perform_tool_upgrade",
]
