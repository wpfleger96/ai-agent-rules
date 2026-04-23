"""Base agent class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from ai_rules.targets.base import ConfigTarget

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager, MCPStatus, OperationResult
    from ai_rules.skills import SkillStatus


class Agent(ConfigTarget):
    """Base class for AI agent configuration managers."""

    @property
    def target_id(self) -> str:
        return self.agent_id

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Short identifier for the agent (e.g., 'claude', 'goose')."""
        pass

    def get_mcp_manager(self) -> MCPManager | None:
        """Return the agent-specific MCPManager, or None if MCP is unsupported."""
        return None

    def install_mcps(
        self, force: bool = False, dry_run: bool = False
    ) -> tuple[OperationResult, str, list[str]]:
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
    ) -> tuple[OperationResult, str]:
        """Uninstall MCPs by delegating to the agent's MCPManager."""
        from ai_rules.mcp import OperationResult

        mgr = self.get_mcp_manager()
        if mgr is None:
            return (
                OperationResult.NOT_FOUND,
                "MCP management not supported for this agent",
            )
        return mgr.uninstall_mcps(force, dry_run)

    def get_mcp_status(self) -> MCPStatus | None:
        """Return MCP status, or None if MCP is unsupported for this agent."""
        mgr = self.get_mcp_manager()
        if mgr is None:
            return None
        return mgr.get_status(self.config_dir, self.config)

    def get_skill_status(self) -> SkillStatus | None:
        """Get status of agent skills.

        Returns:
            SkillStatus object, or None if agent doesn't support skills
        """
        return None
