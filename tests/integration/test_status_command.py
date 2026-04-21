import time

from pathlib import Path
from typing import Any

import pytest
import yaml

from ai_rules.agents.amp import AmpAgent
from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.codex import CodexAgent
from ai_rules.agents.gemini import GeminiAgent
from ai_rules.agents.goose import GooseAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.cli import main
from ai_rules.config import Config
from ai_rules.symlinks import check_symlink, create_symlink


@pytest.mark.integration
class TestStatusValidation:
    """Test status command accuracy for symlink health checks."""

    def test_status_identifies_all_correct_symlinks(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)

        for target, source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            create_symlink(target_path, source, force=False, dry_run=False)

        all_correct = True
        for target, source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            status, message = check_symlink(target_path, source)
            if status != "correct":
                all_correct = False
                break

        assert all_correct

    def test_status_identifies_missing_symlinks(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)

        issues = []
        for target, source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            status, message = check_symlink(target_path, source)
            if status != "correct":
                issues.append((str(target), status))

        assert len(issues) > 0
        assert all(status == "missing" for _, status in issues)

    def test_status_identifies_broken_symlinks(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)
        target, source = claude.symlinks[0]
        target_path = Path(str(target).replace("~", str(mock_home)))

        target_path.parent.mkdir(parents=True, exist_ok=True)
        nonexistent = mock_home / "nonexistent.md"
        target_path.symlink_to(nonexistent)

        status, message = check_symlink(target_path, source)

        assert status in ["broken", "wrong_target"]

    def test_status_identifies_wrong_target_symlinks(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)
        target, source = claude.symlinks[0]
        target_path = Path(str(target).replace("~", str(mock_home)))

        wrong_file = test_repo / "wrong.txt"
        wrong_file.write_text("wrong")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.symlink_to(wrong_file)

        status, message = check_symlink(target_path, source)

        assert status == "wrong_target"

    def test_status_identifies_regular_files_instead_of_symlinks(
        self, test_repo, mock_home
    ):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)
        target, source = claude.symlinks[0]
        target_path = Path(str(target).replace("~", str(mock_home)))

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("not a symlink")

        status, message = check_symlink(target_path, source)

        assert status == "not_symlink"

    def test_status_handles_mixed_symlink_states(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)
        symlinks = claude.symlinks

        target1, source1 = symlinks[0]
        target1_path = Path(str(target1).replace("~", str(mock_home)))
        create_symlink(target1_path, source1, force=False, dry_run=False)

        target2, source2 = symlinks[1]

        target3, source3 = symlinks[2]
        target3_path = Path(str(target3).replace("~", str(mock_home)))
        target3_path.parent.mkdir(parents=True, exist_ok=True)
        target3_path.write_text("regular file")

        statuses = {}
        for target, source in [
            (target1, source1),
            (target2, source2),
            (target3, source3),
        ]:
            target_path = Path(str(target).replace("~", str(mock_home)))
            status, message = check_symlink(target_path, source)
            statuses[str(target)] = status

        assert statuses[str(target1)] == "correct"
        assert statuses[str(target2)] == "missing"
        assert statuses[str(target3)] == "not_symlink"


