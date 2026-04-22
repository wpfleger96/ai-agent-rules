import sys

from pathlib import Path

import pytest
import yaml

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.codex import CodexAgent
from ai_rules.config import (
    Config,
    navigate_path,
    parse_setting_path,
    validate_override_path,
)


@pytest.fixture
def cache_setup(tmp_path, monkeypatch):
    """Shared fixture for cache management tests."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    config_dir = tmp_path / "config"
    claude_dir = config_dir / "claude"
    claude_dir.mkdir(parents=True)

    base_settings_path = claude_dir / "settings.json"
    base_settings_path.write_text('{"model": "claude-opus-4-20250514"}')

    config = Config(
        settings_overrides={"claude": {"model": "claude-sonnet-4-5-20250929"}}
    )

    agent = ClaudeAgent(config_dir, config)

    return {
        "home": home,
        "base_settings_path": base_settings_path,
        "config": config,
        "config_dir": config_dir,
        "agent": agent,
        "repo_root": tmp_path,
    }


@pytest.mark.unit
@pytest.mark.config
class TestConfigLoading:
    """Test configuration file loading.

    Note: As of v0.5.0, only user-level config (~/.ai-agent-rules-config.yaml) is supported.
    Repo-level config support was removed.
    """

    def test_loads_user_config_only(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        user_config = home / ".ai-agent-rules-config.yaml"
        user_config.write_text(
            "version: 1\nexclude_symlinks:\n  - ~/.config/goose/config.yaml\n"
        )

        config = Config.load()

        assert "~/.config/goose/config.yaml" in config.exclude_symlinks

    def test_handles_missing_config_files(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        config = Config.load()

        assert len(config.exclude_symlinks) == 0

    def test_handles_invalid_yaml(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        user_config = home / ".ai-agent-rules-config.yaml"
        user_config.write_text("invalid: yaml: content: [[[")

        with pytest.raises(yaml.YAMLError):
            Config.load()


@pytest.mark.unit
@pytest.mark.config
class TestExcludeSymlinks:
    """Test symlink exclusion filtering."""

    def test_exact_match_excluded(self, tmp_path):
        config = Config(exclude_symlinks=["~/.claude/settings.json"])

        assert config.is_excluded("~/.claude/settings.json")

    def test_non_matching_path_not_excluded(self, tmp_path):
        config = Config(exclude_symlinks=["~/.claude/settings.json"])

        assert not config.is_excluded("~/.claude/agents/test.md")

    def test_multiple_exclusions(self, tmp_path):
        config = Config(
            exclude_symlinks=[
                "~/.claude/settings.json",
                "~/.config/goose/config.yaml",
            ]
        )

        assert config.is_excluded("~/.claude/settings.json")
        assert config.is_excluded("~/.config/goose/config.yaml")
        assert not config.is_excluded("~/.claude/agents/test.md")

    def test_absolute_path_exclusion(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        config = Config(exclude_symlinks=[str(home / ".claude" / "settings.json")])

        assert config.is_excluded(str(home / ".claude" / "settings.json"))

    def test_glob_pattern_matching(self, tmp_path, monkeypatch):
        """Test that glob patterns work for exclusions."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        config = Config(exclude_symlinks=["~/.claude/*.json"])

        assert config.is_excluded("~/.claude/settings.json")
        assert config.is_excluded("~/.claude/debug.json")
        assert not config.is_excluded("~/.claude/agents/test.md")

    def test_glob_pattern_with_recursive(self, tmp_path, monkeypatch):
        """Test recursive glob patterns."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        config = Config(exclude_symlinks=["~/.config/**/*.yaml"])

        assert config.is_excluded("~/.config/goose/config.yaml")
        assert config.is_excluded("~/.config/deep/nested/file.yaml")
        assert not config.is_excluded("~/.config/goose/file.json")

    def test_exact_match_preferred_over_glob(self, tmp_path, monkeypatch):
        """Test that exact matches still work when glob patterns are also present."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        config = Config(
            exclude_symlinks=[
                "~/.claude/settings.json",  # Exact
                "~/.claude/*.md",  # Glob
            ]
        )

        assert config.is_excluded("~/.claude/settings.json")
        assert config.is_excluded("~/.claude/readme.md")


@pytest.mark.unit
@pytest.mark.config
class TestSettingsOverrides:
    """Test settings override loading and merging."""

    def test_settings_override_loading(self, tmp_path, monkeypatch):
        """Test that settings_overrides are loaded from user config."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        config_path = home / ".ai-agent-rules-config.yaml"
        config_path.write_text(
            """version: 1
settings_overrides:
  claude:
    model: claude-sonnet-4-5-20250929
    theme: dark
"""
        )

        config = Config.load()

        assert "claude" in config.settings_overrides
        assert (
            config.settings_overrides["claude"]["model"] == "claude-sonnet-4-5-20250929"
        )
        assert config.settings_overrides["claude"]["theme"] == "dark"

    @pytest.mark.parametrize(
        "overrides,base,expected",
        [
            (
                {"claude": {"model": "claude-sonnet-4-5-20250929", "theme": "dark"}},
                {"model": "claude-opus-4-20250514", "theme": "light", "other": "value"},
                {
                    "model": "claude-sonnet-4-5-20250929",
                    "theme": "dark",
                    "other": "value",
                },
            ),
            (
                {},
                {"model": "claude-opus-4-20250514"},
                {"model": "claude-opus-4-20250514"},
            ),
        ],
    )
    def test_merge_settings(self, overrides, base, expected):
        """Test merging of base settings with overrides."""
        config = Config(settings_overrides=overrides)
        merged = config.merge_settings("claude", base)
        assert merged == expected

    def test_deep_merge_nested_dicts(self, tmp_path):
        """Test that nested dictionaries are merged properly."""
        config = Config(
            settings_overrides={
                "claude": {
                    "nested": {
                        "override": "new_value",
                    }
                }
            }
        )

        base_settings = {
            "nested": {
                "override": "old_value",
                "keep": "unchanged",
            },
            "top_level": "value",
        }

        merged = config.merge_settings("claude", base_settings)

        assert merged["nested"]["override"] == "new_value"
        assert merged["nested"]["keep"] == "unchanged"
        assert merged["top_level"] == "value"

    def test_build_merged_settings_cache_creation(self, cache_setup):
        """Test that merged settings are written to cache."""
        import json

        agent = cache_setup["agent"]

        cache_path = agent.build_merged_settings()

        assert cache_path is not None
        assert cache_path.exists()

        with open(cache_path) as f:
            cached = json.load(f)

        assert cached["model"] == "claude-sonnet-4-5-20250929"

    def test_build_merged_settings_without_overrides_creates_cache_for_preserved_fields(
        self, tmp_path, monkeypatch
    ):
        """Test that cache is created for agents with preserved_fields even without overrides."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        config_dir = tmp_path / "config"
        claude_dir = config_dir / "claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"model": "claude-opus-4-20250514"}')

        config = Config(settings_overrides={})
        agent = ClaudeAgent(config_dir, config)
        cache_path = agent.build_merged_settings()

        assert cache_path is not None
        assert cache_path.exists()

    def test_cache_staleness_when_missing(self, cache_setup):
        """Test that cache is stale when it doesn't exist."""
        agent = cache_setup["agent"]

        assert agent.is_cache_stale() is True

    def test_cache_staleness_when_fresh(self, cache_setup):
        """Test that cache is fresh when recently built."""
        import time

        agent = cache_setup["agent"]

        agent.build_merged_settings()
        time.sleep(0.01)

        assert agent.is_cache_stale() is False

    def test_cache_staleness_when_base_updated(self, cache_setup):
        """Test that cache is stale when base settings are modified."""
        import time

        agent = cache_setup["agent"]
        base_path = cache_setup["base_settings_path"]

        agent.build_merged_settings()
        time.sleep(0.02)

        base_path.write_text('{"model": "claude-opus-4-20250514", "new": "value"}')
        time.sleep(0.02)

        assert agent.is_cache_stale() is True

    def test_get_cache_diff_when_cache_missing(self, cache_setup):
        """Test that diff shows base vs expected when cache doesn't exist."""
        agent = cache_setup["agent"]

        diff = agent.get_cache_diff()

        assert diff is not None
        assert "Base (current)" in diff
        assert "Expected (with overrides)" in diff
        assert "model" in diff

    def test_build_merged_settings_rebuild_behavior(self, cache_setup):
        """Test that cache rebuild is skipped when fresh but happens when forced."""
        import time

        agent = cache_setup["agent"]

        cache_path1 = agent.build_merged_settings()
        assert cache_path1 is not None
        mtime1 = cache_path1.stat().st_mtime

        time.sleep(0.01)

        cache_path2 = agent.build_merged_settings()
        assert cache_path2 is not None
        mtime2 = cache_path2.stat().st_mtime
        assert mtime1 == mtime2

        time.sleep(0.01)
        cache_path3 = agent.build_merged_settings(force_rebuild=True)
        assert cache_path3 is not None
        mtime3 = cache_path3.stat().st_mtime
        assert mtime3 > mtime2

    def test_build_merged_settings_preserves_enabled_plugins(
        self, tmp_path, monkeypatch
    ):
        """Rebuilding cache preserves Claude-managed enabledPlugins field."""
        import json

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        cache_dir = home / ".ai-agent-rules" / "cache" / "claude"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "settings.json"
        cache_file.write_text(
            json.dumps(
                {
                    "model": "old",
                    "enabledPlugins": {"my-plugin@marketplace": True},
                }
            )
        )

        config_dir = tmp_path / "config"
        claude_dir = config_dir / "claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text(json.dumps({"model": "base"}))

        config = Config(settings_overrides={"claude": {"model": "new"}})
        agent = ClaudeAgent(config_dir, config)
        result_path = agent.build_merged_settings(force_rebuild=True)

        assert result_path is not None
        with open(result_path) as f:
            result = json.load(f)
        assert result["model"] == "new"
        assert result["enabledPlugins"] == {"my-plugin@marketplace": True}

    def test_get_settings_file_for_symlink_returns_cache_when_exists(
        self, tmp_path, monkeypatch
    ):
        """Test that get_settings_file_for_symlink returns cached file when it exists."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        config_dir = tmp_path / "config"
        claude_dir = config_dir / "claude"
        claude_dir.mkdir(parents=True)
        base_settings_path = claude_dir / "settings.json"
        base_settings_path.write_text('{"model": "claude-opus-4-20250514"}')

        config = Config(
            settings_overrides={"claude": {"model": "claude-sonnet-4-5-20250929"}}
        )
        agent = ClaudeAgent(config_dir, config)

        cache_path = agent.build_merged_settings()

        result = config.get_settings_file_for_symlink("claude", base_settings_path)
        assert result == cache_path

    def test_get_settings_file_for_symlink_returns_base_when_no_cache(
        self, tmp_path, monkeypatch
    ):
        """Test that get_settings_file_for_symlink returns base file when cache doesn't exist."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        base_settings_path = tmp_path / "settings.json"
        base_settings_path.write_text('{"model": "claude-opus-4-20250514"}')

        config = Config(
            settings_overrides={"claude": {"model": "claude-sonnet-4-5-20250929"}}
        )

        result = config.get_settings_file_for_symlink("claude", base_settings_path)
        assert result == base_settings_path


