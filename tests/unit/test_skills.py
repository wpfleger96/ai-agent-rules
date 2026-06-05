"""Unit tests for skills module."""

import importlib.metadata

from unittest.mock import MagicMock, patch

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
class TestGetRepoUrl:
    def test_returns_repo_url_from_metadata(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = [
            "Repository, https://github.com/wpfleger96/ai-agent-rules",
        ]
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager._get_repo_url()

        assert url == "https://github.com/wpfleger96/ai-agent-rules"

    def test_returns_none_when_package_not_found(self):
        with patch(
            "importlib.metadata.distribution",
            side_effect=importlib.metadata.PackageNotFoundError("ai-agent-rules"),
        ):
            url = SkillManager._get_repo_url()

        assert url is None

    def test_returns_none_when_no_repository_url_in_metadata(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = [
            "Homepage, https://example.com",
            "Documentation, https://docs.example.com",
        ]
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager._get_repo_url()

        assert url is None

    def test_returns_none_when_project_url_list_is_empty(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = []
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager._get_repo_url()

        assert url is None

    def test_skips_malformed_project_url_entries(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = [
            "malformed-no-comma",
            "Repository, https://github.com/wpfleger96/ai-agent-rules",
        ]
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager._get_repo_url()

        assert url == "https://github.com/wpfleger96/ai-agent-rules"

    def test_strips_trailing_slash_from_repo_url(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = [
            "Repository, https://github.com/wpfleger96/ai-agent-rules/",
        ]
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager._get_repo_url()

        assert url == "https://github.com/wpfleger96/ai-agent-rules"


@pytest.mark.unit
class TestGetDownloadUrl:
    def test_returns_url_for_all_skills_when_name_is_none(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = [
            "Repository, https://github.com/wpfleger96/ai-agent-rules",
        ]
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager.get_download_url()

        assert url is not None
        assert url.startswith("https://download-directory.github.io/?url=")
        assert "github.com/wpfleger96/ai-agent-rules" in url
        assert "/tree/main/src/ai_rules/config/skills" in url
        assert url.endswith("/tree/main/src/ai_rules/config/skills")

    def test_returns_url_for_specific_skill(self):
        mock_dist = MagicMock()
        mock_dist.metadata.get_all.return_value = [
            "Repository, https://github.com/wpfleger96/ai-agent-rules",
        ]
        with patch("importlib.metadata.distribution", return_value=mock_dist):
            url = SkillManager.get_download_url("research")

        assert url is not None
        assert url.startswith("https://download-directory.github.io/?url=")
        assert "/tree/main/src/ai_rules/config/skills/research" in url

    def test_returns_none_when_repo_url_unavailable(self):
        with patch(
            "importlib.metadata.distribution",
            side_effect=importlib.metadata.PackageNotFoundError("ai-agent-rules"),
        ):
            url = SkillManager.get_download_url("research")

        assert url is None

    def test_returns_none_for_all_skills_when_repo_url_unavailable(self):
        with patch(
            "importlib.metadata.distribution",
            side_effect=importlib.metadata.PackageNotFoundError("ai-agent-rules"),
        ):
            url = SkillManager.get_download_url()

        assert url is None


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

    def test_handles_no_frontmatter(self, tmp_path):
        d = tmp_path / "plain"
        d.mkdir()
        (d / "SKILL.md").write_text("Just markdown")

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.name == "plain"

    def test_returns_none_for_missing_file(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()

        result = SkillManager.parse_skill_md(d)

        assert result is None

    def test_parses_disabled_true(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: test\ndisabled: true\n---\n"
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.disabled is True

    def test_parses_disabled_false(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: test\ndisabled: false\n---\n"
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.disabled is False

    def test_disabled_missing_defaults_false(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: my-skill\ndescription: test\n---\n")

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.disabled is False

    def test_non_dict_frontmatter_returns_fallback(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\n---\nBody")

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.name == "my-skill"
        assert result.disabled is False

    def test_disabled_quoted_string_not_truthy(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\nname: my-skill\ndescription: test\ndisabled: "false"\n---\n'
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.disabled is False

    def test_disabled_quoted_true_string_not_truthy(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            '---\nname: my-skill\ndescription: test\ndisabled: "true"\n---\n'
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.disabled is False

    def test_parses_version_field(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\nversion: 1.0.0\ndescription: test\n---\n"
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.version == "1.0.0"

    def test_version_missing_defaults_none(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: my-skill\ndescription: test\n---\n")

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.version is None

    def test_version_numeric_coerced_to_string(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\nversion: 1.0\ndescription: test\n---\n"
        )

        result = SkillManager.parse_skill_md(d)

        assert result is not None
        assert result.version == "1.0"


@pytest.mark.unit
class TestIsSkillDisabled:
    def test_returns_true_for_disabled_skill(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: test\ndisabled: true\n---\n"
        )

        assert SkillManager.is_skill_disabled(d) is True

    def test_returns_false_for_enabled_skill(self, tmp_path):
        d = tmp_path / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: my-skill\ndescription: test\n---\n")

        assert SkillManager.is_skill_disabled(d) is False

    def test_returns_false_for_missing_skill_md(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()

        assert SkillManager.is_skill_disabled(d) is False


@pytest.mark.unit
class TestGetManagedSkillsDisabledFiltering:
    def test_excludes_disabled_skills(self, tmp_path):
        config_dir = tmp_path / "config"
        skills_dir = config_dir / "skills"

        enabled = skills_dir / "enabled-skill"
        enabled.mkdir(parents=True)
        (enabled / "SKILL.md").write_text(
            "---\nname: enabled-skill\ndescription: test\n---\n"
        )

        disabled = skills_dir / "disabled-skill"
        disabled.mkdir(parents=True)
        (disabled / "SKILL.md").write_text(
            "---\nname: disabled-skill\ndescription: test\ndisabled: true\n---\n"
        )

        manager = SkillManager(config_dir=config_dir, agent_id="")
        result = manager._get_managed_skills()

        assert "enabled-skill" in result
        assert "disabled-skill" not in result


@pytest.mark.unit
class TestListBundledSkillsDisabled:
    def test_excludes_disabled_by_default(self, tmp_path):
        config_dir = tmp_path / "config"
        skills_dir = config_dir / "skills"

        for name, disabled in [("active", False), ("inactive", True)]:
            d = skills_dir / name
            d.mkdir(parents=True)
            disabled_line = "\ndisabled: true" if disabled else ""
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: test{disabled_line}\n---\n"
            )

        manager = SkillManager(config_dir=config_dir, agent_id="")
        results = manager.list_bundled_skills()

        assert len(results) == 1
        assert results[0].name == "active"

    def test_includes_disabled_when_requested(self, tmp_path):
        config_dir = tmp_path / "config"
        skills_dir = config_dir / "skills"

        for name, disabled in [("active", False), ("inactive", True)]:
            d = skills_dir / name
            d.mkdir(parents=True)
            disabled_line = "\ndisabled: true" if disabled else ""
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: test{disabled_line}\n---\n"
            )

        manager = SkillManager(config_dir=config_dir, agent_id="")
        results = manager.list_bundled_skills(include_disabled=True)

        assert len(results) == 2
        names = {s.name for s in results}
        assert names == {"active", "inactive"}
        disabled_skill = next(s for s in results if s.name == "inactive")
        assert disabled_skill.disabled is True
