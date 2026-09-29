"""Profile-owned skills: additive to shared skills and removed when no longer deployed."""

from pathlib import Path
from typing import Any

import click
import pytest

from rich.console import Console

from ai_rules.agents.shared import SharedAgent
from ai_rules.cli.components.skills import SkillsComponent, _stale_skill_links
from ai_rules.cli.context import CliContext
from ai_rules.cli.helpers import validate_profile_skills
from ai_rules.config import Config
from ai_rules.profiles import ProfileLoader
from ai_rules.skills import SkillManager, deployable_skills


def _skill(root: Path, name: str, extra: str = "") -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n{extra}---\n")
    return d


@pytest.fixture
def config_dir(tmp_path):
    root = tmp_path / "config"
    _skill(root / "skills", "shared-a")
    _skill(root / "skills", "shared-off", "disabled: true\n")
    _skill(root / "profiles" / "skills", "mine")
    _skill(root / "profiles" / "skills", "mine-off", "disabled: true\n")
    (root / "profiles" / "personal.yaml").write_text("name: personal\nskills: [mine]\n")
    (root / "profiles" / "work.yaml").write_text("name: work\nextends: personal\n")
    return root


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    d = tmp_path / "home_skills"
    d.mkdir()
    monkeypatch.setattr("ai_rules.config.get_agent_skills_dirs", lambda: {"claude": d})
    return d


def _ctx(config_dir: Path, **config: Any) -> CliContext:
    cfg = Config(**config)
    agent = SharedAgent(config_dir, cfg)
    return CliContext(
        console=Console(quiet=True),
        config_dir=config_dir,
        config=cfg,
        profile_name=None,
        all_targets=(agent,),
        selected_targets=(agent,),
        yes=True,
    )


def _plan_apply(ctx: CliContext) -> None:
    component = SkillsComponent()
    component.apply(ctx, component.plan(ctx))


def _install(ctx: CliContext) -> None:
    assert SkillsComponent().install(ctx).ok


WRITERS = pytest.mark.parametrize("write", [_plan_apply, _install])


def _links(user_dir: Path) -> set[str]:
    return {p.name for p in user_dir.iterdir()}


def _visible(config_dir: Path, user_dir: Path, profile_skills: list[str]) -> set[str]:
    manager = SkillManager(config_dir, "", [user_dir], profile_skills=profile_skills)
    status = manager.get_status()
    return {
        *status.managed_installed,
        *status.managed_pending,
        *status.unmanaged,
        *(s.name for s in manager.list_bundled_skills(include_disabled=True)),
        *(n for n in ["mine"] if manager.get_skill_content(n) is not None),
    }


@pytest.mark.unit
class TestAdditive:
    def test_shared_skills_unchanged_by_profile_skills(self, config_dir):
        default = deployable_skills(config_dir)
        personal = deployable_skills(config_dir, ["mine"])

        assert list(default) == ["shared-a"]
        assert {k: v for k, v in personal.items() if k != "mine"} == default
        assert personal["mine"] == config_dir / "profiles" / "skills" / "mine"

    def test_bundled_config_default_matches_shared_enabled_set(self):
        from ai_rules.cli import get_config_dir

        config_dir = get_config_dir()
        expected = sorted(
            d.name
            for d in (config_dir / "skills").iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and not SkillManager.is_skill_disabled(d)
        )
        assert sorted(deployable_skills(config_dir)) == expected

    @WRITERS
    def test_default_and_personal_deploy_same_shared_set(
        self, config_dir, user_dir, write
    ):
        write(_ctx(config_dir))
        assert _links(user_dir) == {"shared-a"}
        write(_ctx(config_dir, skills=["mine"]))
        assert _links(user_dir) == {"shared-a", "mine"}
        assert [
            s.name
            for s in SkillManager(config_dir, "").list_bundled_skills(
                include_disabled=True
            )
        ] == ["shared-a", "shared-off"]


