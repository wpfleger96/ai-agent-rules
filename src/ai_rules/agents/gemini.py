"""Gemini CLI agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class GeminiAgent(Agent):
    """Agent for Gemini CLI configuration."""

    @property
    def name(self) -> str:
        return "Gemini CLI"

    @property
    def agent_id(self) -> str:
        return "gemini"

    @property
    def config_file_name(self) -> str:
        return "settings.json"

    @property
    def config_file_format(self) -> str:
        return "json"

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of all Gemini CLI symlinks."""
        result = []

        result.append(
            (
                Path("~/.gemini/GEMINI.md"),
                self.config_dir / "gemini" / "GEMINI.md",
            )
        )

        config_file = self.config_dir / "gemini" / "settings.json"
        if config_file.exists():
            target_file = self.config.get_settings_file_for_symlink(
                "gemini", config_file
            )
            result.append((Path("~/.gemini/settings.json"), target_file))

        return result

    def get_mcp_manager(self) -> "MCPManager":
        from ai_rules.mcp import GeminiMCPManager

        return GeminiMCPManager()
