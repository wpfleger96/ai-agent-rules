"""Shared agent implementation for agent-agnostic configurations."""

from __future__ import annotations

import os

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rules.agents.base import Agent
from ai_rules.platform import Platform, get_appdata_dir, is_platform

if TYPE_CHECKING:
    from ai_rules.skills import SkillStatus


# Tombstone — removal-only. ai-rules used to symlink its Sietch Tabr persona
# pack into these app data dirs; Buzz stopped reading folder-based packs in
# block/buzz#1846. Installs remove the stale links. Do NOT re-add a pack target.
_LEGACY_PACK_ID = "com.wpfleger.sietch-tabr"
_LEGACY_APP_BUNDLES = (
    "xyz.block.buzz.app",
    "xyz.block.buzz.app.dev",
    "xyz.block.sprout.app",
    "xyz.block.sprout.app.dev",
)


def _get_app_data_dir() -> Path:
    if is_platform(Platform.WINDOWS):
        return get_appdata_dir()
    if is_platform(Platform.MACOS):
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))


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

    def get_expected_agents_md_content(self) -> str:
        """Compute what the merged AGENTS.md content should be."""
        base_path = self.config_dir / "AGENTS.md"
        base_content = (
            base_path.read_text(encoding="utf-8") if base_path.exists() else ""
        )
        base_stripped = base_content.rstrip("\n")
        appended = self.config.agents_md.strip()
        if base_stripped and appended:
            return base_stripped + "\n\n" + appended + "\n"
        if base_stripped:
            return base_stripped + "\n"
        if appended:
            return appended + "\n"
        return ""

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

        merged = self.get_expected_agents_md_content()

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

        expected = self.get_expected_agents_md_content()
        actual = cache_path.read_text(encoding="utf-8")
        return actual != expected

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of shared symlinks for agent-agnostic configurations."""
        from ai_rules.config import get_agent_skills_dirs
        from ai_rules.skills import deployable_skills

        result = []

        if self.needs_agents_md_cache:
            cache_path = self.config.get_merged_agents_md_path()
            assert cache_path is not None
            agents_md_source = cache_path
        else:
            agents_md_source = self.config_dir / "AGENTS.md"
        result.append((Path("~/AGENTS.md"), agents_md_source))

        for name, skill_folder in deployable_skills(
            self.config_dir, self.config.skills
        ).items():
            for agent_skills_dir in get_agent_skills_dirs().values():
                result.append((agent_skills_dir / name, skill_folder))

        return result

    def get_skill_status(self) -> SkillStatus:
        """Get status of shared skills symlinked to multiple agent directories."""
        from ai_rules.config import get_agent_skills_dirs
        from ai_rules.skills import SkillManager

        manager = SkillManager(
            config_dir=self.config_dir,
            agent_id="",
            user_skills_dirs=list(get_agent_skills_dirs().values()),
            profile_skills=self.config.skills,
        )
        return manager.get_status()

    def get_deprecated_symlinks(self) -> list[Path]:
        """Return stale Buzz/Sprout persona pack symlinks for cleanup."""
        app_data = _get_app_data_dir()
        return [
            app_data / bundle / "agents" / "teams" / _LEGACY_PACK_ID
            for bundle in _LEGACY_APP_BUNDLES
        ]

    def get_deprecated_symlink_source(self) -> Path:
        return self.config_dir / "buzz"