@pytest.mark.unit
class TestWriters:
    @WRITERS
    def test_switch_to_default_removes_profile_skill(self, config_dir, user_dir, write):
        write(_ctx(config_dir, skills=["mine"]))
        assert (user_dir / "mine").is_symlink()

        write(_ctx(config_dir))
        assert _links(user_dir) == {"shared-a"}
        assert "mine" not in _visible(config_dir, user_dir, [])

    @WRITERS
    def test_excluded_shared_skill_link_removed(self, config_dir, user_dir, write):
        write(_ctx(config_dir))
        write(_ctx(config_dir, exclude_symlinks=[str(user_dir / "shared-a")]))
        assert not (user_dir / "shared-a").exists()

    @WRITERS
    def test_disabled_profile_skill_never_deployed(self, config_dir, user_dir, write):
        write(_ctx(config_dir, skills=["mine-off"]))
        assert _links(user_dir) == {"shared-a"}

    @WRITERS
    def test_profile_only_config_dir(self, tmp_path, user_dir, write):
        root = tmp_path / "profile-only"
        _skill(root / "profiles" / "skills", "mine")
        write(_ctx(root, skills=["mine"]))
        assert _links(user_dir) == {"mine"}
        write(_ctx(root))
        assert _links(user_dir) == set()

    def test_uninstall_removes_profile_skill(self, config_dir, user_dir):
        ctx = _ctx(config_dir, skills=["mine"])
        _install(ctx)
        SkillsComponent().uninstall(ctx)
        assert _links(user_dir) == set()


@pytest.mark.unit
class TestUserLinksPreserved:
    """Links main never removed must survive the new removal rules."""

    def test_unrelated_path_with_package_marker(self, config_dir, tmp_path, user_dir):
        own = _skill(tmp_path / "my-ai-rules-notes", "own")
        (user_dir / "own").symlink_to(own)
        assert _stale_skill_links(_ctx(config_dir), user_dir) == []
        _install(_ctx(config_dir))
        assert (user_dir / "own").resolve() == own.resolve()

    def test_alias_to_shared_skill(self, config_dir, user_dir):
        (user_dir / "alias").symlink_to(config_dir / "skills" / "shared-a")
        assert _stale_skill_links(_ctx(config_dir), user_dir) == []
        _install(_ctx(config_dir))
        assert (user_dir / "alias").is_symlink()

    def test_old_install_shared_link_kept_like_main(
        self, tmp_path, config_dir, user_dir
    ):
        old = _skill(
            tmp_path / "old-venv" / "ai_rules" / "config" / "skills", "retired"
        )
        (user_dir / "retired").symlink_to(old)
        _install(_ctx(config_dir))
        assert (user_dir / "retired").is_symlink()

    def test_stale_bundled_install_path_still_removed(
        self, tmp_path, config_dir, user_dir
    ):
        old = _skill(
            tmp_path / "old-venv" / "ai_rules" / "config" / "profiles" / "skills",
            "gone",
        )
        (user_dir / "gone").symlink_to(old)
        assert _stale_skill_links(_ctx(config_dir), user_dir) == [user_dir / "gone"]


@pytest.mark.unit
class TestValidation:
    def test_work_inherits_through_extends(self, config_dir):
        loader = ProfileLoader(profiles_dir=config_dir / "profiles")
        assert loader.load_profile("work").skills == ["mine"]
        assert loader.load_profile("default").skills == []

    def test_unknown_name_is_error(self, config_dir):
        with pytest.raises(click.ClickException, match="unknown profile skill 'nope'"):
            validate_profile_skills(config_dir, ["nope"])

    def test_collision_with_shared_skill_is_error(self, config_dir):
        _skill(config_dir / "profiles" / "skills", "shared-a")
        with pytest.raises(click.ClickException, match="collides with a shared skill"):
            validate_profile_skills(config_dir, ["shared-a"])

    def test_escape_outside_profile_skills_is_error(self, config_dir):
        outside = _skill(config_dir / "profiles", "outside")
        (config_dir / "profiles" / "skills" / "outside").symlink_to(outside)
        with pytest.raises(click.ClickException, match="unknown profile skill"):
            validate_profile_skills(config_dir, ["outside"])

    @pytest.mark.parametrize("name", ["", ".", "..", ".hidden", "a/b", "a\\b"])
    def test_path_shaped_names_rejected(self, config_dir, name):
        with pytest.raises(click.ClickException, match="invalid profile skill name"):
            validate_profile_skills(config_dir, [name])

    def test_loader_accepts_any_names(self, config_dir):
        (config_dir / "profiles" / "bad.yaml").write_text(
            "name: bad\nskills: ['../outside']\n"
        )
        loader = ProfileLoader(profiles_dir=config_dir / "profiles")
        assert loader.load_profile("bad").skills == ["../outside"]

    def test_source_alias_with_different_name_rejected(self, config_dir):
        (config_dir / "profiles" / "skills" / "alias").symlink_to("mine")
        with pytest.raises(click.ClickException, match="unknown profile skill 'alias'"):
            validate_profile_skills(config_dir, ["alias"])


