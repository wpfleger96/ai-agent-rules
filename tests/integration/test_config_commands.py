"""Integration tests for config commands."""

import yaml

from ai_rules.cli import main


class TestConfigInitCommand:
    """Tests for the config init command."""

    def test_config_init_creates_basic_config(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        inputs = [
            "n",  # Exclude Claude Code settings?
            "n",  # Exclude Codex CLI config?
            "n",  # Exclude Gemini CLI settings?
            "n",  # Exclude Gemini rules?
            "n",  # Exclude Goose config?
            "n",  # Exclude Goose hints?
            "n",  # Exclude Shared agents file?
            "",  # Custom exclusions (empty to finish)
            "n",  # Override settings?
            "y",  # Save configuration?
        ]

        result = runner.invoke(main, ["config", "init"], input="\n".join(inputs))

        assert result.exit_code == 0
        assert config_path.exists()

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["version"] == 1
        assert "exclude_symlinks" not in data or len(data["exclude_symlinks"]) == 0

    def test_config_init_with_exclusions(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        inputs = [
            "y",  # Exclude Claude Code settings?
            "n",  # Exclude Codex CLI config?
            "n",  # Exclude Gemini CLI settings?
            "n",  # Exclude Gemini rules?
            "n",  # Exclude Goose config?
            "y",  # Exclude Goose hints?
            "n",  # Exclude Shared agents file?
            "~/.custom/pattern.txt",  # Custom exclusion
            "",  # Finish custom exclusions
            "n",  # Override settings?
            "y",  # Save configuration?
        ]

        result = runner.invoke(main, ["config", "init"], input="\n".join(inputs))

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert len(data["exclude_symlinks"]) == 3
        assert "~/.claude/settings.json" in data["exclude_symlinks"]
        assert "~/.config/goose/.goosehints" in data["exclude_symlinks"]
        assert "~/.custom/pattern.txt" in data["exclude_symlinks"]

    def test_config_init_with_settings_overrides(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        inputs = [
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",  # Skip exclusions (Claude, Codex, Gemini settings, Gemini rules, Goose config, Goose hints, Shared)
            "",  # No custom exclusions
            "y",  # Override settings?
            "2",  # Choose claude (amp=1, claude=2, codex=3, gemini=4, goose=5, statusline=6, done=7)
            "model=claude-3-5-sonnet-20241022",  # Add override
            "",  # Finish overrides for claude
            "7",  # Done with agents
            "y",  # Save configuration?
        ]

        result = runner.invoke(main, ["config", "init"], input="\n".join(inputs))

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "settings_overrides" in data
        assert "claude" in data["settings_overrides"]
        assert (
            data["settings_overrides"]["claude"]["model"]
            == "claude-3-5-sonnet-20241022"
        )

    def test_config_init_cancels_on_overwrite_decline(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        with open(config_path, "w") as f:
            yaml.dump({"version": 1}, f)

        inputs = ["n"]  # Decline overwrite

        result = runner.invoke(main, ["config", "init"], input="\n".join(inputs))

        assert result.exit_code == 0
        assert "Cancelled" in result.output

    def test_config_init_overwrites_existing_config(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        with open(config_path, "w") as f:
            yaml.dump({"version": 1, "old_key": "old_value"}, f)

        inputs = [
            "y",  # Overwrite existing config
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",  # Skip exclusions (Claude, Codex, Gemini settings, Gemini rules, Goose config, Goose hints, Shared)
            "",  # No custom exclusions
            "n",  # Override settings?
            "y",  # Save configuration?
        ]

        result = runner.invoke(main, ["config", "init"], input="\n".join(inputs))

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "old_key" not in data
        assert data["version"] == 1

    def test_config_init_cancels_on_save_decline(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        inputs = [
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",
            "n",  # Skip exclusions (Claude, Codex, Gemini settings, Gemini rules, Goose config, Goose hints, Shared)
            "",  # No custom exclusions
            "n",  # Override settings?
            "n",  # Configure projects?
            "n",  # DON'T save configuration
        ]

        result = runner.invoke(main, ["config", "init"], input="\n".join(inputs))

        assert result.exit_code == 0
        assert not config_path.exists()
        assert "Configuration not saved" in result.output


class TestConfigShowCommand:
    """Tests for the config show command."""

    def test_config_show_displays_user_config(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        config_data = {
            "version": 1,
            "exclude_symlinks": ["~/.claude/settings.json"],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        result = runner.invoke(main, ["config", "show"])

        assert result.exit_code == 0
        assert "User Config:" in result.output
        assert "~/.claude/settings.json" in result.output
