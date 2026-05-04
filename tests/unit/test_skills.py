"""Unit tests for skills module."""

import pytest

from ai_rules.skills import SkillManager


@pytest.mark.unit
class TestListBundledSkills:
    def test_returns_all_bundled_skills(self, tmp_path):
        config_dir = tmp_path / "config"
        skills_dir = config_dir / "skills"
        for name in ["skill-a", "skill-b"]:
            d = skills_dir / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Test {name}\n---\nBody"
            )

        manager = SkillManager(config_dir=config_dir, agent_id="")
        results = manager.list_bundled_skills()

        assert len(results) == 2
        names = {s.name for s in results}
        assert names == {"skill-a", "skill-b"}

    def test_handles_missing_frontmatter(self, tmp_path):
        config_dir = tmp_path / "config"
        d = config_dir / "skills" / "plain"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("Just plain markdown")

        manager = SkillManager(config_dir=config_dir, agent_id="")
        results = manager.list_bundled_skills()

        assert len(results) == 1
        assert results[0].name == "plain"

    def test_returns_empty_for_no_skills(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        manager = SkillManager(config_dir=config_dir, agent_id="")
        results = manager.list_bundled_skills()

        assert results == []


@pytest.mark.unit
class TestGetSkillContent:
    def test_returns_content(self, tmp_path):
        config_dir = tmp_path / "config"
        d = config_dir / "skills" / "test-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# Test Skill\nContent here")

        manager = SkillManager(config_dir=config_dir, agent_id="")
        content = manager.get_skill_content("test-skill")

        assert content == "# Test Skill\nContent here"

    def test_returns_none_for_unknown_skill(self, tmp_path):
        config_dir = tmp_path / "config"
        (config_dir / "skills").mkdir(parents=True)

        manager = SkillManager(config_dir=config_dir, agent_id="")
        content = manager.get_skill_content("nonexistent")

        assert content is None


@pytest.mark.unit
class TestGetSkillUrl:
    def test_returns_github_url(self):
        url = SkillManager.get_skill_url("research")

        assert url is not None
        assert "github.com/wpfleger96/ai-agent-rules" in url
        assert "skills/research/SKILL.md" in url
        assert "/blob/main/" in url


@pytest.mark.unit
class TestParseSkillMd:
    def test_parses_frontmatter(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A test skill\n---\nBody content"
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.name == "my-skill"
        assert result.description == "A test skill"
        assert result.body == "Body content"

    def test_handles_no_frontmatter(self, tmp_path):
        d = tmp_path / "plain"
        d.mkdir()
        (d / "SKILL.md").write_text("Just markdown")

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.name == "plain"
        assert result.body == "Just markdown"

    def test_returns_none_for_missing_file(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()

        result = SkillManager.parse_skill_md(d)

        assert result is None
