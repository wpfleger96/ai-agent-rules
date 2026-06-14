from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    is_still_in_use: Callable[[object], bool] | None = None


DEPRECATED_TOOLS: tuple[DeprecatedToolSpec, ...] = ()


def get_deprecated_mcp_names() -> frozenset[str]:
    return frozenset(spec.tool_id for spec in DEPRECATED_TOOLS if spec.is_mcp)


@dataclass(frozen=True)
class ActiveToolSpec:
    tool_id: str
    command_name: str
    get_install_spec: Callable[[], ToolSpec]
    is_configured: Callable[[object], bool] | None = None


def _get_statusline_spec() -> ToolSpec:
    from ai_rules.tools.statusline import StatuslineTool

    return StatuslineTool.INSTALL_SPEC


ACTIVE_TOOLS: tuple[ActiveToolSpec, ...] = (
    ActiveToolSpec(
        tool_id="statusline",
        command_name="claude-statusline",
        get_install_spec=_get_statusline_spec,
    ),
)
