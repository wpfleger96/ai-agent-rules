"""Base tool class."""

from __future__ import annotations

from abc import abstractmethod

from ai_rules.targets.base import ConfigTarget


class Tool(ConfigTarget):
    """Base class for external tool configuration managers.

    Sibling to Agent — shares the ConfigTarget config pipeline but
    has no MCP, skills, or plugin machinery.
    """

    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Short identifier for the tool (e.g., 'statusline')."""
        pass

    @property
    def target_id(self) -> str:
        return self.tool_id
