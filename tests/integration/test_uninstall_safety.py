from pathlib import Path

import pytest

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.goose import GooseAgent
from ai_rules.config import Config
from ai_rules.symlinks import create_symlink, remove_symlink


@pytest.mark.integration
class TestUninstallSafety:
    """Test uninstall safety mechanisms to prevent data loss."""

    def test_uninstall_only_removes_symlinks(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)

        for target, source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            create_symlink(target_path, source, force=False, dry_run=False)

        for target, _source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            success, message = remove_symlink(target_path, force=True)
            assert success is True

        for target, _source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            assert not target_path.exists()

    def test_uninstall_never_removes_real_files(self, test_repo, mock_home):
        important_file = mock_home / "CLAUDE.md"
        important_file.parent.mkdir(parents=True, exist_ok=True)
        important_file.write_text("IMPORTANT USER DATA")

        success, message = remove_symlink(important_file, force=True)

        assert success is False
        assert important_file.exists()
        assert important_file.read_text() == "IMPORTANT USER DATA"
        assert not important_file.is_symlink()

    def test_uninstall_removes_broken_symlinks(self, test_repo, mock_home):
        target_path = mock_home / "CLAUDE.md"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        nonexistent = test_repo / "nonexistent.md"
        target_path.symlink_to(nonexistent)

        success, message = remove_symlink(target_path, force=True)

        assert success is True
        assert not target_path.exists()

    def test_complete_uninstall_cleanup(self, test_repo, mock_home):
        from ai_rules.agents.shared import SharedAgent

        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)
        goose = GooseAgent(test_repo, config)
        shared = SharedAgent(test_repo, config)

        for agent in [claude, goose, shared]:
            for target, source in agent.symlinks:
                target_path = Path(str(target).replace("~", str(mock_home)))
                create_symlink(target_path, source, force=False, dry_run=False)

        claude_files = [
            mock_home / ".claude" / "CLAUDE.md",
            mock_home / ".claude" / "settings.json",
            mock_home / ".claude" / "agents" / "test-agent.md",
            mock_home / ".claude" / "commands" / "test-command.md",
        ]
        goose_files = [
            mock_home / ".config" / "goose" / ".goosehints",
            mock_home / ".config" / "goose" / "config.yaml",
        ]

        for file in claude_files + goose_files:
            assert file.is_symlink()

        for agent in [claude, goose, shared]:
            for target, _source in agent.symlinks:
                target_path = Path(str(target).replace("~", str(mock_home)))
                remove_symlink(target_path, force=True)

        for file in claude_files + goose_files:
            assert not file.exists()

    def test_uninstall_preserves_source_files(self, test_repo, mock_home):
        config = Config(exclude_symlinks=[])
        claude = ClaudeAgent(test_repo, config)

        for target, source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            create_symlink(target_path, source, force=False, dry_run=False)

        source_files = [source for _, source in claude.symlinks]

        for target, _source in claude.symlinks:
            target_path = Path(str(target).replace("~", str(mock_home)))
            remove_symlink(target_path, force=True)

        for source in source_files:
            assert source.exists()
            assert not source.is_symlink()
