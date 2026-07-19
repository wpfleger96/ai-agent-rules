"""Integration tests for tool CLI commands."""

import pytest

from ai_rules.cli import main


@pytest.mark.integration
class TestToolList:
    def test_lists_managed_tools(self, runner):
        result = runner.invoke(main, ["tool", "list"])

        assert result.exit_code == 0
        assert "ai-agent-rules" in result.output
        assert "Managed Tools" in result.output


@pytest.mark.integration
class TestToolShow:
    def test_show_ai_agent_rules(self, runner, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_version",
            lambda _: "1.0.0",
        )
        result = runner.invoke(main, ["tool", "show", "ai-agent-rules"])

        assert result.exit_code == 0
        assert "ai-agent-rules" in result.output
        assert "Version:" in result.output

    def test_show_alias_ai_rules(self, runner):
        result = runner.invoke(main, ["tool", "show", "ai-rules"])

        assert result.exit_code == 0
        assert "ai-agent-rules" in result.output

    def test_show_unknown_tool_fails(self, runner):
        result = runner.invoke(main, ["tool", "show", "nonexistent"])

        assert result.exit_code == 1
        assert "Unknown tool" in result.output


@pytest.mark.integration
class TestToolSourceList:
    def test_lists_source_preferences(self, runner):
        result = runner.invoke(main, ["tool", "source", "list"])

        assert result.exit_code == 0
        assert "ai-agent-rules" in result.output
        assert "Tool Install Source Preferences" in result.output


@pytest.mark.integration
class TestToolSourceGet:
    def test_get_existing_tool(self, runner):
        result = runner.invoke(main, ["tool", "source", "get", "ai-agent-rules"])

        assert result.exit_code == 0
        assert "ai-agent-rules" in result.output

    def test_get_unknown_tool_fails(self, runner):
        result = runner.invoke(main, ["tool", "source", "get", "nonexistent"])

        assert result.exit_code == 1
        assert "Unknown tool" in result.output


@pytest.mark.integration
class TestToolSourceSet:
    def test_set_invalid_source_fails(self, runner):
        result = runner.invoke(
            main, ["tool", "source", "set", "ai-agent-rules", "invalid"]
        )

        assert result.exit_code == 1
        assert "Invalid source value" in result.output