@pytest.mark.unit
@pytest.mark.config
class TestPathParsing:
    """Test setting path parsing with array notation."""

    def test_parse_simple_path(self):
        """Test parsing a simple path without arrays."""
        result = parse_setting_path("model")
        assert result == ["model"]

    def test_parse_nested_path(self):
        """Test parsing a nested path."""
        result = parse_setting_path("env.SOME_VAR")
        assert result == ["env", "SOME_VAR"]

    def test_parse_path_with_array_index(self):
        """Test parsing a path with array index."""
        result = parse_setting_path("hooks.SubagentStop[0].command")
        assert result == ["hooks", "SubagentStop", 0, "command"]

    def test_parse_path_with_multiple_array_indices(self):
        """Test parsing a path with multiple array indices."""
        result = parse_setting_path("hooks.SubagentStop[0].hooks[0].command")
        assert result == ["hooks", "SubagentStop", 0, "hooks", 0, "command"]

    def test_parse_path_with_nested_array_indices(self):
        """Test parsing a path with nested array indices on same key."""
        result = parse_setting_path("matrix[0][1].value")
        assert result == ["matrix", 0, 1, "value"]

    def test_parse_empty_path_raises_error(self):
        """Test that empty path raises ValueError."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            parse_setting_path("")

    def test_parse_invalid_array_notation_raises_error(self):
        """Test that invalid array notation raises ValueError."""
        with pytest.raises(ValueError, match="Invalid array notation"):
            parse_setting_path("hooks[invalid].command")

    def test_parse_unclosed_bracket_raises_error(self):
        """Test that unclosed bracket raises ValueError."""
        with pytest.raises(ValueError, match="Invalid array notation"):
            parse_setting_path("hooks[0.command")


@pytest.mark.unit
@pytest.mark.config
class TestPathNavigation:
    """Test navigating data structures using path components."""

    def test_navigate_simple_dict(self):
        """Test navigating a simple dictionary."""
        data = {"model": "sonnet"}
        value, success, error = navigate_path(data, ["model"])
        assert success
        assert value == "sonnet"
        assert error == ""

    def test_navigate_nested_dict(self):
        """Test navigating a nested dictionary."""
        data = {"env": {"VAR": "value"}}
        value, success, error = navigate_path(data, ["env", "VAR"])
        assert success
        assert value == "value"

    def test_navigate_array_index(self):
        """Test navigating with array index."""
        data = {"items": ["first", "second", "third"]}
        value, success, error = navigate_path(data, ["items", 0])
        assert success
        assert value == "first"

    def test_navigate_nested_array_and_dict(self):
        """Test navigating through nested arrays and dicts."""
        data = {"hooks": {"SubagentStop": [{"command": "test.py"}]}}
        value, success, error = navigate_path(
            data, ["hooks", "SubagentStop", 0, "command"]
        )
        assert success
        assert value == "test.py"

    def test_navigate_missing_key_fails(self):
        """Test that navigating to missing key fails."""
        data = {"model": "sonnet"}
        value, success, error = navigate_path(data, ["missing"])
        assert not success
        assert "not found" in error.lower()

    def test_navigate_array_index_out_of_range_fails(self):
        """Test that out of range array index fails."""
        data = {"items": ["first"]}
        value, success, error = navigate_path(data, ["items", 5])
        assert not success
        assert "out of range" in error.lower()

    def test_navigate_expected_array_but_found_dict_fails(self):
        """Test that expecting array but finding dict fails."""
        data = {"items": {"key": "value"}}
        value, success, error = navigate_path(data, ["items", 0])
        assert not success
        assert "expected array" in error.lower()

    def test_navigate_expected_dict_but_found_array_fails(self):
        """Test that expecting dict but finding array fails."""
        data = {"items": ["first", "second"]}
        value, success, error = navigate_path(data, ["items", "key"])
        assert not success
        assert "expected object" in error.lower()


@pytest.mark.unit
@pytest.mark.config
class TestPathValidation:
    """Test validation of override paths against base settings."""

    def test_validate_invalid_agent_fails(self, tmp_path):
        """Test that invalid agent name fails validation."""
        is_valid, error, warning, suggestions = validate_override_path(
            "invalid", "model", tmp_path
        )
        assert not is_valid
        assert "unknown agent" in error.lower()
        assert "claude" in suggestions
        assert "goose" in suggestions

    def test_validate_missing_settings_file_fails(self, tmp_path):
        """Test that missing settings file fails validation."""
        is_valid, error, warning, suggestions = validate_override_path(
            "claude", "model", tmp_path
        )
        assert not is_valid
        assert "no base settings file" in error.lower()

    def test_validate_valid_simple_path_succeeds(self, tmp_path):
        """Test that valid simple path succeeds."""
        settings_file = tmp_path / "claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text('{"model": "sonnet"}')

        is_valid, error, warning, suggestions = validate_override_path(
            "claude", "model", tmp_path
        )
        assert is_valid
        assert error == ""
        assert warning == ""
        assert suggestions == []

    def test_validate_valid_nested_path_succeeds(self, tmp_path):
        """Test that valid nested path succeeds."""
        settings_file = tmp_path / "claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text('{"env": {"VAR": "value"}}')

        is_valid, error, warning, suggestions = validate_override_path(
            "claude", "env.VAR", tmp_path
        )
        assert is_valid
        assert warning == ""

    def test_validate_valid_array_path_succeeds(self, tmp_path):
        """Test that valid array path succeeds."""
        settings_file = tmp_path / "claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text('{"items": ["first", "second"]}')

        is_valid, error, warning, suggestions = validate_override_path(
            "claude", "items[0]", tmp_path
        )
        assert is_valid
        assert warning == ""

    def test_validate_invalid_path_provides_suggestions(self, tmp_path):
        """Test that invalid path provides suggestions (as error)."""
        settings_file = tmp_path / "claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text('{"model": "sonnet", "theme": "dark"}')

        is_valid, error, warning, suggestions = validate_override_path(
            "claude", "invalid", tmp_path
        )
        assert not is_valid
        assert "not found" in error.lower()
        assert warning == ""
        assert "model" in suggestions
        assert "theme" in suggestions

    def test_validate_malformed_array_notation_fails(self, tmp_path):
        """Test that malformed array notation fails."""
        settings_file = tmp_path / "claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text('{"items": ["first"]}')

        is_valid, error, warning, suggestions = validate_override_path(
            "claude", "items[invalid]", tmp_path
        )
        assert not is_valid
        assert "invalid array notation" in error.lower()


@pytest.mark.unit
@pytest.mark.config
class TestDeepMergeWithArrays:
    """Test deep merge functionality with array support."""

    def test_merge_arrays_replaced_wholesale(self):
        """Override list replaces base list entirely."""
        from ai_rules.utils import deep_merge

        base = {"items": ["a", "b", "c"]}
        override = {"items": ["x", "y"]}

        result = deep_merge(base, override)

        assert result["items"] == ["x", "y"]

    def test_merge_array_with_dict_elements_replaced(self):
        """Override list of dicts replaces base list entirely."""
        from ai_rules.utils import deep_merge

        base = {
            "hooks": {
                "SubagentStop": [
                    {"command": "old.py", "type": "command"},
                    {"command": "other.py"},
                ]
            }
        }
        override = {"hooks": {"SubagentStop": [{"command": "new.py"}]}}

        result = deep_merge(base, override)

        assert result["hooks"]["SubagentStop"] == [{"command": "new.py"}]

    def test_merge_extends_base_array_if_override_longer(self):
        """Override list replaces base even when longer."""
        from ai_rules.utils import deep_merge

        base = {"items": ["a"]}
        override = {"items": ["x", "y", "z"]}

        result = deep_merge(base, override)

        assert result["items"] == ["x", "y", "z"]

    def test_merge_shorter_override_replaces_base_array(self):
        """Shorter override list fully replaces longer base list."""
        from ai_rules.utils import deep_merge

        base = {"items": ["a", "b", "c", "d"]}
        override = {"items": ["x"]}

        result = deep_merge(base, override)

        assert result["items"] == ["x"]

    def test_merge_nested_arrays_in_dicts_replaced(self):
        """Override lists inside nested dicts are replaced wholesale."""
        from ai_rules.utils import deep_merge

        base = {
            "hooks": {
                "SubagentStop": [{"hooks": [{"type": "command", "command": "old.py"}]}]
            }
        }
        override = {"hooks": {"SubagentStop": [{"hooks": [{"command": "new.py"}]}]}}

        result = deep_merge(base, override)

        assert result["hooks"]["SubagentStop"] == [{"hooks": [{"command": "new.py"}]}]


class TestCacheCleanup:
    """Tests for orphaned cache cleanup functionality."""

    def test_cleanup_orphaned_cache(self, tmp_path, monkeypatch):
        """Test that orphaned cache files are removed but needed ones are kept."""

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        claude_cache = home / ".ai-agent-rules" / "cache" / "claude"
        claude_cache.mkdir(parents=True)
        (claude_cache / "settings.json").write_text('{"active": true}')

        stale_cache = home / ".ai-agent-rules" / "cache" / "old_agent"
        stale_cache.mkdir(parents=True)
        (stale_cache / "config.json").write_text('{"stale": true}')

        config = Config(settings_overrides={})

        removed = config.cleanup_orphaned_cache(agents_needing_cache={"claude"})
        assert "old_agent" in removed
        assert "claude" not in removed
        assert claude_cache.exists()
        assert not stale_cache.exists()

    def test_cleanup_preserves_cache_with_overrides(self, tmp_path, monkeypatch):
        """Test that cache files with active overrides are preserved."""

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        cache_dir = home / ".ai-agent-rules" / "cache" / "claude"
        cache_dir.mkdir(parents=True)
        (cache_dir / "settings.json").write_text('{"active": true}')

        config = Config(settings_overrides={"claude": {"model": "test"}})

        removed = config.cleanup_orphaned_cache(agents_needing_cache={"claude"})
        assert removed == []
        assert cache_dir.exists()

    def test_cleanup_when_no_cache_dir(self, tmp_path, monkeypatch):
        """Test cleanup when cache directory doesn't exist."""

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        config = Config(settings_overrides={})
        removed = config.cleanup_orphaned_cache(agents_needing_cache=set())
        assert removed == []


