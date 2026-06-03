from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_rules.bootstrap.installer import _is_recall_configured

if TYPE_CHECKING:
    from ai_rules.bootstrap.updater import ToolSpec

__all__ = [
    "ActiveToolSpec",
    "ACTIVE_TOOLS",
    "DeprecatedToolSpec",
    "DEPRECATED_TOOLS",
    "get_deprecated_mcp_names",
]


@dataclass(frozen=True)
class DeprecatedToolSpec:
    tool_id: str
    package_name: str
    command_name: str
    is_mcp: bool = False
    # If provided and returns True, the tool is still in use and should not be pruned.
    is_configured: Callable[[object], bool] | None = None


DEPRECATED_TOOLS: tuple[DeprecatedToolSpec, ...] = (
    DeprecatedToolSpec(
        tool_id="recall",
        package_name="recall-mcp-server",
        command_name="recall",
        is_mcp=True,
        is_configured=lambda config: _is_recall_configured(config),
    ),
)


def get_deprecated_mcp_names() -> frozenset[str]:
    return frozenset(spec.tool_id for spec in DEPRECATED_TOOLS if spec.is_mcp)


@dataclass(frozen=True)
class ActiveToolSpec:
    tool_id: str
    get_install_spec: Callable[[], ToolSpec]  # lazy to avoid circular imports
    is_configured: Callable[[object], bool] | None = None
    # If is_configured is provided and returns False, skip install (tool not wanted)
    # If None, always install


def _get_statusline_spec() -> ToolSpec:
    from ai_rules.tools.statusline import StatuslineTool

    return StatuslineTool.INSTALL_SPEC


ACTIVE_TOOLS: tuple[ActiveToolSpec, ...] = (
    ActiveToolSpec(
        tool_id="statusline",
        get_install_spec=_get_statusline_spec,
    ),
)
