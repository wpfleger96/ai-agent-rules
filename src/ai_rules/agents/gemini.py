"""Gemini CLI agent implementation."""

from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class GeminiAgent(Agent):
    """Agent for Gemini CLI configuration."""

    name = "Gemini CLI"
    agent_id = "gemini"
    config_file_name = "settings.json"
    config_file_format = "json"
    preserved_fields = ["ide"]
    settings_symlink_target = Path("~/.gemini/settings.json")
    instructions_target = "~/.gemini/GEMINI.md"
    instructions_source = "GEMINI.md"

    @property
    def copy_mode_targets(self) -> set[Path]:
        from ai_rules.platform import Platform, is_platform

        if is_platform(Platform.WINDOWS):
            return {self.settings_symlink_target.expanduser()}
        return set()

    def get_mcp_manager(self) -> MCPManager:
        from ai_rules.mcp import GeminiMCPManager

        return GeminiMCPManager()
