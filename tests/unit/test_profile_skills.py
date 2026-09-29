"""Profile-owned skills: additive to shared skills and removed when no longer deployed."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_rules.cli.components.skills import _enabled_skill_folders, _stale_skill_links
from ai_rules.config import Config
from ai_rules.profiles import ProfileError, ProfileLoader
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
    (root / "profiles" / "personal.yaml").write_text("name: personal\nskills: [mine]\n")
    (root / "profiles" / "work.yaml").write_text("name: work\nextends: personal\n")
    return root


def _ctx(config_dir: Path, **config: Any) -> Any:
    return SimpleNamespace(config_dir=config_dir, config=Config(**config))


def _install_links(ctx: Any, user_dir: Path) -> None:
    user_dir.mkdir(exist_ok=True)
    for folder in _enabled_skill_folders(ctx):
        (user_dir / folder.name).symlink_to(folder, target_is_directory=True)


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

    def test_shared_status_and_list_unchanged(self, config_dir, tmp_path):
        user_dir = tmp_path / "home_skills"
        _install_links(_ctx(config_dir, skills=["mine"]), user_dir)
        default = SkillManager(config_dir, "", [user_dir])
        personal = SkillManager(config_dir, "", [user_dir], profile_skills=["mine"])

        assert set(personal.get_status().managed_installed) == {"shared-a", "mine"}
        assert [s.name for s in personal.list_bundled_skills()] == ["shared-a", "mine"]
        assert [s.name for s in default.list_bundled_skills()] == ["shared-a"]


@pytest.mark.unit
class TestCleanup:
    def test_switch_to_default_removes_profile_skill(self, config_dir, tmp_path):
        user_dir = tmp_path / "home_skills"
        _install_links(_ctx(config_dir, skills=["mine"]), user_dir)

        default_ctx = _ctx(config_dir)
        stale = _stale_skill_links(default_ctx, user_dir)
        assert stale == [user_dir / "mine"]
        assert _stale_skill_links(_ctx(config_dir, skills=["mine"]), user_dir) == []

        for link in stale:
            link.unlink()
        manager = SkillManager(config_dir, "", [user_dir])
        status = manager.get_status()
        assert "mine" not in {
            *status.managed_installed,
            *status.managed_pending,
            *status.unmanaged,
        }
        assert "mine" not in [
            s.name for s in manager.list_bundled_skills(include_disabled=True)
        ]

    def test_excluded_shared_skill_link_removed(self, config_dir, tmp_path):
        user_dir = tmp_path / "home_skills"
        _install_links(_ctx(config_dir), user_dir)

        ctx = _ctx(config_dir, exclude_symlinks=[str(user_dir / "shared-a")])
        assert _stale_skill_links(ctx, user_dir) == [user_dir / "shared-a"]

    def test_unmanaged_links_untouched(self, config_dir, tmp_path):
        user_dir = tmp_path / "home_skills"
        user_dir.mkdir()
        (user_dir / "own").symlink_to(_skill(tmp_path / "elsewhere", "own"))
        assert _stale_skill_links(_ctx(config_dir), user_dir) == []


@pytest.mark.unit
class TestProfileSkillsField:
    def test_work_inherits_through_extends(self, config_dir):
        loader = ProfileLoader(profiles_dir=config_dir / "profiles")
        assert loader.load_profile("work").skills == ["mine"]
        assert loader.load_profile("default").skills == []

    def test_unknown_name_is_error(self, config_dir):
        (config_dir / "profiles" / "bad.yaml").write_text("name: bad\nskills: [nope]\n")
        with pytest.raises(ProfileError, match="unknown skill 'nope'"):
            ProfileLoader(profiles_dir=config_dir / "profiles").load_profile("bad")

    def test_collision_with_shared_skill_is_error(self, config_dir):
        _skill(config_dir / "profiles" / "skills", "shared-a")
        (config_dir / "profiles" / "bad.yaml").write_text(
            "name: bad\nskills: [shared-a]\n"
        )
        with pytest.raises(ProfileError, match="collides with a shared skill"):
            ProfileLoader(profiles_dir=config_dir / "profiles").load_profile("bad")
