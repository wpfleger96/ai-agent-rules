"""Ordered lifecycle component registries."""

from __future__ import annotations

from ai_rules.cli.components.agents_md import AgentsMdComponent
from ai_rules.cli.components.completions import CompletionsComponent
from ai_rules.cli.components.config import ConfigComponent
from ai_rules.cli.components.extensions import ClaudeExtensionsComponent
from ai_rules.cli.components.mcp import MCPComponent
from ai_rules.cli.components.optional_tools import OptionalToolsComponent
from ai_rules.cli.components.plugins import ClaudePluginComponent
from ai_rules.cli.components.settings import SettingsComponent
from ai_rules.cli.components.skills import SkillsComponent
from ai_rules.cli.components.source_files import SourceFilesComponent
from ai_rules.cli.context import Component

INSTALL_COMPONENTS: tuple[Component, ...] = (
    SettingsComponent(),
    AgentsMdComponent(),
    OptionalToolsComponent(),
    ConfigComponent(),
    SkillsComponent(),
    ClaudeExtensionsComponent(),
    MCPComponent(),
    ClaudePluginComponent(),
    CompletionsComponent(),
)

STATUS_COMPONENTS: tuple[Component, ...] = (
    ConfigComponent(),
    SettingsComponent(),
    AgentsMdComponent(),
    MCPComponent(),
    ClaudePluginComponent(),
    ClaudeExtensionsComponent(),
    SkillsComponent(),
    OptionalToolsComponent(),
    CompletionsComponent(),
)

DIFF_COMPONENTS: tuple[Component, ...] = (
    ConfigComponent(),
    SettingsComponent(),
    AgentsMdComponent(),
    MCPComponent(),
    ClaudePluginComponent(),
    ClaudeExtensionsComponent(),
    SkillsComponent(),
)

# Uninstall waves run in order. MCPs and plugins rewrite settings/MCP JSON
# through the links and cache that later waves delete, and the whole-cache
# delete runs after the per-file cache cleanup inside it.
UNINSTALL_WAVES: tuple[tuple[Component, ...], ...] = (
    (MCPComponent(), ClaudePluginComponent()),
    (
        ConfigComponent(),
        SkillsComponent(),
        ClaudeExtensionsComponent(),
        OptionalToolsComponent(),
        AgentsMdComponent(),
    ),
    (SettingsComponent(),),
)

UNINSTALL_COMPONENTS: tuple[Component, ...] = tuple(
    c for wave in UNINSTALL_WAVES for c in wave
)

VALIDATE_COMPONENTS: tuple[Component, ...] = (SourceFilesComponent(),)
