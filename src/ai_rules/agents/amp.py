"""Amp agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class AmpAgent(Agent):
    """Agent for Amp configuration."""

    @property
    def name(self) -> str:
        return "Amp"

    @property
    def agent_id(self) -> str:
        return "amp"

    @property
    def config_file_name(self) -> str:
        return "settings.json"

    @property
    def config_file_format(self) -> str:
        return "json"

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of all Amp symlinks."""
        result = []

        result.append(
            (
                Path("~/.config/amp/AGENTS.md"),
                self.config_dir / "amp" / "AGENTS.md",
            )
        )

        config_file = self.config_dir / "amp" / "settings.json"
        if config_file.exists():
            target_file = self.config.get_settings_file_for_symlink(
                "amp", config_file, force=bool(self.preserved_fields)
            )
            result.append((Path("~/.config/amp/settings.json"), target_file))

        return result

    def get_mcp_manager(self) -> "MCPManager":
        from ai_rules.mcp import AmpMCPManager

        return AmpMCPManager()
