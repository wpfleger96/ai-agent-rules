"""Integration tests for exclude commands."""

import pytest
import yaml

from ai_rules.cli import main

pytestmark = pytest.mark.integration


class TestExcludeAddCommand:
    """Tests for the exclude add command."""

    def test_exclude_add_creates_config_if_missing(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(main, ["exclude", "add", "~/.claude/test.json"])

        assert result.exit_code == 0
        assert config_path.exists()

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["version"] == 1
        assert "~/.claude/test.json" in data["exclude_symlinks"]

    def test_exclude_add_appends_to_existing_config(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "exclude_symlinks": ["~/.existing/pattern.txt"],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["exclude", "add", "~/.new/pattern.txt"])

        assert result.exit_code == 0

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert len(data["exclude_symlinks"]) == 2
        assert "~/.existing/pattern.txt" in data["exclude_symlinks"]
        assert "~/.new/pattern.txt" in data["exclude_symlinks"]

    def test_exclude_add_rejects_duplicate_pattern(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "exclude_symlinks": ["~/.claude/settings.json"],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["exclude", "add", "~/.claude/settings.json"])

        assert result.exit_code == 0
        assert "already excluded" in result.output

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["exclude_symlinks"].count("~/.claude/settings.json") == 1

    def test_exclude_add_handles_glob_patterns(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(main, ["exclude", "add", "~/.claude/*.json"])

        assert result.exit_code == 0

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "~/.claude/*.json" in data["exclude_symlinks"]


class TestExcludeRemoveCommand:
    """Tests for the exclude remove command."""

    def test_exclude_remove_deletes_pattern(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "exclude_symlinks": ["~/.pattern1.txt", "~/.pattern2.txt"],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["exclude", "remove", "~/.pattern1.txt"])

        assert result.exit_code == 0
        assert "Removed exclusion pattern" in result.output

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "~/.pattern1.txt" not in data["exclude_symlinks"]
        assert "~/.pattern2.txt" in data["exclude_symlinks"]

    def test_exclude_remove_fails_on_missing_config(
        self, runner, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(main, ["exclude", "remove", "~/.pattern.txt"])

        assert result.exit_code == 1
        assert "No user config found" in result.output

    def test_exclude_remove_fails_on_nonexistent_pattern(
        self, runner, tmp_path, monkeypatch
    ):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "exclude_symlinks": ["~/.other.txt"],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f)

        result = runner.invoke(main, ["exclude", "remove", "~/.nonexistent.txt"])

        assert result.exit_code == 1
        assert "Pattern not found" in result.output


class TestExcludeListCommand:
    """Tests for the exclude list command."""

    def test_exclude_list_shows_patterns(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {
            "version": 1,
            "exclude_symlinks": ["~/.pattern1.txt", "~/.pattern2.txt"],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f)

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.chdir(repo_root)

        result = runner.invoke(main, ["exclude", "list"])

        assert result.exit_code == 0
        assert "~/.pattern1.txt" in result.output
        assert "~/.pattern2.txt" in result.output

    def test_exclude_list_shows_empty_message(self, runner, tmp_path, monkeypatch):
        config_path = tmp_path / ".ai-agent-rules-config.yaml"
        monkeypatch.setenv("HOME", str(tmp_path))

        existing_data = {"version": 1}
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f)

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.chdir(repo_root)

        result = runner.invoke(main, ["exclude", "list"])

        assert result.exit_code == 0
        assert "No exclusion patterns" in result.output
