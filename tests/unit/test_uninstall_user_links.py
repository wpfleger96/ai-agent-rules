"""Uninstall removes only links ai-rules created, never user-created links.

A link is ai-rules' only when its raw target is the expected source entry, or
the same entry inside an older package install (``.../ai_rules/config/...``).
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.claude_extensions import ClaudeExtensionManager
from ai_rules.cli.components.config import ConfigComponent
from ai_rules.cli.components.extensions import ClaudeExtensionsComponent
from ai_rules.cli.components.skills import SkillsComponent
from ai_rules.cli.context import CliContext, Component
from ai_rules.config import Config
from ai_rules.targets.base import ConfigTarget


def _uninstall(component: Component, config_dir: Path, *targets: ConfigTarget) -> None:
    ctx = CliContext(
        console=Console(file=StringIO()),
        config_dir=config_dir,
        config=Config(exclude_symlinks=[]),
        profile_name=None,
        all_targets=targets,
        selected_targets=targets,
        dry_run=False,
        yes=True,
    )
    component.uninstall(ctx)


def _stale_package(tmp_path: Path, relative: str) -> Path:
    """An entry inside a previous Python version's package install."""
    return (
        tmp_path
        / "uv/tools/ai-agent-rules/lib/python3.13/site-packages/ai_rules/config"
        / relative
    )


def _unrelated(tmp_path: Path, relative: str) -> Path:
    """Same short suffix as a package path, in a user folder named like it."""
    return tmp_path / "my-ai-rules-notes" / relative


@pytest.fixture
def config_dir(tmp_path):
    config_dir = tmp_path / "python3.14" / "site-packages" / "ai_rules" / "config"
    for relative, content in {
        "AGENTS.md": "# agents\n",
        "claude/CLAUDE.md": "@~/AGENTS.md\n",
        "claude/agents/managed.md": "# managed\n",
        "skills/research/SKILL.md": "# research\n",
    }.items():
        (config_dir / relative).parent.mkdir(parents=True, exist_ok=True)
        (config_dir / relative).write_text(content)
    return config_dir


@pytest.fixture
def skills_dir(mock_home):
    path = mock_home / ".agents" / "skills"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def agents_dir(mock_home):
    path = mock_home / ".claude" / "agents"
    path.mkdir(parents=True)
    return path


def _uninstall_skills(config_dir: Path) -> None:
    config = Config(exclude_symlinks=[])
    _uninstall(SkillsComponent(), config_dir, SharedAgent(config_dir, config))


@pytest.mark.unit
class TestSkillsUninstallOwnership:
    def test_keeps_link_into_unrelated_folder_named_like_package(
        self, tmp_path, config_dir, skills_dir
    ):
        notes = _unrelated(tmp_path, "own")
        notes.mkdir(parents=True)
        link = skills_dir / "own"
        link.symlink_to(notes)

        _uninstall_skills(config_dir)

        assert link.is_symlink()

    def test_keeps_same_suffix_link_into_unrelated_folder(
        self, tmp_path, config_dir, skills_dir
    ):
        notes = _unrelated(tmp_path, "config/skills/shaped")
        notes.mkdir(parents=True)
        link = skills_dir / "shaped"
        link.symlink_to(notes)

        _uninstall_skills(config_dir)

        assert link.is_symlink()

    def test_keeps_user_alias_to_shared_skill(self, config_dir, skills_dir):
        alias = skills_dir / "my-research"
        alias.symlink_to(config_dir / "skills" / "research")

        _uninstall_skills(config_dir)

        assert alias.is_symlink()

    def test_keeps_link_whose_target_cannot_be_read(
        self, config_dir, skills_dir, monkeypatch
    ):
        link = skills_dir / "research"
        link.symlink_to(config_dir / "skills" / "research")
        real_readlink, real_resolve = Path.readlink, Path.resolve

        def fail_for_link(path: Path) -> None:
            if path == link:
                raise OSError("unreadable")

        def readlink(self: Path) -> Path:
            fail_for_link(self)
            return real_readlink(self)

        def resolve(self: Path, strict: bool = False) -> Path:
            fail_for_link(self)
            return real_resolve(self, strict)

        monkeypatch.setattr(Path, "readlink", readlink)
        monkeypatch.setattr(Path, "resolve", resolve)

        _uninstall_skills(config_dir)

        assert link.is_symlink()

    def test_removes_managed_relative_and_stale_package_links(
        self, tmp_path, config_dir, skills_dir
    ):
        managed = skills_dir / "research"
        managed.symlink_to(config_dir / "skills" / "research")
        (config_dir / "skills" / "relative").mkdir()
        relative = skills_dir / "relative"
        relative.symlink_to(
            Path("../../..") / config_dir.relative_to(tmp_path) / "skills/relative"
        )
        stale = skills_dir / "retired"
        stale.symlink_to(_stale_package(tmp_path, "skills/retired"))

        _uninstall_skills(config_dir)

        assert not managed.is_symlink()
        assert not relative.is_symlink()
        assert not stale.is_symlink()

    def test_removes_link_to_source_alias_on_round_trip(self, config_dir, skills_dir):
        (config_dir / "skills" / "review-source-alias").symlink_to("research")
        link = skills_dir / "review-source-alias"
        link.symlink_to(config_dir / "skills" / "review-source-alias")

        _uninstall_skills(config_dir)

        assert not link.is_symlink()


