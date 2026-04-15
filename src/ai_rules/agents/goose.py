"""Goose agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class GooseAgent(Agent):
    """Agent for Goose configuration."""

    @property
    def name(self) -> str:
        return "Goose"

    @property
    def agent_id(self) -> str:
        return "goose"

    @property
    def config_file_name(self) -> str:
        return "config.yaml"

    @property
    def config_file_format(self) -> str:
        return "yaml"

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of all Goose symlinks."""
        result = []

        result.append(
            (
                Path("~/.config/goose/.goosehints"),
                self.config_dir / "goose" / ".goosehints",
            )
        )

        config_file = self.config_dir / "goose" / "config.yaml"
        if config_file.exists():
            target_file = self.config.get_settings_file_for_symlink(
                "goose", config_file
            )
            result.append((Path("~/.config/goose/config.yaml"), target_file))

        return result

    def get_mcp_manager(self) -> "MCPManager":
        from ai_rules.mcp import GooseMCPManager

        return GooseMCPManager()
