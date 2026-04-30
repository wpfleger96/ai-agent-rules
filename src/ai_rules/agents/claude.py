"""Claude Code agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent
from ai_rules.utils import is_managed_target

if TYPE_CHECKING:
    from ai_rules.claude_extensions import ClaudeExtensionStatus
    from ai_rules.mcp import MCPManager


class ClaudeAgent(Agent):
    """Agent for Claude Code configuration."""

    _KNOWN_OLD_LOCATIONS: list[Path] = [
        Path("~/CLAUDE.md"),
    ]

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def agent_id(self) -> str:
        return "claude"

    @property
    def config_file_name(self) -> str:
        return "settings.json"

    @property
    def config_file_format(self) -> str:
        return "json"

    @property
    def preserved_fields(self) -> list[str]:
        return ["enabledPlugins", "hooks"]

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of all Claude Code symlinks including dynamic agents/commands."""
        result = []

        result.append(
            (Path("~/.claude/CLAUDE.md"), self.config_dir / "claude" / "CLAUDE.md")
        )

        settings_file = self.config_dir / "claude" / "settings.json"
        if settings_file.exists():
            target_file = self.config.get_settings_file_for_symlink(
                "claude", settings_file, force=bool(self._effective_preserved_fields)
            )
            result.append((Path("~/.claude/settings.json"), target_file))

        agents_dir = self.config_dir / "claude" / "agents"
        if agents_dir.exists():
            for agent_file in sorted(agents_dir.glob("*.md")):
                result.append(
                    (
                        Path(f"~/.claude/agents/{agent_file.name}"),
                        agent_file,
                    )
                )

        commands_dir = self.config_dir / "claude" / "commands"
        if commands_dir.exists():
            for command_file in sorted(commands_dir.glob("*.md")):
                result.append(
                    (
                        Path(f"~/.claude/commands/{command_file.name}"),
                        command_file,
                    )
                )

        hooks_dir = self.config_dir / "claude" / "hooks"
        if hooks_dir.exists():
            for hook_file in sorted(hooks_dir.iterdir()):
                if hook_file.is_file():
                    result.append(
                        (
                            Path(f"~/.claude/hooks/{hook_file.name}"),
                            hook_file,
                        )
                    )

        return result

    def get_deprecated_symlinks(self) -> list[Path]:
        """Return deprecated symlink locations for cleanup.

        Dynamically checks known old locations to verify they are actually
        managed symlinks before flagging as deprecated.

        Returns:
            List of paths that are deprecated symlinks pointing to ai-rules
        """
        deprecated = []
        for loc in self._KNOWN_OLD_LOCATIONS:
            loc = loc.expanduser()
            if loc.is_symlink():
                try:
                    target = loc.resolve()
                    if is_managed_target(target, self.config_dir):
                        deprecated.append(loc)
                except (OSError, RuntimeError):
                    pass
        return deprecated

    def get_mcp_manager(self) -> "MCPManager":
        from ai_rules.mcp import ClaudeMCPManager

        return ClaudeMCPManager()

    def get_extension_status(self) -> "ClaudeExtensionStatus":
        """Get status of Claude extensions (agents, commands, hooks).

        Returns:
            ClaudeExtensionStatus object with categorized extensions
        """
        from ai_rules.claude_extensions import ClaudeExtensionManager

        manager = ClaudeExtensionManager(self.config_dir)
        return manager.get_status()
