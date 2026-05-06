"""Integration tests for override commands."""

import yaml

from ai_rules.cli import main


class TestOverrideSetCommand:
    """Tests for the override set command."""

    def test_override_set_creates_config_if_missing(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(
            main, ["override", "set", "claude.model", "claude-3-opus"]
        )

        assert result.exit_code == 0
        assert config_path.exists()

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["settings_overrides"]["claude"]["model"] == "claude-3-opus"

    def test_override_set_with_json_value(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(
            main, ["override", "set", "claude.cleanupPeriodDays", "30"]
        )

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["settings_overrides"]["claude"]["cleanupPeriodDays"] == 30
        assert isinstance(
            data["settings_overrides"]["claude"]["cleanupPeriodDays"], int
        )

    def test_override_set_with_string_value(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(
            main, ["override", "set", "claude.model", "my-model-name"]
        )

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["settings_overrides"]["claude"]["model"] == "my-model-name"

    def test_override_set_with_nested_key(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(
            main,
            [
                "override",
                "set",
                "claude.env.ANTHROPIC_DEFAULT_SONNET_MODEL",
                "claude-sonnet-4-5",
            ],
        )

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert (
            data["settings_overrides"]["claude"]["env"][
                "ANTHROPIC_DEFAULT_SONNET_MODEL"
            ]
            == "claude-sonnet-4-5"
        )

    def test_override_set_updates_existing_value(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {"claude": {"model": "old-model"}},
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["override", "set", "claude.model", "new-model"])

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["settings_overrides"]["claude"]["model"] == "new-model"

    def test_override_set_supports_multiple_agents(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        runner.invoke(main, ["override", "set", "claude.model", "claude-model"])
        result = runner.invoke(
            main, ["override", "set", "goose.GOOSE_MODEL", "goose-model"]
        )

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert data["settings_overrides"]["claude"]["model"] == "claude-model"
        assert data["settings_overrides"]["goose"]["GOOSE_MODEL"] == "goose-model"


class TestOverrideUnsetCommand:
    """Tests for the override unset command."""

    def test_override_unset_removes_setting(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {"claude": {"model": "claude-3-opus", "timeout": 30}},
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["override", "unset", "claude.model"])

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "model" not in data["settings_overrides"]["claude"]
        assert data["settings_overrides"]["claude"]["timeout"] == 30

    def test_override_unset_removes_nested_setting(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {
                "claude": {
                    "api": {"endpoint": "https://api.example.com", "key": "secret"}
                }
            },
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["override", "unset", "claude.api.endpoint"])

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "endpoint" not in data["settings_overrides"]["claude"]["api"]
        assert data["settings_overrides"]["claude"]["api"]["key"] == "secret"

    def test_override_unset_cleans_up_empty_dicts(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {
                "claude": {"api": {"endpoint": "https://api.example.com"}}
            },
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["override", "unset", "claude.api.endpoint"])

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "claude" not in data.get("settings_overrides", {})

    def test_override_unset_removes_agent_when_empty(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {"claude": {"model": "claude-3-opus"}},
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["override", "unset", "claude.model"])

        assert result.exit_code == 0

        with open(config_path) as f:
            data = yaml.safe_load(f)

        assert "claude" not in data.get("settings_overrides", {})

    def test_override_unset_fails_on_missing_config(
        self, runner, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(main, ["override", "unset", "claude.model"])

        assert result.exit_code == 1
        assert "No user config found" in result.output

    def test_override_unset_fails_on_nonexistent_override(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {"claude": {"timeout": 30}},
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["override", "unset", "claude.model"])

        assert result.exit_code == 1
        assert "Override not found" in result.output


class TestOverrideListCommand:
    """Tests for the override list command."""

    def test_override_list_shows_overrides(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "settings_overrides": {
                "claude": {"model": "claude-3-opus", "timeout": 30},
                "goose": {"model": "gpt-4"},
            },
        }
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.chdir(repo_root)

        result = runner.invoke(main, ["override", "list"])

        assert result.exit_code == 0
        assert "claude:" in result.output
        assert "model:" in result.output or "model" in result.output
        assert "goose:" in result.output

    def test_override_list_shows_empty_message(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {"version": 1}
        with open(config_path, "w") as f:
            yaml.dump(existing_data, f)

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.chdir(repo_root)

        result = runner.invoke(main, ["override", "list"])

        assert result.exit_code == 0
        assert "No settings overrides" in result.output


class TestOverrideInstallValidation:
    """Test that invalid overrides are caught at install time."""

    def test_codex_null_override_fails_on_install(self, runner, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: home))

        config_dir = tmp_path / "config"
        codex_dir = config_dir / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "config.toml").write_text('model = "gpt-5.5"\n')

        monkeypatch.setattr("ai_rules.cli.get_config_dir", lambda: config_dir)

        (home / ".ai-agent-rules-config.yaml").write_text(
            "version: 1\nsettings_overrides:\n  codex:\n    model: null\n"
        )

        result = runner.invoke(main, ["install", "--rebuild-cache"])

        assert result.exit_code == 1
        assert "null" in result.output.lower()


class TestOverrideSetArrayIndex:
    """Test that override set with array indices preserves other elements."""

    def test_override_set_array_index_preserves_other_elements(
        self, runner, tmp_path, monkeypatch
    ):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: home))

        config_dir = tmp_path / "config"
        claude_dir = config_dir / "claude"
        claude_dir.mkdir(parents=True)
        import json

        base_settings = {
            "hooks": {
                "SubagentStop": [
                    {"command": "run-tests.sh", "type": "command"},
                    {"command": "lint.sh", "type": "command"},
                    {"command": "notify.sh", "type": "command"},
                ]
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(base_settings))

        monkeypatch.setattr("ai_rules.cli.get_config_dir", lambda: config_dir)

        result = runner.invoke(
            main,
            ["override", "set", "claude.hooks.SubagentStop[1].command", "new-lint.sh"],
        )

        assert result.exit_code == 0

        import yaml

        config_path = home / ".ai-agent-rules-config.yaml"
        with open(config_path) as f:
            data = yaml.safe_load(f)

        stored_list = data["settings_overrides"]["claude"]["hooks"]["SubagentStop"]

        assert len(stored_list) == 3
        assert stored_list[0]["command"] == "run-tests.sh"
        assert stored_list[1]["command"] == "new-lint.sh"
        assert stored_list[2]["command"] == "notify.sh"
