"""Codex CLI agent implementation."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.mcp import MCPManager


class CodexAgent(Agent):
    """Agent for Codex CLI configuration."""

    name = "Codex CLI"
    agent_id = "codex"
    config_file_name = "config.toml"
    config_file_format = "toml"
    preserved_fields = ["projects"]
    settings_symlink_target = Path("~/.codex/config.toml")
    instructions_target = "~/.codex/AGENTS.md"
    instructions_source = "AGENTS.md"
    skills_dir: ClassVar[Path | None] = Path("~/.agents/skills")

    def get_mcp_manager(self) -> MCPManager:
        from ai_rules.mcp import CodexMCPManager

        return CodexMCPManager()
