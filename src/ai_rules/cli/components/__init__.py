"""Ordered lifecycle component registries."""

from __future__ import annotations

from ai_rules.cli.components.cleanup import CleanupComponent
from ai_rules.cli.components.completions import CompletionsComponent
from ai_rules.cli.components.confirmation import InstallConfirmationComponent
from ai_rules.cli.components.extensions import ClaudeExtensionsComponent
from ai_rules.cli.components.legacy import LegacyMigrationComponent
from ai_rules.cli.components.mcp import MCPComponent
from ai_rules.cli.components.optional_tools import OptionalToolsComponent
from ai_rules.cli.components.plugins import ClaudePluginComponent
from ai_rules.cli.components.settings_cache import (
    CacheCleanupComponent,
    SettingsCacheComponent,
)
from ai_rules.cli.components.skills import SkillsComponent
from ai_rules.cli.components.source_files import SourceFilesComponent
from ai_rules.cli.components.symlinks import SymlinkComponent
from ai_rules.cli.context import Component

INSTALL_COMPONENTS: tuple[Component, ...] = (
    OptionalToolsComponent(),
    SettingsCacheComponent(),
    LegacyMigrationComponent(),
    InstallConfirmationComponent(),
    CacheCleanupComponent(),
    SymlinkComponent(),
    MCPComponent(),
    ClaudePluginComponent(),
    CleanupComponent(),
    CompletionsComponent(),
)
STATUS_COMPONENTS: tuple[Component, ...] = (
    SymlinkComponent(),
    SettingsCacheComponent(),
    MCPComponent(),
    ClaudePluginComponent(),
    ClaudeExtensionsComponent(),
    SkillsComponent(),
    OptionalToolsComponent(),
    CompletionsComponent(),
)
DIFF_COMPONENTS: tuple[Component, ...] = (
    SymlinkComponent(),
    SettingsCacheComponent(),
    MCPComponent(),
    ClaudePluginComponent(),
    ClaudeExtensionsComponent(),
    SkillsComponent(),
)
VALIDATE_COMPONENTS: tuple[Component, ...] = (SourceFilesComponent(),)
UNINSTALL_COMPONENTS: tuple[Component, ...] = (SymlinkComponent(), MCPComponent())
