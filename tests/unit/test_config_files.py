from importlib.resources import files as resource_files
from pathlib import Path

import pytest

from ai_rules.config import load_config_file
from ai_rules.profiles import ProfileLoader


@pytest.fixture(scope="module")
def config_root():
    return Path(str(resource_files("ai_rules") / "config"))


@pytest.fixture(scope="module")
def amp_config(config_root):
    return load_config_file(config_root / "amp" / "settings.json", "json")


@pytest.fixture(scope="module")
def claude_config(config_root):
    return load_config_file(config_root / "claude" / "settings.json", "json")


@pytest.fixture(scope="module")
def codex_config(config_root):
    return load_config_file(config_root / "codex" / "config.toml", "toml")


@pytest.fixture(scope="module")
def gemini_config(config_root):
    return load_config_file(config_root / "gemini" / "settings.json", "json")


@pytest.fixture(scope="module")
def goose_config(config_root):
    return load_config_file(config_root / "goose" / "config.yaml", "yaml")


@pytest.mark.unit
@pytest.mark.config
class TestConfigFileSyntax:
    @pytest.mark.parametrize(
        "agent,filename,fmt",
        [
            ("amp", "settings.json", "json"),
            ("claude", "settings.json", "json"),
            ("codex", "config.toml", "toml"),
            ("gemini", "settings.json", "json"),
            ("goose", "config.yaml", "yaml"),
        ],
    )
    def test_config_file_exists(self, config_root, agent, filename, fmt):
        assert (config_root / agent / filename).is_file()

    @pytest.mark.parametrize(
        "agent,filename,fmt",
        [
            ("amp", "settings.json", "json"),
            ("claude", "settings.json", "json"),
            ("codex", "config.toml", "toml"),
            ("gemini", "settings.json", "json"),
            ("goose", "config.yaml", "yaml"),
        ],
    )
    def test_config_file_parseable(self, config_root, agent, filename, fmt):
        result = load_config_file(config_root / agent / filename, fmt)
        assert isinstance(result, dict)
        assert len(result) > 0