@pytest.mark.unit
class TestExtensionOrphanOwnership:
    def test_orphans_exclude_user_links_and_include_stale_package_links(
        self, tmp_path, config_dir, agents_dir
    ):
        (agents_dir / "mine.md").symlink_to(_unrelated(tmp_path, "mine.md"))
        (agents_dir / "shaped.md").symlink_to(
            _unrelated(tmp_path, "claude/agents/shaped.md")
        )
        (agents_dir / "alias.md").symlink_to(config_dir / "claude/agents/gone.md")
        stale = agents_dir / "old.md"
        stale.symlink_to(_stale_package(tmp_path, "claude/agents/old.md"))

        orphaned = ClaudeExtensionManager(config_dir).get_all_orphaned()["agents"]

        assert orphaned == {"old": stale}


def _uninstall_extensions(config_dir: Path) -> None:
    config = Config(exclude_symlinks=[])
    _uninstall(ClaudeExtensionsComponent(), config_dir, ClaudeAgent(config_dir, config))


@pytest.mark.unit
class TestNamedExtensionUninstallOwnership:
    def test_keeps_user_replacement_of_managed_extension(
        self, tmp_path, config_dir, agents_dir
    ):
        notes = _unrelated(tmp_path, "managed.md")
        notes.parent.mkdir(parents=True)
        notes.write_text("# mine\n")
        link = agents_dir / "managed.md"
        link.symlink_to(notes)

        _uninstall_extensions(config_dir)

        assert link.is_symlink()

    @pytest.mark.parametrize("stale", [False, True], ids=["current", "stale"])
    def test_removes_managed_extension(self, tmp_path, config_dir, agents_dir, stale):
        link = agents_dir / "managed.md"
        link.symlink_to(
            _stale_package(tmp_path, "claude/agents/managed.md")
            if stale
            else config_dir / "claude/agents/managed.md"
        )

        _uninstall_extensions(config_dir)

        assert not link.is_symlink()


def _uninstall_config(config_dir: Path) -> None:
    config = Config(exclude_symlinks=[])
    _uninstall(ConfigComponent(), config_dir, ClaudeAgent(config_dir, config))


@pytest.mark.unit
class TestManifestUninstallOwnership:
    def test_keeps_user_replacement_of_manifest_destination(
        self, tmp_path, config_dir, mock_home
    ):
        notes = _unrelated(tmp_path, "claude/CLAUDE.md")
        notes.parent.mkdir(parents=True)
        notes.write_text("# mine\n")
        link = mock_home / ".claude" / "CLAUDE.md"
        link.parent.mkdir()
        link.symlink_to(notes)

        _uninstall_config(config_dir)

        assert link.is_symlink()

    @pytest.mark.parametrize("stale", [False, True], ids=["current", "stale"])
    def test_removes_managed_manifest_destination(
        self, tmp_path, config_dir, mock_home, stale
    ):
        link = mock_home / ".claude" / "CLAUDE.md"
        link.parent.mkdir()
        link.symlink_to(
            _stale_package(tmp_path, "claude/CLAUDE.md")
            if stale
            else config_dir / "claude/CLAUDE.md"
        )

        _uninstall_config(config_dir)

        assert not link.is_symlink()

    def test_removes_link_to_merged_settings_cache_after_cache_is_gone(
        self, config_dir, mock_home
    ):
        (config_dir / "claude" / "settings.json").write_text("{}")
        link = mock_home / ".claude" / "settings.json"
        link.parent.mkdir()
        link.symlink_to(Config.get_cache_dir() / "claude" / "settings.json")

        _uninstall_config(config_dir)

        assert not link.is_symlink()


_PACK = "agents/teams/com.wpfleger.sietch-tabr"


@pytest.mark.unit
class TestDeprecatedUninstallOwnership:
    @pytest.fixture(autouse=True)
    def _linux_data_home(self, mock_home, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(mock_home / ".local" / "share"))
        monkeypatch.setattr(
            "ai_rules.agents.shared.is_platform", lambda platform: False
        )

    def _uninstall(self, config_dir: Path) -> None:
        config = Config(exclude_symlinks=[])
        _uninstall(
            ConfigComponent(),
            config_dir,
            ClaudeAgent(config_dir, config),
            SharedAgent(config_dir, config),
        )

    def _pack_link(self, mock_home: Path, target: Path) -> Path:
        link = mock_home / ".local/share/xyz.block.buzz.app" / _PACK
        link.parent.mkdir(parents=True)
        link.symlink_to(target, target_is_directory=True)
        return link

    def test_keeps_user_replacement_of_deprecated_location(
        self, tmp_path, config_dir, mock_home
    ):
        claude_md = mock_home / "CLAUDE.md"
        claude_md.symlink_to(_unrelated(tmp_path, "CLAUDE.md"))
        pack = self._pack_link(mock_home, _unrelated(tmp_path, "buzz"))

        self._uninstall(config_dir)

        assert claude_md.is_symlink()
        assert pack.is_symlink()

    @pytest.mark.parametrize("stale", [False, True], ids=["current", "stale"])
    def test_removes_deprecated_links_to_our_source(
        self, tmp_path, config_dir, mock_home, stale
    ):
        root = _stale_package(tmp_path, "") if stale else config_dir
        claude_md = mock_home / "CLAUDE.md"
        claude_md.symlink_to(root / "AGENTS.md")
        pack = self._pack_link(mock_home, root / "buzz")

        self._uninstall(config_dir)

        assert not claude_md.is_symlink()
        assert not pack.is_symlink()
