"""Base agent class."""

from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.config import Config

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager, MCPStatus, OperationResult
    from ai_rules.skills import SkillStatus


class Agent(ABC):
    """Base class for AI agent configuration managers."""

    def __init__(self, config_dir: Path, config: Config):
        self.config_dir = config_dir
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the agent."""
        pass

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Short identifier for the agent (e.g., 'claude', 'goose')."""
        pass

    @property
    @abstractmethod
    def config_file_name(self) -> str:
        """Config file name for the agent (e.g., 'settings.json', 'config.yaml')."""
        pass

    @property
    @abstractmethod
    def config_file_format(self) -> str:
        """Config file format ('json', 'yaml', or 'toml')."""
        pass

    @cached_property
    @abstractmethod
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of (target_path, source_path) tuples for symlinks.

        Returns:
            List of tuples where:
            - target_path: Where symlink should be created (e.g., ~/.CLAUDE.md)
            - source_path: What symlink should point to (e.g., repo/config/AGENTS.md)
        """
        pass

    def get_filtered_symlinks(self) -> list[tuple[Path, Path]]:
        """Get symlinks filtered by config exclusions."""
        return [
            (target, source)
            for target, source in self.symlinks
            if not self.config.is_excluded(str(target))
        ]

    def get_deprecated_symlinks(self) -> list[Path]:
        """Get list of deprecated symlink paths that should be cleaned up.

        Returns:
            List of paths that were previously used but are now deprecated.
            These will be removed during install if they point to our config files.
        """
        return []

    def get_mcp_manager(self) -> "MCPManager | None":
        """Return the agent-specific MCPManager, or None if MCP is unsupported."""
        return None

    def install_mcps(
        self, force: bool = False, dry_run: bool = False
    ) -> "tuple[OperationResult, str, list[str]]":
        """Install MCPs by delegating to the agent's MCPManager."""
        from ai_rules.mcp import OperationResult

        mgr = self.get_mcp_manager()
        if mgr is None:
            return (
                OperationResult.NOT_FOUND,
                "MCP management not supported for this agent",
                [],
            )
        return mgr.install_mcps(self.config_dir, self.config, force, dry_run)

    def uninstall_mcps(
        self, force: bool = False, dry_run: bool = False
    ) -> "tuple[OperationResult, str]":
        """Uninstall MCPs by delegating to the agent's MCPManager."""
        from ai_rules.mcp import OperationResult

        mgr = self.get_mcp_manager()
        if mgr is None:
            return (
                OperationResult.NOT_FOUND,
                "MCP management not supported for this agent",
            )
        return mgr.uninstall_mcps(force, dry_run)

    def get_mcp_status(self) -> "MCPStatus | None":
        """Return MCP status, or None if MCP is unsupported for this agent."""
        mgr = self.get_mcp_manager()
        if mgr is None:
            return None
        return mgr.get_status(self.config_dir, self.config)

    def get_skill_status(self) -> "SkillStatus | None":
        """Get status of agent skills.

        Returns:
            SkillStatus object, or None if agent doesn't support skills
        """
        return None
