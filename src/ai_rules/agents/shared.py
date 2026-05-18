"""Shared agent implementation for agent-agnostic configurations."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent

if TYPE_CHECKING:
    from ai_rules.skills import SkillStatus


class SharedAgent(Agent):
    """Agent for shared configurations that both Claude Code and Goose respect."""

    @property
    def name(self) -> str:
        return "Shared"

    @property
    def agent_id(self) -> str:
        return "shared"

    @property
    def config_file_name(self) -> str:
        return ""

    @property
    def config_file_format(self) -> str:
        return ""

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of shared symlinks for agent-agnostic configurations."""
        from ai_rules.config import AGENT_SKILLS_DIRS
        from ai_rules.skills import SkillManager

        result = []

        result.append((Path("~/AGENTS.md"), self.config_dir / "AGENTS.md"))

        skills_dir = self.config_dir / "skills"
        if skills_dir.exists():
            for skill_folder in sorted(skills_dir.glob("*")):
                if (
                    skill_folder.is_dir()
                    and not skill_folder.name.startswith(".")
                    and not SkillManager.is_skill_disabled(skill_folder)
                ):
                    for agent_skills_dir in AGENT_SKILLS_DIRS.values():
                        result.append(
                            (agent_skills_dir / skill_folder.name, skill_folder)
                        )

        return result

    def get_skill_status(self) -> SkillStatus:
        """Get status of shared skills symlinked to multiple agent directories."""
        from ai_rules.config import AGENT_SKILLS_DIRS
        from ai_rules.skills import SkillManager

        manager = SkillManager(
            config_dir=self.config_dir,
            agent_id="",
            user_skills_dirs=list(AGENT_SKILLS_DIRS.values()),
        )
        return manager.get_status()
