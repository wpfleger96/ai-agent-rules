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
        "attribution": {"commit": "", "pr": ""},
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

    def test_permissions_allow_array_merge_element_by_element(self):
        override = {"permissions": {"allow": ["Bash(dog:*)"]}}
        result = deep_merge(self.BASE, override)

        assert result["permissions"]["allow"][0] == "Bash(dog:*)"
        assert result["permissions"]["allow"][1] == "Read(*)"

    def test_attribution_partial_override(self):
        override = {"attribution": {"commit": "abc123"}}
        result = deep_merge(self.BASE, override)

        assert result["attribution"]["commit"] == "abc123"
        assert result["attribution"]["pr"] == ""

    def test_simultaneous_env_and_permissions_override(self):
        override = {
            "env": {"NEW_VAR": "x"},
            "permissions": {"defaultMode": "allow"},
        }
        result = deep_merge(self.BASE, override)

        assert result["env"]["NEW_VAR"] == "x"
        assert result["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet-4-6"
        assert result["permissions"]["defaultMode"] == "allow"
        assert result["permissions"]["allow"] == ["Bash(cat:*)", "Read(*)"]

    def test_deep_merge_does_not_mutate_base(self):
        base: dict[str, Any] = copy.deepcopy(self.BASE)
        override = {"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "changed"}}
        deep_merge(base, override)

        assert base["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet-4-6"


@pytest.mark.unit
class TestCodexDeepMerge:
    BASE = {
        "model": "gpt-5.4",
        "approval_policy": "on-request",
    }

    def test_flat_model_override(self):
        override = {"model": "gpt-5.2-codex"}
        result = deep_merge(self.BASE, override)

        assert result["model"] == "gpt-5.2-codex"
        assert result["approval_policy"] == "on-request"

    def test_new_key_added_to_flat_config(self):
        override = {"full_auto": True}
        result = deep_merge(self.BASE, override)

        assert result["full_auto"] is True
        assert result["model"] == "gpt-5.4"
        assert result["approval_policy"] == "on-request"

    def test_unrelated_keys_survive_merge(self):
        base = {**self.BASE, "projects": ["my-project"]}
        override = {"model": "gpt-5.2-codex"}
        result = deep_merge(base, override)

        assert result["projects"] == ["my-project"]
        assert result["model"] == "gpt-5.2-codex"


@pytest.mark.unit
class TestGeminiDeepMerge:
    BASE = {
        "context": {"fileName": ["GEMINI.md", "AGENTS.md"]},
        "tools": {"shell": {"enableInteractiveShell": False}},
        "ide": {"hasSeenNudge": True},
    }

    def test_model_block_added_when_absent_from_base(self):
        override = {"model": {"name": "gemini-3.1-pro-preview"}}
        result = deep_merge(self.BASE, override)

        assert result["model"]["name"] == "gemini-3.1-pro-preview"
        assert result["context"]["fileName"] == ["GEMINI.md", "AGENTS.md"]
        assert result["tools"]["shell"]["enableInteractiveShell"] is False
        assert result["ide"]["hasSeenNudge"] is True

    def test_security_auth_deep_nested_added(self):
        override = {"security": {"auth": {"selectedType": "gemini-api-key"}}}
        result = deep_merge(self.BASE, override)

        assert result["security"]["auth"]["selectedType"] == "gemini-api-key"
        assert "context" in result
        assert "tools" in result

    def test_ui_flag_added(self):
        override = {"ui": {"useFullWidth": True}}
        result = deep_merge(self.BASE, override)

        assert result["ui"]["useFullWidth"] is True
        assert result["context"]["fileName"] == ["GEMINI.md", "AGENTS.md"]

    def test_all_work_profile_overrides_simultaneous(self):
        override = {
            "model": {"name": "gemini-3.1-pro-preview"},
            "security": {"auth": {"selectedType": "gemini-api-key"}},
            "ui": {"useFullWidth": True},
        }
        result = deep_merge(self.BASE, override)

        assert result["model"]["name"] == "gemini-3.1-pro-preview"
        assert result["security"]["auth"]["selectedType"] == "gemini-api-key"
        assert result["ui"]["useFullWidth"] is True
        assert result["context"]["fileName"] == ["GEMINI.md", "AGENTS.md"]
        assert result["tools"]["shell"]["enableInteractiveShell"] is False
        assert result["ide"]["hasSeenNudge"] is True

    def test_tools_shell_nested_override(self):
        override = {"tools": {"shell": {"enableInteractiveShell": True}}}
        result = deep_merge(self.BASE, override)

        assert result["tools"]["shell"]["enableInteractiveShell"] is True
        assert "context" in result
        assert "ide" in result

    def test_context_filename_array_merge(self):
        override = {"context": {"fileName": ["ONLY.md"]}}
        result = deep_merge(self.BASE, override)

        assert result["context"]["fileName"][0] == "ONLY.md"
        assert result["context"]["fileName"][1] == "AGENTS.md"


@pytest.mark.unit
class TestGooseDeepMerge:
    BASE = {
        "GOOSE_MODEL": "claude-sonnet-4-6",
        "GOOSE_PROVIDER": "anthropic",
        "GOOSE_MODE": "auto",
        "ANTHROPIC_HOST": "https://api.anthropic.com",
        "OPENAI_BASE_PATH": "v1/chat/completions",
        "extensions": {
            "developer": {
                "enabled": True,
                "type": "builtin",
                "timeout": 300,
                "available_tools": ["tool_a", "tool_b"],
            },
            "memory": {
                "enabled": True,
                "type": "builtin",
                "timeout": 300,
            },
        },
    }

    def test_top_level_env_var_override(self):
        override = {"GOOSE_MODEL": "claude-opus-4-6"}
        result = deep_merge(self.BASE, override)

        assert result["GOOSE_MODEL"] == "claude-opus-4-6"
        assert result["GOOSE_PROVIDER"] == "anthropic"
        assert result["GOOSE_MODE"] == "auto"
        assert result["ANTHROPIC_HOST"] == "https://api.anthropic.com"
        assert result["extensions"]["developer"]["enabled"] is True

    def test_extension_dict_deep_merge(self):
        override = {"extensions": {"developer": {"enabled": False}}}
        result = deep_merge(self.BASE, override)

        assert result["extensions"]["developer"]["enabled"] is False
        assert result["extensions"]["developer"]["timeout"] == 300
        assert result["extensions"]["developer"]["type"] == "builtin"

    def test_new_extension_added(self):
        override = {"extensions": {"new_ext": {"enabled": True, "type": "platform"}}}
        result = deep_merge(self.BASE, override)

        assert "developer" in result["extensions"]
        assert "memory" in result["extensions"]
        assert result["extensions"]["new_ext"]["enabled"] is True

    def test_extension_available_tools_array_merge(self):
        override = {"extensions": {"developer": {"available_tools": ["tool_x"]}}}
        result = deep_merge(self.BASE, override)

        assert result["extensions"]["developer"]["available_tools"][0] == "tool_x"
        assert result["extensions"]["developer"]["available_tools"][1] == "tool_b"
