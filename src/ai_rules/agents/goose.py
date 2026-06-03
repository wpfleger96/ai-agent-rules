"""Goose agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent
from ai_rules.platform import get_goose_config_dir

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

    @property
    def preserved_fields(self) -> list[str]:
        return ["extensions"]

    @property
    def settings_symlink_target(self) -> Path:
        return get_goose_config_dir() / "config.yaml"

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of all Goose symlinks."""
        result = []

        result.append(
            (
                get_goose_config_dir() / ".goosehints",
                self.config_dir / "goose" / ".goosehints",
            )
        )

        config_file = self.config_dir / "goose" / "config.yaml"
        if config_file.exists():
            target_file = self.config.get_settings_file_for_symlink(
                "goose", config_file, force=bool(self._effective_preserved_fields)
            )
            result.append((get_goose_config_dir() / "config.yaml", target_file))

        return result

    def get_mcp_manager(self) -> MCPManager:
        from ai_rules.mcp import GooseMCPManager

        return GooseMCPManager()
