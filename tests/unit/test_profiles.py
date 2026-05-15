"""Unit tests for profile loading and inheritance."""

import pytest

from ai_rules.profiles import (
    CircularInheritanceError,
    ProfileError,
    ProfileLoader,
    ProfileNotFoundError,
)


@pytest.fixture
def profiles_dir(tmp_path):
    """Create test profiles directory."""
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    return profiles


@pytest.mark.unit
class TestProfileLoading:
    """Test basic profile loading."""

    def test_load_simple_profile(self, profiles_dir):
        """Test loading a profile without inheritance."""
        profile_file = profiles_dir / "test.yaml"
        profile_file.write_text("""
name: test
description: Test profile
settings_overrides:
  claude:
    model: test-model
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("test")

        assert profile.name == "test"
        assert profile.description == "Test profile"
        assert profile.settings_overrides["claude"]["model"] == "test-model"

    def test_load_nonexistent_profile_raises_error(self, profiles_dir):
        """Test that loading missing profile raises error."""
        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(ProfileNotFoundError, match="not found"):
            loader.load_profile("nonexistent")

    def test_default_profile_always_available(self, profiles_dir):
        """Test that default profile works even without file."""
        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("default")

        assert profile.name == "default"
        assert profile.settings_overrides == {}


@pytest.mark.unit
class TestProfileInheritance:
    """Test profile inheritance resolution."""

    def test_single_level_inheritance(self, profiles_dir):
        """Test profile extends another profile."""
        (profiles_dir / "base.yaml").write_text("""
name: base
settings_overrides:
  claude:
    model: base-model
    timeout: 30
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: base
settings_overrides:
  claude:
    model: child-model
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.settings_overrides["claude"]["model"] == "child-model"
        assert profile.settings_overrides["claude"]["timeout"] == 30

    def test_multi_level_inheritance(self, profiles_dir):
        """Test deep inheritance chain."""
        (profiles_dir / "grandparent.yaml").write_text("""
name: grandparent
settings_overrides:
  claude:
    model: gp-model
    theme: dark
""")
        (profiles_dir / "parent.yaml").write_text("""
name: parent
extends: grandparent
settings_overrides:
  claude:
    model: parent-model
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: parent
settings_overrides:
  claude:
    timeout: 60
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.settings_overrides["claude"]["model"] == "parent-model"
        assert profile.settings_overrides["claude"]["theme"] == "dark"
        assert profile.settings_overrides["claude"]["timeout"] == 60

    def test_codex_status_line_override_replaces_parent_list(self, profiles_dir):
        """Codex footer overrides should replace the full ordered list."""
        (profiles_dir / "base.yaml").write_text("""
name: base
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
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: base
settings_overrides:
  codex:
    tui:
      status_line:
        - model-with-reasoning
        - session-id
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.settings_overrides["codex"]["tui"]["status_line"] == [
            "model-with-reasoning",
            "session-id",
        ]

    def test_circular_inheritance_detected(self, profiles_dir):
        """Test that circular inheritance raises error."""
        (profiles_dir / "a.yaml").write_text("""
name: a
extends: b
""")
        (profiles_dir / "b.yaml").write_text("""
name: b
extends: a
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(CircularInheritanceError, match="Circular"):
            loader.load_profile("a")


@pytest.mark.unit
class TestExcludeSymlinksMerge:
    """Test exclude_symlinks merging behavior."""

    def test_exclude_symlinks_union(self, profiles_dir):
        """Test that exclude_symlinks are combined."""
        (profiles_dir / "base.yaml").write_text("""
name: base
exclude_symlinks:
  - ~/.claude/settings.json
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: base
exclude_symlinks:
  - ~/.config/goose/config.yaml
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert "~/.claude/settings.json" in profile.exclude_symlinks
        assert "~/.config/goose/config.yaml" in profile.exclude_symlinks


@pytest.mark.unit
class TestProfileListing:
    """Test profile listing functionality."""

    def test_list_profiles(self, profiles_dir):
        """Test listing available profiles."""
        (profiles_dir / "work.yaml").write_text("name: work")
        (profiles_dir / "personal.yaml").write_text("name: personal")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profiles = loader.list_profiles()

        assert "work" in profiles
        assert "personal" in profiles
        assert "default" in profiles


@pytest.mark.unit
class TestProfileErrorHandling:
    """Test error handling for profiles."""

    def test_self_referential_inheritance_detected(self, profiles_dir):
        """Test that a profile cannot extend itself."""
        (profiles_dir / "self.yaml").write_text("""
name: self
extends: self
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(CircularInheritanceError, match="Circular"):
            loader.load_profile("self")

    def test_yaml_error_provides_helpful_message(self, profiles_dir):
        """Test that malformed YAML provides helpful error."""
        (profiles_dir / "bad.yaml").write_text("""
name: bad
settings_overrides:
  invalid: yaml: syntax: here
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(ProfileError, match="invalid YAML"):
            loader.load_profile("bad")

    def test_invalid_settings_overrides_type(self, profiles_dir):
        """Test that invalid settings_overrides type raises error."""
        (profiles_dir / "invalid.yaml").write_text("""
name: invalid
settings_overrides: "should be a dict"
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(ProfileError, match="settings_overrides must be a dict"):
            loader.load_profile("invalid")

    def test_invalid_exclude_symlinks_type(self, profiles_dir):
        """Test that invalid exclude_symlinks type raises error."""
        (profiles_dir / "invalid.yaml").write_text("""
name: invalid
exclude_symlinks: "should be a list"
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(ProfileError, match="exclude_symlinks must be a list"):
            loader.load_profile("invalid")

    def test_invalid_mcp_overrides_type(self, profiles_dir):
        """Test that invalid mcp_overrides type raises error."""
        (profiles_dir / "invalid.yaml").write_text("""
name: invalid
mcp_overrides: "should be a dict"
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)

        with pytest.raises(ProfileError, match="mcp_overrides must be a dict"):
            loader.load_profile("invalid")


@pytest.mark.unit
class TestNestedSettingsOverrideInheritance:
    def test_claude_env_block_merges_across_inheritance(self, profiles_dir):
        (profiles_dir / "parent.yaml").write_text("""
name: parent
settings_overrides:
  claude:
    env:
      VAR_A: "parent"
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: parent
settings_overrides:
  claude:
    env:
      VAR_B: "child"
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.settings_overrides["claude"]["env"]["VAR_A"] == "parent"
        assert profile.settings_overrides["claude"]["env"]["VAR_B"] == "child"

    def test_child_overrides_parent_env_key(self, profiles_dir):
        (profiles_dir / "parent.yaml").write_text("""
name: parent
settings_overrides:
  claude:
    env:
      MODEL_KEY: "old"
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: parent
settings_overrides:
  claude:
    env:
      MODEL_KEY: "new"
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.settings_overrides["claude"]["env"]["MODEL_KEY"] == "new"

    def test_gemini_nested_model_security_inheritance(self, profiles_dir):
        (profiles_dir / "parent.yaml").write_text("""
name: parent
settings_overrides:
  gemini:
    model:
      name: "gemini-x"
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: parent
settings_overrides:
  gemini:
    security:
      auth:
        selectedType: "key"
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.settings_overrides["gemini"]["model"]["name"] == "gemini-x"
        assert (
            profile.settings_overrides["gemini"]["security"]["auth"]["selectedType"]
            == "key"
        )

    def test_multi_agent_overrides_preserved_across_inheritance(self, profiles_dir):
        (profiles_dir / "parent.yaml").write_text("""
name: parent
settings_overrides:
  claude:
    env:
      SHARED_VAR: "from-parent"
  gemini:
    ui:
      useFullWidth: false
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: parent
settings_overrides:
  gemini:
    ui:
      useFullWidth: true
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert (
            profile.settings_overrides["claude"]["env"]["SHARED_VAR"] == "from-parent"
        )
        assert profile.settings_overrides["gemini"]["ui"]["useFullWidth"] is True

    def test_goose_extension_deep_merged_across_profiles(self, profiles_dir):
        (profiles_dir / "parent.yaml").write_text("""
name: parent
settings_overrides:
  goose:
    extensions:
      developer:
        timeout: 300
""")
        (profiles_dir / "child.yaml").write_text("""
name: child
extends: parent
settings_overrides:
  goose:
    extensions:
      developer:
        enabled: false
""")

        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        dev = profile.settings_overrides["goose"]["extensions"]["developer"]
        assert dev["timeout"] == 300
        assert dev["enabled"] is False


@pytest.mark.unit
class TestManagedToolsInheritance:
    """Tests for managed_tools field in profiles."""

    def test_managed_tools_loaded_from_profile(self, profiles_dir):
        (profiles_dir / "work.yaml").write_text("""\
name: work
managed_tools:
  install_sources:
    ai-agent-rules: github
    statusline: github
""")
        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("work")

        assert profile.managed_tools == {
            "install_sources": {"ai-agent-rules": "github", "statusline": "github"}
        }

    def test_managed_tools_deep_merged_across_inheritance(self, profiles_dir):
        (profiles_dir / "base.yaml").write_text("""\
name: base
managed_tools:
  install_sources:
    ai-agent-rules: github
""")
        (profiles_dir / "child.yaml").write_text("""\
name: child
extends: base
managed_tools:
  install_sources:
    statusline: github
""")
        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        # Both tools present after deep merge
        assert profile.managed_tools["install_sources"]["ai-agent-rules"] == "github"
        assert profile.managed_tools["install_sources"]["statusline"] == "github"

    def test_child_overrides_parent_managed_tools_value(self, profiles_dir):
        (profiles_dir / "base.yaml").write_text("""\
name: base
managed_tools:
  install_sources:
    statusline: github
""")
        (profiles_dir / "child.yaml").write_text("""\
name: child
extends: base
managed_tools:
  install_sources:
    statusline: pypi
""")
        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("child")

        assert profile.managed_tools["install_sources"]["statusline"] == "pypi"

    def test_profile_without_managed_tools_has_empty_dict(self, profiles_dir):
        (profiles_dir / "simple.yaml").write_text("name: simple\n")
        loader = ProfileLoader(profiles_dir=profiles_dir)
        profile = loader.load_profile("simple")
        assert profile.managed_tools == {}

    def test_invalid_managed_tools_type_raises_error(self, profiles_dir):
        (profiles_dir / "bad.yaml").write_text("""\
name: bad
managed_tools: "should be a dict"
""")
        loader = ProfileLoader(profiles_dir=profiles_dir)
        with pytest.raises(Exception, match="managed_tools must be a dict"):
            loader.load_profile("bad")
