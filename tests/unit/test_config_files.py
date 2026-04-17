from importlib.resources import files as resource_files
from pathlib import Path

import pytest

from ai_rules.config import load_config_file
from ai_rules.profiles import ProfileLoader


@pytest.fixture(scope="module")
def config_root():
    return Path(str(resource_files("ai_rules") / "config"))


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
        assert "trust_level" in codex_config

    def test_codex_approval_policy_is_valid_value(self, codex_config):
        assert codex_config["approval_policy"] in {
            "on-request",
            "never",
            "always",
            "auto",
        }

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
