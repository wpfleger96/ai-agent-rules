import copy

from typing import Any

import pytest

from ai_rules.utils import deep_merge


@pytest.mark.unit
class TestClaudeDeepMerge:
    BASE = {
        "env": {
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
            "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-4-6",
            "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
            "CLAUDE_CODE_EFFORT_LEVEL": "max",
        },
        "permissions": {
            "allow": ["Bash(cat:*)", "Read(*)"],
            "deny": ["rm -rf:*"],
            "defaultMode": "plan",
        },
    }

    def test_env_override_preserves_sibling_keys(self):
        override = {
            "env": {
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6[1m]",
                "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-4-6[1m]",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6[1m]",
            }
        }
        result = deep_merge(self.BASE, override)

        assert (
            result["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet-4-6[1m]"
        )
        assert result["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "claude-sonnet-4-6[1m]"
        assert result["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "claude-opus-4-6[1m]"
        assert (
            result["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"]
            == "claude-haiku-4-5-20251001"
        )
        assert result["env"]["CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING"] == "1"
        assert result["env"]["CLAUDE_CODE_EFFORT_LEVEL"] == "max"
        assert len(result["env"]) == 6

    def test_env_new_key_added(self):
        override = {"env": {"NEW_CUSTOM_VAR": "custom_value"}}
        result = deep_merge(self.BASE, override)

        assert result["env"]["NEW_CUSTOM_VAR"] == "custom_value"
        assert len(result["env"]) == 7
        assert result["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet-4-6"

    def test_permissions_allow_array_replaced_wholesale(self):
        override = {"permissions": {"allow": ["Bash(dog:*)"]}}
        result = deep_merge(self.BASE, override)

        assert result["permissions"]["allow"] == ["Bash(dog:*)"]

    def test_deep_merge_does_not_mutate_base(self):
        base: dict[str, Any] = copy.deepcopy(self.BASE)
        override = {"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "changed"}}
        deep_merge(base, override)

        assert base["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet-4-6"


@pytest.mark.unit
class TestGeminiDeepMerge:
    BASE = {
        "context": {"fileName": ["GEMINI.md", "AGENTS.md"]},
        "tools": {"shell": {"enableInteractiveShell": False}},
        "ide": {"hasSeenNudge": True},
    }

    def test_tools_shell_nested_override(self):
        override = {"tools": {"shell": {"enableInteractiveShell": True}}}
        result = deep_merge(self.BASE, override)

        assert result["tools"]["shell"]["enableInteractiveShell"] is True
        assert "context" in result
        assert "ide" in result
