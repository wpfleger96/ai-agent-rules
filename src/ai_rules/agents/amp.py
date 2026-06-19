"""Amp agent implementation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class AmpAgent(Agent):
    """Agent for Amp configuration."""

    name = "Amp"
    agent_id = "amp"
    config_file_name = "settings.json"
    config_file_format = "json"
    settings_symlink_target = Path("~/.config/amp/settings.json")
    instructions_target = "~/.config/amp/AGENTS.md"
    instructions_source = "AGENTS.md"
    skills_dir: ClassVar[Path | None] = Path("~/.config/agents/skills")

    @classmethod
    def is_supported_on_current_platform(cls) -> bool:
        from ai_rules.platform import Platform, is_platform

        return not is_platform(Platform.WINDOWS)

    def get_mcp_manager(self) -> MCPManager:
        from ai_rules.mcp import AmpMCPManager

        return AmpMCPManager()