@pytest.mark.unit
@pytest.mark.config
class TestConfigFileStructuralInvariants:
    def test_amp_settings_keys_are_prefixed(self, amp_config):
        for key in amp_config:
            assert key.startswith("amp."), (
                f"Amp setting key {key!r} missing amp. prefix"
            )

    def test_amp_has_anthropic_effort_max(self, amp_config):
        assert amp_config["amp.anthropic.effort"] == "max"

    def test_amp_has_interleaved_thinking(self, amp_config):
        assert amp_config["amp.anthropic.interleavedThinking.enabled"] is True

    def test_amp_has_notifications_enabled(self, amp_config):
        assert amp_config["amp.notifications.enabled"] is True
        assert amp_config["amp.notifications.system.enabled"] is True

    def test_amp_has_permissions_deny_rules(self, amp_config):
        permissions = amp_config["amp.permissions"]
        assert isinstance(permissions, list)
        assert len(permissions) > 0
        reject_cmds = []
        for rule in permissions:
            if rule.get("action") == "reject":
                reject_cmds.extend(rule["matches"]["cmd"])
        assert any("rm -rf" in cmd for cmd in reject_cmds)
        assert any("git push --force" in cmd for cmd in reject_cmds)
        assert any("gh pr merge" in cmd for cmd in reject_cmds)

    def test_claude_has_env_and_permissions(self, claude_config):
        assert isinstance(claude_config["env"], dict)
        assert isinstance(claude_config["permissions"], dict)

    def test_claude_env_has_required_model_vars(self, claude_config):
        env = claude_config["env"]
        assert "ANTHROPIC_DEFAULT_OPUS_MODEL" in env
        assert "ANTHROPIC_DEFAULT_SONNET_MODEL" in env
        assert "CLAUDE_CODE_SUBAGENT_MODEL" in env
        assert "CLAUDE_CODE_EFFORT_LEVEL" in env

    def test_claude_permissions_has_allow_and_deny_lists(self, claude_config):
        perms = claude_config["permissions"]
        assert isinstance(perms["allow"], list)
        assert isinstance(perms["deny"], list)

    def test_gemini_has_context_and_tools(self, gemini_config):
        assert "context" in gemini_config
        assert "tools" in gemini_config

    def test_gemini_context_has_filename_list(self, gemini_config):
        filenames = gemini_config["context"]["fileName"]
        assert isinstance(filenames, list)
        assert len(filenames) > 0

    def test_codex_has_required_flat_keys(self, codex_config):
        assert "model" in codex_config
        assert "approval_policy" in codex_config

    def test_codex_default_model_is_gpt_5_5(self, codex_config):
        assert codex_config["model"] == "gpt-5.5"

    def test_codex_approval_policy_is_untrusted(self, codex_config):
        assert codex_config["approval_policy"] == "untrusted"

    def test_codex_has_reasoning_effort(self, codex_config):
        assert codex_config["model_reasoning_effort"] == "xhigh"

    def test_codex_has_plan_mode_reasoning_effort(self, codex_config):
        assert codex_config["plan_mode_reasoning_effort"] == "xhigh"

    def test_codex_has_reasoning_summary(self, codex_config):
        assert codex_config["model_reasoning_summary"] == "detailed"

    def test_codex_has_commit_attribution_empty(self, codex_config):
        assert codex_config["commit_attribution"] == ""

    def test_codex_has_history_persistence(self, codex_config):
        assert codex_config["history"]["persistence"] == "save-all"

    def test_codex_has_analytics_disabled(self, codex_config):
        assert codex_config["analytics"]["enabled"] is False

    def test_codex_has_status_line_defaults(self, codex_config):
        assert codex_config["tui"]["status_line"] == [
            "model-with-reasoning",
            "project-name",
            "git-branch",
            "context-used",
            "used-tokens",
            "session-id",
        ]

    def test_gemini_has_approval_mode(self, gemini_config):
        assert gemini_config["general"]["defaultApprovalMode"] == "auto_edit"

    def test_gemini_has_session_retention_disabled(self, gemini_config):
        assert gemini_config["general"]["sessionRetention"]["enabled"] is False

    def test_gemini_has_tools_allowed_list(self, gemini_config):
        allowed = gemini_config["tools"]["allowed"]
        assert isinstance(allowed, list)
        assert len(allowed) > 0
        assert all(a.startswith("run_shell_command(") for a in allowed)

    def test_gemini_tools_allowed_excludes_mutable_commands(self, gemini_config):
        allowed = gemini_config["tools"]["allowed"]
        dangerous = [
            "run_shell_command(git)",
            "run_shell_command(gh)",
            "run_shell_command(docker)",
            "run_shell_command(rm)",
            "run_shell_command(curl)",
            "run_shell_command(npm)",
            "run_shell_command(pip)",
        ]
        for cmd in dangerous:
            assert cmd not in allowed

    def test_gemini_has_inline_thinking_full(self, gemini_config):
        assert gemini_config["ui"]["inlineThinkingMode"] == "full"

    def test_goose_telemetry_disabled(self, goose_config):
        assert goose_config["GOOSE_TELEMETRY_ENABLED"] is False

    def test_goose_has_extensions_dict(self, goose_config):
        assert isinstance(goose_config["extensions"], dict)

    def test_goose_has_model_and_provider(self, goose_config):
        assert isinstance(goose_config["GOOSE_MODEL"], str)
        assert isinstance(goose_config["GOOSE_PROVIDER"], str)

    def test_goose_extensions_each_have_enabled_and_type(self, goose_config):
        for name, ext in goose_config["extensions"].items():
            assert isinstance(ext["enabled"], bool), f"{name} missing bool 'enabled'"
            assert isinstance(ext["type"], str), f"{name} missing str 'type'"


@pytest.mark.unit
class TestProfileFileSyntax:
    @pytest.mark.parametrize("profile_name", ["default", "work", "personal"])
    def test_bundled_profiles_load_without_error(self, profile_name):
        loader = ProfileLoader()
        profile = loader.load_profile(profile_name)
        assert profile is not None
        assert profile.name == profile_name

    def test_default_profile_has_empty_settings_overrides(self):
        loader = ProfileLoader()
        profile = loader.load_profile("default")
        assert profile.settings_overrides == {}

    def test_work_profile_overrides_claude_and_gemini(self):
        loader = ProfileLoader()
        profile = loader.load_profile("work")
        assert "claude" in profile.settings_overrides
        assert "gemini" in profile.settings_overrides

    def test_work_profile_excludes_goose_config(self):
        loader = ProfileLoader()
        profile = loader.load_profile("work")
        assert "~/.config/goose/config.yaml" in profile.exclude_symlinks

    def test_work_profile_has_codex_fast_mode(self):
        loader = ProfileLoader()
        profile = loader.load_profile("work")
        assert "codex" in profile.settings_overrides
        codex = profile.settings_overrides["codex"]
        assert codex.get("service_tier") == "fast"
        assert codex.get("features", {}).get("fast_mode") is True