@pytest.mark.integration
class TestStatusCacheValidation:
    """Test status command cache staleness detection."""

    def test_status_detects_stale_cache_when_base_settings_newer(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test that status detects stale cache when base settings are modified."""
        import ai_rules.cli

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)

        user_config_path = mock_home / ".ai-rules-config.yaml"
        user_config = {
            "version": 1,
            "settings_overrides": {"claude": {"test_override": "value"}},
        }
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config.load()
        cache_path = config.get_merged_settings_path("claude", "settings.json")
        assert cache_path is not None

        ClaudeAgent(test_repo, config).build_merged_settings()
        assert cache_path.exists()

        time.sleep(0.01)

        base_settings_path = test_repo / "claude" / "settings.json"
        base_settings_path.write_text('{"test": "updated"}')

        assert ClaudeAgent(test_repo, config).is_cache_stale()

        result = runner.invoke(main, ["status"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "Cached settings are stale" in result.output

    def test_status_detects_stale_cache_when_user_config_newer(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test that status detects stale cache when user config is modified."""
        import ai_rules.cli

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)

        user_config_path = mock_home / ".ai-rules-config.yaml"
        user_config: dict[str, Any] = {
            "version": 1,
            "settings_overrides": {"claude": {"test_override": "value"}},
        }
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config.load()
        cache_path = config.get_merged_settings_path("claude", "settings.json")
        assert cache_path is not None

        ClaudeAgent(test_repo, config).build_merged_settings()
        assert cache_path.exists()

        time.sleep(0.01)

        user_config["settings_overrides"]["claude"]["test_override"] = "updated_value"
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config_reloaded = Config.load()
        assert ClaudeAgent(test_repo, config_reloaded).is_cache_stale()

        result = runner.invoke(main, ["status"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "Cached settings are stale" in result.output

    def test_status_suggests_rebuild_cache_when_cache_stale(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test that status suggests --rebuild-cache flag when cache is stale."""
        import ai_rules.cli

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)

        user_config_path = mock_home / ".ai-rules-config.yaml"
        user_config = {
            "version": 1,
            "settings_overrides": {"claude": {"test_override": "value"}},
        }
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config.load()
        ClaudeAgent(test_repo, config).build_merged_settings()

        time.sleep(0.01)

        base_settings_path = test_repo / "claude" / "settings.json"
        base_settings_path.write_text('{"test": "updated"}')

        result = runner.invoke(main, ["status"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "--rebuild-cache" in result.output

    def test_status_passes_when_cache_fresh(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test that status passes when cache is fresh."""
        import ai_rules.cli

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)
        monkeypatch.setattr(
            ai_rules.cli,
            "get_git_repo_root",
            lambda: (_ for _ in ()).throw(RuntimeError("Not in git repo")),
        )

        user_config_path = mock_home / ".ai-rules-config.yaml"
        user_config = {
            "version": 1,
            "settings_overrides": {"claude": {"test_override": "value"}},
        }
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config.load()
        config.plugins = []
        config.marketplaces = []

        amp = AmpAgent(test_repo, config)
        claude = ClaudeAgent(test_repo, config)
        codex = CodexAgent(test_repo, config)
        gemini = GeminiAgent(test_repo, config)
        goose = GooseAgent(test_repo, config)
        shared = SharedAgent(test_repo, config)
        for agent in [amp, claude, codex, gemini, goose]:
            agent.build_merged_settings()
        for agent in [amp, claude, codex, gemini, goose, shared]:
            for target, source in agent.symlinks:
                target_path = Path(str(target).replace("~", str(mock_home)))
                create_symlink(target_path, source, force=False, dry_run=False)

        assert not ClaudeAgent(test_repo, config).is_cache_stale()

        result = runner.invoke(
            main, ["status"], catch_exceptions=False, env={"HOME": str(mock_home)}
        )
        assert result.exit_code == 0

    def test_status_no_cache_warning_when_no_overrides(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test that status doesn't warn about cache when no overrides exist."""
        import ai_rules.cli

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)
        monkeypatch.setattr(
            ai_rules.cli,
            "get_git_repo_root",
            lambda: (_ for _ in ()).throw(RuntimeError("Not in git repo")),
        )

        config = Config.load()
        config.plugins = []
        config.marketplaces = []
        amp = AmpAgent(test_repo, config)
        claude = ClaudeAgent(test_repo, config)
        codex = CodexAgent(test_repo, config)
        gemini = GeminiAgent(test_repo, config)
        goose = GooseAgent(test_repo, config)
        shared = SharedAgent(test_repo, config)
        for agent in [amp, claude, codex, gemini, goose]:
            agent.build_merged_settings()
        for agent in [amp, claude, codex, gemini, goose, shared]:
            for target, source in agent.symlinks:
                target_path = Path(str(target).replace("~", str(mock_home)))
                create_symlink(target_path, source, force=False, dry_run=False)

        result = runner.invoke(
            main, ["status"], catch_exceptions=False, env={"HOME": str(mock_home)}
        )
        assert result.exit_code == 0
        assert "Cached settings are stale" not in result.output

    def test_status_shows_cache_diff_when_stale(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test that status displays diff when cache is stale."""
        import ai_rules.cli

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)

        user_config_path = mock_home / ".ai-rules-config.yaml"
        user_config = {
            "version": 1,
            "settings_overrides": {"claude": {"model": "claude-sonnet-4"}},
        }
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config.load()
        ClaudeAgent(test_repo, config).build_merged_settings()

        time.sleep(0.01)

        base_settings_path = test_repo / "claude" / "settings.json"
        base_settings_path.write_text('{"model": "claude-3-5-sonnet"}')

        claude = ClaudeAgent(test_repo, config)
        goose = GooseAgent(test_repo, config)
        shared = SharedAgent(test_repo, config)
        for agent in [claude, goose, shared]:
            for target, source in agent.symlinks:
                target_path = Path(str(target).replace("~", str(mock_home)))
                create_symlink(target_path, source, force=False, dry_run=False)

        result = runner.invoke(main, ["status"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "Cached settings are stale" in result.output
        assert "Cached (current)" in result.output
        assert "Expected (merged)" in result.output
        assert "model" in result.output

    def test_status_shows_diff_when_cache_missing(
        self, test_repo, mock_home, runner, monkeypatch
    ):
        """Test status displays diff when cache doesn't exist."""
        import ai_rules.cli

        from ai_rules.agents.claude import ClaudeAgent
        from ai_rules.agents.goose import GooseAgent
        from ai_rules.agents.shared import SharedAgent
        from ai_rules.config import Config
        from ai_rules.symlinks import create_symlink

        monkeypatch.setattr(ai_rules.cli, "get_config_dir", lambda: test_repo)

        user_config_path = mock_home / ".ai-rules-config.yaml"
        user_config = {
            "version": 1,
            "settings_overrides": {"claude": {"model": "claude-sonnet-4"}},
        }
        with open(user_config_path, "w") as f:
            yaml.dump(user_config, f)

        config = Config.load()
        claude = ClaudeAgent(test_repo, config)
        goose = GooseAgent(test_repo, config)
        shared = SharedAgent(test_repo, config)
        for agent in [claude, goose, shared]:
            for target, source in agent.symlinks:
                target_path = Path(str(target).replace("~", str(mock_home)))
                create_symlink(target_path, source, force=False, dry_run=False)

        result = runner.invoke(main, ["status"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "Cached settings are stale" in result.output
        assert "Base (current)" in result.output
        assert "Expected (with overrides)" in result.output
