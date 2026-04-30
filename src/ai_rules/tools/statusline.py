"""Statusline tool configuration and install spec."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from ai_rules.bootstrap.installer import get_tool_version, is_command_available
from ai_rules.bootstrap.updater import ToolSpec
from ai_rules.tools.base import Tool


class StatuslineTool(Tool):
    """Manages claude-code-status-line config and install lifecycle."""

    name = "Statusline"
    tool_id = "statusline"
    config_file_name = "config.yaml"
    config_file_format = "yaml"

    INSTALL_SPEC: ToolSpec = ToolSpec(
        tool_id="statusline",
        package_name="claude-code-statusline",
        display_name="statusline",
        get_version=lambda: get_tool_version("claude-code-statusline"),
        is_installed=lambda: is_command_available("claude-statusline"),
        github_repo="wpfleger96/claude-code-status-line",
    )

    @property
    def install_spec(self) -> ToolSpec:
        return self.INSTALL_SPEC

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        config_file = self.config_dir / "statusline" / "config.yaml"
        if not config_file.exists():
            return []
        target_file = self.config.get_settings_file_for_symlink(
            "statusline", config_file, force=bool(self._effective_preserved_fields)
        )
        return [(Path("~/.config/claude-statusline/config.yaml"), target_file)]
