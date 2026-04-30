"""Base agent class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

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

    def _merge_managed_mcps(self, merged: dict[str, Any]) -> None:
        """Merge managed MCPs into the settings cache.

        Reconciles managed entries (add/update/remove) while preserving
        unmanaged entries that the user added directly.
        """
        from ai_rules.mcp import is_managed_value

        mgr = self.get_mcp_manager()
        if mgr is None or mgr.mcp_settings_key is None:
            return

        mcp_key = mgr.mcp_settings_key
        native_mcps = mgr.get_native_mcps(self.config_dir, self.config)

        current = merged.get(mcp_key, {})
        if not isinstance(current, dict):
            current = {}

        if mgr.mcp_tracking_key:
            tracking = merged.get(mgr.mcp_tracking_key, {})
            tracked = set(tracking.get("names", []))
        else:
            tracked = {
                n
                for n, c in current.items()
                if is_managed_value(c.get(mgr._marker_field))
            }
        for name in tracked - set(native_mcps.keys()):
            current.pop(name, None)

        current.update(native_mcps)

        if current:
            merged[mcp_key] = current
        else:
            merged.pop(mcp_key, None)

        if mgr.mcp_tracking_key:
            if native_mcps:
                merged[mgr.mcp_tracking_key] = {"names": sorted(native_mcps.keys())}
            else:
                merged.pop(mgr.mcp_tracking_key, None)

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
