"""Codex CLI agent implementation."""

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class CodexAgent(Agent):
    """Agent for Codex CLI configuration."""

    @property
    def name(self) -> str:
        return "Codex CLI"

    @property
    def agent_id(self) -> str:
        return "codex"

    @property
    def config_file_name(self) -> str:
        return "config.toml"

    @property
    def config_file_format(self) -> str:
        return "toml"

    @property
    def preserved_fields(self) -> list[str]:
        return ["projects"]

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of all Codex CLI symlinks."""
        result = []

        result.append(
            (
                Path("~/.codex/AGENTS.md"),
                self.config_dir / "AGENTS.md",
            )
        )

        config_file = self.config_dir / "codex" / "config.toml"
        if config_file.exists():
            target_file = self.config.get_settings_file_for_symlink(
                "codex", config_file, force=bool(self._effective_preserved_fields)
            )
            result.append((Path("~/.codex/config.toml"), target_file))

        return result

    def get_mcp_manager(self) -> "MCPManager":
        from ai_rules.mcp import CodexMCPManager

        return CodexMCPManager()
