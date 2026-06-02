from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ai_rules.bootstrap.installer import _is_recall_configured

__all__ = [
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
