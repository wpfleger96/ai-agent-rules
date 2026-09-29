"""Uninstall removes only links ai-rules created, never user-created links.

A link is ai-rules' only when its raw target is the expected source entry, or
the same entry inside an older package install (``.../ai_rules/config/...``).
"""

from __future__ import annotations

import os

from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.codex import CodexAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.claude_extensions import ClaudeExtensionManager
from ai_rules.cli.components.config import ConfigComponent
from ai_rules.cli.components.extensions import ClaudeExtensionsComponent
from ai_rules.cli.components.settings import SettingsComponent
from ai_rules.cli.components.skills import SkillsComponent
from ai_rules.cli.context import CliContext, Component
from ai_rules.config import Config, get_managed_fields_path
from ai_rules.targets.base import ConfigTarget
from ai_rules.utils import links_to_source


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
        real_readlink, real_resolve = os.readlink, Path.resolve

        def fail_for_link(path: Path) -> None:
            if path == link:
                raise OSError("unreadable")

        def readlink(path: Path) -> str:
            fail_for_link(Path(path))
            return real_readlink(path)

        def resolve(self: Path, strict: bool = False) -> Path:
            fail_for_link(self)
            return real_resolve(self, strict)

        monkeypatch.setattr(os, "readlink", readlink)
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
class TestSymlinkedHomeOwnership:
    """HOME reached through a symlink at a different depth than the real home.

    The alias sits in ``config/skills`` so that ``../../../<name>`` from the
    link's spelled directory lands on the bundled skill, while from its real
    directory it lands in the user's own folder.
    """

    @pytest.fixture
    def alias_skills_dir(self, tmp_path, config_dir, monkeypatch):
        real_home = tmp_path / "real" / "deep" / "home"
        (real_home / ".agents" / "skills").mkdir(parents=True)
        alias = config_dir / "skills" / "home"
        alias.symlink_to(real_home, target_is_directory=True)
        monkeypatch.setenv("HOME", str(alias))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: alias))
        return alias / ".agents" / "skills"

    def test_keeps_healthy_link_that_only_lexically_reaches_source(
        self, tmp_path, config_dir, alias_skills_dir
    ):
        (tmp_path / "real" / "deep" / "research").mkdir()
        link = alias_skills_dir / "research"
        link.symlink_to("../../../research")

        _uninstall_skills(config_dir)

        assert link.is_symlink()

    def test_removes_relative_link_physically_reaching_source(
        self, tmp_path, config_dir, alias_skills_dir
    ):
        real_dir = (tmp_path / "real/deep/home/.agents/skills").resolve()
        source = (config_dir / "skills" / "research").resolve()
        link = alias_skills_dir / "research"
        link.symlink_to(os.path.relpath(source, real_dir))

        _uninstall_skills(config_dir)

        assert not link.is_symlink()


@pytest.mark.unit
class TestSourceSpelledThroughSymlinkThenParent:
    """``HOME=alias/../home`` where ``alias`` is a symlink to a deeper folder.

    Lexically the source is ``<root>/home/...``; physically it is
    ``<root>/physical/home/...``. Only the physical one is ours.
    """

    def test_matches_physical_source_not_lexical_one(self, tmp_path):
        (tmp_path / "physical" / "deep").mkdir(parents=True)
        (tmp_path / "alias").symlink_to(tmp_path / "physical" / "deep")
        cache = ".ai-agent-rules/cache/claude/settings.json"
        source = tmp_path / "alias" / ".." / "home" / cache
        for home in ("home", "physical/home"):
            (tmp_path / home / cache).parent.mkdir(parents=True)
            (tmp_path / home / cache).write_text("{}")
        (tmp_path / "unrelated").mkdir()
        unrelated = tmp_path / "unrelated" / "settings.json"
        unrelated.symlink_to(tmp_path / "home" / cache)
        (tmp_path / "ours").mkdir()
        ours = tmp_path / "ours" / "settings.json"
        ours.symlink_to(tmp_path / "physical" / "home" / cache)

        assert not links_to_source(unrelated, source)
        assert links_to_source(ours, source)


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

    def test_removes_deprecated_link_to_source_that_is_itself_an_alias(
        self, tmp_path, config_dir, mock_home
    ):
        external = tmp_path / "dotfiles" / "AGENTS.md"
        external.parent.mkdir(parents=True)
        external.write_text("# shared\n")
        (config_dir / "AGENTS.md").unlink()
        (config_dir / "AGENTS.md").symlink_to(external)
        claude_md = mock_home / "CLAUDE.md"
        claude_md.symlink_to(config_dir / "AGENTS.md")

        self._uninstall(config_dir)

        assert not claude_md.is_symlink()


@pytest.mark.unit
class TestManifestSourceRoles:
    """Only settings and the shared AGENTS.md accept bundled and cache forms."""

    def test_keeps_codex_instructions_pointing_at_shared_agents_md(
        self, config_dir, mock_home
    ):
        (config_dir / "codex").mkdir()
        (config_dir / "codex" / "AGENTS.md").write_text("# codex\n")
        link = mock_home / ".codex" / "AGENTS.md"
        link.parent.mkdir()
        link.symlink_to(config_dir / "AGENTS.md")

        config = Config(exclude_symlinks=[])
        _uninstall(ConfigComponent(), config_dir, CodexAgent(config_dir, config))

        assert link.is_symlink()

    def test_keeps_claude_instructions_pointing_at_cache(self, config_dir, mock_home):
        link = mock_home / ".claude" / "CLAUDE.md"
        link.parent.mkdir()
        link.symlink_to(Config.get_cache_dir() / "claude" / "CLAUDE.md")

        _uninstall_config(config_dir)

        assert link.is_symlink()

    @pytest.mark.parametrize("form", ["bundled", "cache"])
    def test_removes_settings_link_in_either_form(self, config_dir, mock_home, form):
        (config_dir / "claude" / "settings.json").write_text("{}")
        link = mock_home / ".claude" / "settings.json"
        link.parent.mkdir()
        link.symlink_to(
            config_dir / "claude" / "settings.json"
            if form == "bundled"
            else Config.get_cache_dir() / "claude" / "settings.json"
        )

        _uninstall_config(config_dir)

        assert not link.is_symlink()

    @pytest.mark.parametrize("form", ["bundled", "cache"])
    def test_removes_shared_agents_md_link_in_either_form(
        self, config_dir, mock_home, form
    ):
        link = mock_home / "AGENTS.md"
        link.symlink_to(
            config_dir / "AGENTS.md"
            if form == "bundled"
            else Config.get_cache_dir() / "shared" / "AGENTS.md"
        )

        config = Config(exclude_symlinks=[])
        _uninstall(ConfigComponent(), config_dir, SharedAgent(config_dir, config))

        assert not link.is_symlink()


@pytest.mark.unit
class TestGeneratedFileCleanup:
    def test_keeps_user_symlink_at_managed_fields_tracker(
        self, tmp_path, config_dir, mock_home
    ):
        mine = _unrelated(tmp_path, "managed-fields.json")
        mine.parent.mkdir(parents=True)
        mine.write_text("{}")
        tracker = get_managed_fields_path()
        tracker.parent.mkdir(parents=True, exist_ok=True)
        tracker.symlink_to(mine)

        _uninstall(SettingsComponent(), config_dir)

        assert tracker.is_symlink()
        assert mine.read_text() == "{}"
