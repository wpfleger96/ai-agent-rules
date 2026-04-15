"""Claude Code agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

    def _get_configured_hooks(self, settings: dict[str, Any]) -> set[str]:
        """Get set of hook filenames that have configurations in settings.

        Scans settings['hooks'] for any command that references a file in ~/.claude/hooks/.

        Args:
            settings: Merged settings dict containing hooks configuration

        Returns:
            Set of hook filenames (e.g., {'subagentStop.py', 'skillRouter.py'})
        """
        import re

        configured = set()
        hooks_config = settings.get("hooks", {})

        for event_handlers in hooks_config.values():
            for handler in event_handlers:
                for hook in handler.get("hooks", []):
                    if hook.get("type") == "command":
                        command = hook.get("command", "")
                        if (
                            "~/.claude/hooks/" in command
                            or "/.claude/hooks/" in command
                        ):
                            match = re.search(
                                r"[~/.]*/\.claude/hooks/(\w+\.py)", command
                            )
                            if match:
                                configured.add(match.group(1))

        return configured

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
                "claude", settings_file
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
            import json

            base_settings_path = self.config_dir / "claude" / "settings.json"
            if base_settings_path.exists():
                try:
                    with open(base_settings_path) as f:
                        base_settings = json.load(f)
                    merged_settings = self.config.merge_settings(
                        "claude", base_settings
                    )
                    configured_hooks = self._get_configured_hooks(merged_settings)

                    for hook_file in sorted(hooks_dir.glob("*.py")):
                        if hook_file.name in configured_hooks:
                            result.append(
                                (
                                    Path(f"~/.claude/hooks/{hook_file.name}"),
                                    hook_file,
                                )
                            )
                except (json.JSONDecodeError, OSError):
                    pass

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
