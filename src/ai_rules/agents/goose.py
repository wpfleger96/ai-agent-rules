"""Goose agent implementation."""

from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent
from ai_rules.platform import get_goose_config_dir

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class GooseAgent(Agent):
    """Agent for Goose configuration."""

    name = "Goose"
    agent_id = "goose"
    config_file_name = "config.yaml"
    config_file_format = "yaml"
    preserved_fields = ["extensions"]

    @property
    def settings_symlink_target(self) -> Path:
        # Resolved at runtime: the Goose config dir is platform-specific.
        return get_goose_config_dir() / "config.yaml"

    def _instruction_symlinks(self) -> list[tuple[Path, Path]]:
        return [
            (
                get_goose_config_dir() / ".goosehints",
                self.config_dir / "goose" / ".goosehints",
            )
        ]

    def get_mcp_manager(self) -> MCPManager:
        from ai_rules.mcp import GooseMCPManager

        return GooseMCPManager()
