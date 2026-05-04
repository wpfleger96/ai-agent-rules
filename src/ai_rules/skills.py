"""Shared skills management for AI agents."""

from __future__ import annotations

import importlib.metadata

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ai_rules.utils import is_managed_target


@dataclass
class SkillMetadata:
    """Parsed SKILL.md metadata."""

    name: str
    description: str
    body: str = ""


@dataclass
class SkillItem:
    """Status of a single skill."""

    name: str
    target_path: Path
    actual_source: Path | None
    expected_source: Path | None
    is_symlink: bool
    is_managed: bool
    is_installed: bool
    is_broken: bool
    metadata: SkillMetadata | None = None


@dataclass
class SkillStatus:
    """Status of skills for an agent."""

    managed_installed: dict[str, SkillItem] = field(default_factory=dict)
    managed_pending: dict[str, SkillItem] = field(default_factory=dict)
    managed_wrong_target: dict[str, SkillItem] = field(default_factory=dict)
    unmanaged: dict[str, SkillItem] = field(default_factory=dict)


class SkillManager:
    """Manages skills for any AI agent."""

    def __init__(
        self,
        config_dir: Path,
        agent_id: str,
        user_skills_dir: Path | None = None,
        user_skills_dirs: list[Path] | None = None,
    ):
        """Initialize skill manager.

        Args:
            config_dir: ai-rules config directory
            agent_id: Agent identifier (e.g., 'claude', 'goose', '' for shared)
            user_skills_dir: Where skills are installed (e.g., ~/.claude/skills/)
            user_skills_dirs: Multiple directories for shared skills
        """
        self.config_dir = config_dir
        self.agent_id = agent_id
        if user_skills_dirs:
            self.user_skills_dirs = [p.expanduser() for p in user_skills_dirs]
        elif user_skills_dir:
            self.user_skills_dirs = [user_skills_dir.expanduser()]
        else:
            self.user_skills_dirs = []

    @staticmethod
    def parse_skill_md(skill_dir: Path) -> SkillMetadata | None:
        """Parse SKILL.md file and extract metadata.

        Args:
            skill_dir: Path to skill directory containing SKILL.md

        Returns:
            SkillMetadata or None if parsing fails
        """
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None

        content = skill_file.read_text()

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                    body = parts[2].strip()
                    return SkillMetadata(
                        name=frontmatter.get("name", skill_dir.name),
                        description=frontmatter.get("description", ""),
                        body=body,
                    )
                except yaml.YAMLError:
                    pass

        return SkillMetadata(name=skill_dir.name, description="", body=content)

    def _get_managed_skills(self) -> dict[str, Path]:
        """Get all managed skills from config_dir."""
        if self.agent_id:
            source_dir = self.config_dir / self.agent_id / "skills"
        else:
            source_dir = self.config_dir / "skills"

        if not source_dir.exists():
            return {}

        result = {}
        for item in sorted(source_dir.glob("*")):
            if item.is_dir():
                result[item.name] = item
        return result

    def get_orphaned_skills(self) -> dict[str, list[Path]]:
        """Get skill symlinks that point to ai-rules but source no longer exists.

        Returns:
            dict mapping skill name -> list of orphaned symlink paths
        """
        orphaned: dict[str, list[Path]] = {}

        for user_dir in self.user_skills_dirs:
            if not user_dir.exists():
                continue

            for item in user_dir.glob("*"):
                if not item.is_symlink() or not item.is_dir():
                    continue

                try:
                    target = item.resolve()
                    if (
                        is_managed_target(target, self.config_dir)
                        and not target.exists()
                    ):
                        if item.name not in orphaned:
                            orphaned[item.name] = []
                        orphaned[item.name].append(item)
                except (OSError, RuntimeError):
                    try:
                        raw_target = item.readlink()
                        if is_managed_target(raw_target, self.config_dir):
                            if item.name not in orphaned:
                                orphaned[item.name] = []
                            orphaned[item.name].append(item)
                    except (OSError, RuntimeError):
                        pass

        return orphaned

    def _scan_installed_skills(self) -> dict[str, list[tuple[Path, Path | None, bool]]]:
        """Scan user directories for installed skills.

        Returns:
            dict mapping name -> list of (target_path, symlink_source_or_none, is_broken) per directory
        """
        result: dict[str, list[tuple[Path, Path | None, bool]]] = {}

        for user_dir in self.user_skills_dirs:
            if not user_dir.exists():
                continue

            for item in sorted(user_dir.glob("*")):
                if not item.is_dir() and not item.is_symlink():
                    continue

                name = item.name

                if item.is_symlink():
                    try:
                        source = item.resolve()
                        is_broken = not source.exists()
                    except (OSError, RuntimeError):
                        source = None
                        is_broken = True
                    entry = (item, source, is_broken)
                else:
                    entry = (item, None, False)

                if name not in result:
                    result[name] = []
                result[name].append(entry)

        return result

    def get_status(self) -> SkillStatus:
        """Get comprehensive status of skills."""
        status = SkillStatus()
        managed_sources = self._get_managed_skills()
        installed = self._scan_installed_skills()

        for name, expected_source in managed_sources.items():
            metadata = self.parse_skill_md(expected_source)

            if name in installed:
                installations = installed[name]
                expected_count = len(self.user_skills_dirs)
                actual_count = len(installations)

                synced_count = sum(
                    1
                    for _, actual_source, is_broken in installations
                    if not is_broken
                    and actual_source
                    and actual_source == expected_source.resolve()
                )

                has_issues = any(
                    is_broken
                    or (actual_source and actual_source != expected_source.resolve())
                    for _, actual_source, is_broken in installations
                )

                if synced_count == expected_count and not has_issues:
                    target_path, actual_source, _ = installations[0]
                    status.managed_installed[name] = SkillItem(
                        name=name,
                        target_path=target_path,
                        actual_source=actual_source,
                        expected_source=expected_source,
                        is_symlink=True,
                        is_managed=True,
                        is_installed=True,
                        is_broken=False,
                        metadata=metadata,
                    )
                elif has_issues or actual_count < expected_count:
                    target_path, actual_source, is_broken = installations[0]
                    status.managed_wrong_target[name] = SkillItem(
                        name=name,
                        target_path=target_path,
                        actual_source=actual_source,
                        expected_source=expected_source,
                        is_symlink=actual_source is not None,
                        is_managed=True,
                        is_installed=False,
                        is_broken=any(ib for _, _, ib in installations),
                        metadata=metadata,
                    )
            else:
                user_path = (
                    self.user_skills_dirs[0] / name
                    if self.user_skills_dirs
                    else Path(f"~/.skills/{name}")
                )
                status.managed_pending[name] = SkillItem(
                    name=name,
                    target_path=user_path,
                    actual_source=None,
                    expected_source=expected_source,
                    is_symlink=False,
                    is_managed=True,
                    is_installed=False,
                    is_broken=False,
                    metadata=metadata,
                )

        for name, installations in installed.items():
            if name not in managed_sources:
                target_path, actual_source, is_broken = installations[0]
                metadata = None
                if target_path.is_dir():
                    metadata = self.parse_skill_md(target_path)

                status.unmanaged[name] = SkillItem(
                    name=name,
                    target_path=target_path,
                    actual_source=actual_source,
                    expected_source=None,
                    is_symlink=actual_source is not None,
                    is_managed=False,
                    is_installed=False,
                    is_broken=is_broken,
                    metadata=metadata,
                )

        return status

    def list_bundled_skills(self) -> list[SkillMetadata]:
        """List all bundled skills with their metadata."""
        managed = self._get_managed_skills()
        results = []
        for name, source_path in managed.items():
            metadata = self.parse_skill_md(source_path)
            if metadata is None:
                metadata = SkillMetadata(name=name, description="")
            results.append(metadata)
        return results

    def get_skill_content(self, name: str) -> str | None:
        """Get the raw SKILL.md content for a bundled skill.

        Returns:
            Raw file content, or None if skill doesn't exist.
        """
        managed = self._get_managed_skills()
        if name not in managed:
            return None
        skill_file = managed[name] / "SKILL.md"
        if not skill_file.exists():
            return None
        return skill_file.read_text()

    @staticmethod
    def get_skill_url(name: str) -> str | None:
        """Construct a versioned GitHub URL for a bundled skill.

        Returns:
            GitHub blob URL, or None if repo URL can't be determined.
        """
        try:
            dist = importlib.metadata.distribution("ai-agent-rules")
        except importlib.metadata.PackageNotFoundError:
            return None

        repo_url = None
        for url_entry in dist.metadata.get_all("Project-URL") or []:
            label, url = url_entry.split(",", 1)
            if label.strip().lower() == "repository":
                repo_url = url.strip()
                break

        if not repo_url:
            return None

        return f"{repo_url}/blob/main/src/ai_rules/config/skills/{name}/SKILL.md"
