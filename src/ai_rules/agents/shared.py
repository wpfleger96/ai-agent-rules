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

    @property
    def needs_agents_md_cache(self) -> bool:
        return bool(self.config.agents_md)

    @property
    def agents_md_cache_path(self) -> Path | None:
        return self.config.get_merged_agents_md_path()

    def build_merged_agents_md(self, force_rebuild: bool = False) -> Path | None:
        """Write base AGENTS.md + profile agents_md content to cache."""
        if not self.needs_agents_md_cache:
            return None

        cache_path = self.config.get_merged_agents_md_path()
        if cache_path is None:
            return None

        if not force_rebuild and cache_path.exists():
            if not self.is_agents_md_cache_stale():
                return cache_path

        base_path = self.config_dir / "AGENTS.md"
        base_content = (
            base_path.read_text(encoding="utf-8") if base_path.exists() else ""
        )

        merged = (
            base_content.rstrip("\n") + "\n\n" + self.config.agents_md.strip() + "\n"
        )

        from ai_rules.config import write_file_atomic

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        write_file_atomic(cache_path, lambda f: f.write(merged))
        return cache_path

    def is_agents_md_cache_stale(self) -> bool:
        """Check if cached merged AGENTS.md is stale."""
        if not self.needs_agents_md_cache:
            return False

        cache_path = self.config.get_merged_agents_md_path()
        if not cache_path or not cache_path.exists():
            return True

        cache_mtime = cache_path.stat().st_mtime

        from ai_rules.config import get_user_config_path

        user_config_path = get_user_config_path()
        if user_config_path.exists() and user_config_path.stat().st_mtime > cache_mtime:
            return True

        if self.config.profile_name and self.config.profile_name != "default":
            from ai_rules.profiles import ProfileLoader

            loader = ProfileLoader()
            profile_path = loader._profiles_dir / f"{self.config.profile_name}.yaml"
            if profile_path.exists() and profile_path.stat().st_mtime > cache_mtime:
                return True

        base_path = self.config_dir / "AGENTS.md"
        if base_path.exists() and base_path.stat().st_mtime > cache_mtime:
            return True

        # Content comparison fallback
        base_content = (
            base_path.read_text(encoding="utf-8") if base_path.exists() else ""
        )
        expected = (
            base_content.rstrip("\n") + "\n\n" + self.config.agents_md.strip() + "\n"
        )
        actual = cache_path.read_text(encoding="utf-8")
        return actual != expected

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of shared symlinks for agent-agnostic configurations."""
        from ai_rules.config import AGENT_SKILLS_DIRS
        from ai_rules.skills import SkillManager

        result = []

        if self.needs_agents_md_cache:
            agents_md_source = self.config.get_merged_agents_md_path()
        else:
            agents_md_source = self.config_dir / "AGENTS.md"
        result.append((Path("~/AGENTS.md"), agents_md_source))

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