@pytest.mark.unit
def test_skill_urls_follow_source_dir(monkeypatch):
    monkeypatch.setattr(SkillManager, "_get_repo_url", staticmethod(lambda: "R"))
    assert (
        SkillManager.get_skill_url("x")
        == "R/blob/main/src/ai_rules/config/skills/x/SKILL.md"
    )
    assert (
        SkillManager.get_skill_url("x", Path("profiles/skills"))
        == "R/blob/main/src/ai_rules/config/profiles/skills/x/SKILL.md"
    )
    download = SkillManager.get_download_url("x", Path("profiles/skills"))
    assert download is not None
    assert download.endswith("tree/main/src/ai_rules/config/profiles/skills/x")


@pytest.mark.unit
def test_hidden_shared_skill_readers_match_main(config_dir, user_dir):
    _skill(config_dir / "skills", ".hidden")
    manager = SkillManager(config_dir, "", [user_dir])
    assert manager.get_skill_content(".hidden") is not None
    assert ".hidden" in manager.get_status().managed_pending
    assert ".hidden" not in deployable_skills(config_dir)


@pytest.fixture
def cli(tmp_path, monkeypatch, config_dir, user_dir):
    """Real Click commands against an isolated HOME and the fixture profiles."""
    from click.testing import CliRunner

    from ai_rules.cli import main

    home = (tmp_path / "home").resolve()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    init = ProfileLoader.__init__
    monkeypatch.setattr(
        ProfileLoader,
        "__init__",
        lambda self, profiles_dir=None: init(
            self, profiles_dir or config_dir / "profiles"
        ),
    )
    monkeypatch.setattr("ai_rules.cli.get_config_dir", lambda: config_dir)

    def run(*args: str) -> Any:
        Config._load_cached.cache_clear()  # each call is a fresh process in production
        return CliRunner().invoke(main, list(args))

    return run, home


def _set_profile_skills(config_dir: Path, skills: str) -> None:
    (config_dir / "profiles" / "personal.yaml").write_text(
        f"name: personal\nskills: {skills}\n"
    )


@pytest.mark.unit
class TestCommands:
    def test_rejected_install_changes_nothing(self, cli, config_dir, user_dir):
        run, home = cli
        assert (
            run("install", "--profile", "default", "-y", "--only", "skills").exit_code
            == 0
        )
        state = (home / ".ai-agent-rules" / "state.yaml").read_bytes()
        links = _links(user_dir)
        _set_profile_skills(config_dir, "[missing]")

        result = run("install", "--profile", "personal", "-y", "--only", "skills")
        assert result.exit_code == 1
        assert "unknown profile skill 'missing'" in result.output
        assert (home / ".ai-agent-rules" / "state.yaml").read_bytes() == state
        assert _links(user_dir) == links

    @pytest.mark.parametrize("broken", ["[mine, missing]", "['../outside']"])
    def test_uninstall_ignores_broken_profile(self, cli, config_dir, user_dir, broken):
        run, _ = cli
        assert (
            run("install", "--profile", "personal", "-y", "--only", "skills").exit_code
            == 0
        )
        assert "mine" in _links(user_dir)
        _set_profile_skills(config_dir, broken)

        result = run("uninstall", "-y", "--only", "skills")
        assert result.exit_code == 0, result.output
        assert _links(user_dir) == set()

    def test_list_agents_rejects_broken_profile(self, cli, config_dir):
        run, _ = cli
        assert (
            run("install", "--profile", "personal", "-y", "--only", "skills").exit_code
            == 0
        )
        _set_profile_skills(config_dir, "[mine, missing]")
        result = run("list-agents")
        assert result.exit_code == 1, result.output
        assert "unknown profile skill 'missing'" in result.output