@pytest.mark.unit
@pytest.mark.config
class TestConfigWithProfiles:
    """Test Config.load() with profile support."""

    def test_config_load_with_profile(self, tmp_path, monkeypatch):
        """Test loading config with a profile."""
        Config._load_cached.cache_clear()

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "work.yaml").write_text("""
name: work
settings_overrides:
  claude:
    model: work-model
""")

        from ai_rules.profiles import ProfileLoader

        original_init = ProfileLoader.__init__

        def mock_init(self, profiles_dir_arg=None):
            original_init(self, profiles_dir=profiles_dir_arg or profiles_dir)

        monkeypatch.setattr(ProfileLoader, "__init__", mock_init)

        config = Config.load(profile="work")

        assert config.settings_overrides["claude"]["model"] == "work-model"
        assert config.profile_name == "work"

    def test_user_overrides_take_precedence_over_profile(self, tmp_path, monkeypatch):
        """Test that user config overrides profile settings."""
        Config._load_cached.cache_clear()

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        (home / ".ai-agent-rules-config.yaml").write_text("""
settings_overrides:
  claude:
    model: user-model
""")

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "work.yaml").write_text("""
name: work
settings_overrides:
  claude:
    model: work-model
    timeout: 30
""")

        from ai_rules.profiles import ProfileLoader

        original_init = ProfileLoader.__init__

        def mock_init(self, profiles_dir_arg=None):
            original_init(self, profiles_dir=profiles_dir_arg or profiles_dir)

        monkeypatch.setattr(ProfileLoader, "__init__", mock_init)

        config = Config.load(profile="work")

        assert config.settings_overrides["claude"]["model"] == "user-model"
        assert config.settings_overrides["claude"]["timeout"] == 30

    def test_codex_status_line_user_override_replaces_profile_list(
        self, tmp_path, monkeypatch
    ):
        """Codex footer overrides should replace the full profile list on load."""
        Config._load_cached.cache_clear()

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        (home / ".ai-agent-rules-config.yaml").write_text("""
settings_overrides:
  codex:
    tui:
      status_line:
        - model-with-reasoning
        - session-id
""")

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "work.yaml").write_text("""
name: work
settings_overrides:
  codex:
    tui:
      status_line:
        - model-with-reasoning
        - current-dir
        - git-branch
        - context-used
        - used-tokens
        - session-id
""")

        from ai_rules.profiles import ProfileLoader

        original_init = ProfileLoader.__init__

        def mock_init(self, profiles_dir_arg=None):
            original_init(self, profiles_dir=profiles_dir_arg or profiles_dir)

        monkeypatch.setattr(ProfileLoader, "__init__", mock_init)

        config = Config.load(profile="work")

        assert config.settings_overrides["codex"]["tui"]["status_line"] == [
            "model-with-reasoning",
            "session-id",
        ]


