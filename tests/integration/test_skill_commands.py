"""Integration tests for skill CLI commands."""

import pytest

from click.testing import CliRunner

from ai_rules.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.integration
class TestSkillList:
    def test_lists_bundled_skills(self, runner):
        result = runner.invoke(main, ["skill", "list"])

        assert result.exit_code == 0
        assert "research" in result.output
        assert "code-reviewer" in result.output
        assert "prompt-engineer" in result.output

    def test_shows_descriptions(self, runner):
        result = runner.invoke(main, ["skill", "list"])

        assert result.exit_code == 0
        assert "Bundled Skills" in result.output


@pytest.mark.integration
class TestSkillShow:
    def test_show_renders_content(self, runner):
        result = runner.invoke(main, ["skill", "show", "research"])

        assert result.exit_code == 0
        assert "research" in result.output.lower()

    def test_show_raw_outputs_markdown(self, runner):
        result = runner.invoke(main, ["skill", "show", "research", "--raw"])

        assert result.exit_code == 0
        assert "---" in result.output
        assert "name: research" in result.output

    def test_show_url_outputs_github_link(self, runner):
        result = runner.invoke(main, ["skill", "show", "research", "--url"])

        assert result.exit_code == 0
        output = result.output.replace("\n", "")
        assert "github.com/wpfleger96/ai-agent-rules" in output
        assert "skills/research/SKILL.md" in output

    def test_show_nonexistent_skill_fails(self, runner):
        result = runner.invoke(main, ["skill", "show", "nonexistent"])

        assert result.exit_code == 1
        assert "Unknown skill" in result.output
        assert "research" in result.output

    def test_show_url_nonexistent_skill_fails(self, runner):
        result = runner.invoke(main, ["skill", "show", "nonexistent", "--url"])

        assert result.exit_code == 1
        assert "Unknown skill" in result.output