@pytest.mark.unit
@pytest.mark.config
class TestTomlSupport:
    """Test TOML format support for Codex CLI settings."""

    def test_build_merged_toml_settings(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        config_dir = tmp_path / "config"
        codex_dir = config_dir / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "config.toml").write_text(
            'model = "gpt-5.2-codex"\napproval_policy = "on-request"\n'
        )

        config = Config(settings_overrides={"codex": {"model": "gpt-5.2"}})
        agent = CodexAgent(config_dir, config)
        cache_path = agent.build_merged_settings()

        assert cache_path is not None
        assert cache_path.exists()

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        with open(cache_path, "rb") as f:
            cached = tomllib.load(f)

        assert cached["model"] == "gpt-5.2"
        assert cached["approval_policy"] == "on-request"

    def test_validate_codex_override_path_valid(self, tmp_path):
        settings_dir = tmp_path / "codex"
        settings_dir.mkdir(parents=True)
        (settings_dir / "config.toml").write_text('model = "gpt-5.2-codex"\n')

        is_valid, error, _warning, _suggestions = validate_override_path(
            "codex", "model", tmp_path
        )

        assert is_valid
        assert error == ""

    def test_validate_codex_nested_override_path_valid(self, tmp_path):
        settings_dir = tmp_path / "codex"
        settings_dir.mkdir(parents=True)
        (settings_dir / "config.toml").write_text(
            'model = "gpt-5.2-codex"\n[tui]\nstatus_line = ["model-with-reasoning"]\n'
        )

        is_valid, error, _warning, _suggestions = validate_override_path(
            "codex", "tui.status_line", tmp_path
        )

        assert is_valid
        assert error == ""

    def test_validate_codex_override_path_invalid(self, tmp_path):
        settings_dir = tmp_path / "codex"
        settings_dir.mkdir(parents=True)
        (settings_dir / "config.toml").write_text('model = "gpt-5.2-codex"\n')

        is_valid, error, _warning, _suggestions = validate_override_path(
            "codex", "nonexistent_key", tmp_path
        )

        assert not is_valid
        assert "nonexistent_key" in error

    def test_toml_settings_stale_without_cache_when_preserved_fields(
        self, tmp_path, monkeypatch
    ):
        """Agents with preserved_fields report stale when no cache exists."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

        config_dir = tmp_path / "config"
        codex_dir = config_dir / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "config.toml").write_text('model = "gpt-5.4"\n')

        config = Config()
        agent = CodexAgent(config_dir, config)
        assert agent.is_cache_stale()

        agent.build_merged_settings()
        assert not agent.is_cache_stale()


@pytest.mark.unit
@pytest.mark.config
class TestMergeSettingsAgentShapes:
    def test_claude_env_override_preserves_base_keys(self):
        config = Config(
            settings_overrides={"claude": {"env": {"CLAUDE_CODE_EFFORT_LEVEL": "high"}}}
        )
        base = {
            "env": {
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
                "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-4-6",
                "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
                "CLAUDE_CODE_EFFORT_LEVEL": "max",
            }
        }
        result = config.merge_settings("claude", base)

        assert result["env"]["CLAUDE_CODE_EFFORT_LEVEL"] == "high"
        assert result["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet-4-6"
        assert result["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "claude-opus-4-6"
        assert (
            result["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"]
            == "claude-haiku-4-5-20251001"
        )
        assert result["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "claude-sonnet-4-6"

    def test_gemini_model_block_added_to_base(self):
        config = Config(
            settings_overrides={"gemini": {"model": {"name": "gemini-3.1-pro-preview"}}}
        )
        base = {
            "context": {"fileName": ["GEMINI.md", "AGENTS.md"]},
            "tools": {},
            "ide": {},
        }
        result = config.merge_settings("gemini", base)

        assert result["model"]["name"] == "gemini-3.1-pro-preview"
        assert result["context"]["fileName"] == ["GEMINI.md", "AGENTS.md"]
        assert "tools" in result
        assert "ide" in result

    def test_goose_top_level_override_preserves_extensions(self):
        config = Config(
            settings_overrides={"goose": {"GOOSE_MODEL": "claude-opus-4-6"}}
        )
        base = {
            "GOOSE_MODEL": "claude-sonnet-4-6",
            "GOOSE_PROVIDER": "anthropic",
            "extensions": {"developer": {"enabled": True}},
        }
        result = config.merge_settings("goose", base)

        assert result["GOOSE_MODEL"] == "claude-opus-4-6"
        assert result["GOOSE_PROVIDER"] == "anthropic"
        assert result["extensions"]["developer"]["enabled"] is True

    def test_codex_flat_override_preserves_siblings(self):
        config = Config(settings_overrides={"codex": {"model": "gpt-5.2"}})
        base = {
            "model": "gpt-5.4",
            "approval_policy": "on-request",
        }
        result = config.merge_settings("codex", base)

        assert result["model"] == "gpt-5.2"
        assert result["approval_policy"] == "on-request"

    def test_codex_status_line_override_replaces_entire_list(self):
        config = Config(
            settings_overrides={
                "codex": {
                    "tui": {
                        "status_line": [
                            "model-with-reasoning",
                            "session-id",
                        ]
                    }
                }
            }
        )
        base = {
            "model": "gpt-5.4",
            "approval_policy": "on-request",
            "tui": {
                "status_line": [
                    "model-with-reasoning",
                    "current-dir",
                    "git-branch",
                    "context-used",
                    "used-tokens",
                    "session-id",
                ]
            },
        }

        result = config.merge_settings("codex", base)

        assert result["tui"]["status_line"] == [
            "model-with-reasoning",
            "session-id",
        ]

    def test_no_override_returns_base_unchanged(self):
        config = Config(settings_overrides={})
        base = {"env": {"KEY": "value"}, "permissions": {"allow": []}}
        result = config.merge_settings("claude", base)

        assert result == base
