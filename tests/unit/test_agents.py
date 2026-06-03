from pathlib import Path

import pytest

from ai_rules.agents.amp import AmpAgent
from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.codex import CodexAgent
from ai_rules.agents.gemini import GeminiAgent
from ai_rules.agents.goose import GooseAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.config import Config
from ai_rules.platform import Platform


@pytest.mark.unit
@pytest.mark.agents
class TestClaudeAgent:
    """Test Claude agent symlink discovery and filtering."""

    def test_discovers_all_symlinks(self, test_repo):
        agent = ClaudeAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.claude/CLAUDE.md" in targets
        assert "~/.claude/settings.json" in targets
        assert "~/.claude/agents/test-agent.md" in targets
        assert "~/.claude/commands/test-command.md" in targets

    def test_dynamic_discovery_of_multiple_agents(self, test_repo):
        agents_dir = test_repo / "claude" / "agents"
        (agents_dir / "another-agent.md").write_text("# Another Agent")
        (agents_dir / "third-agent.md").write_text("# Third Agent")

        agent = ClaudeAgent(test_repo, Config(exclude_symlinks=[]))
        symlinks = agent.symlinks

        agent_targets = [
            Path(target).as_posix()
            for target, _ in symlinks
            if "/agents/" in Path(target).as_posix()
        ]
        assert len(agent_targets) == 3
        assert "~/.claude/agents/test-agent.md" in agent_targets
        assert "~/.claude/agents/another-agent.md" in agent_targets
        assert "~/.claude/agents/third-agent.md" in agent_targets

    def test_dynamic_discovery_of_multiple_commands(self, test_repo):
        commands_dir = test_repo / "claude" / "commands"
        (commands_dir / "another-command.md").write_text("# Another Command")

        agent = ClaudeAgent(test_repo, Config(exclude_symlinks=[]))
        symlinks = agent.symlinks

        command_targets = [
            Path(target).as_posix()
            for target, _ in symlinks
            if "/commands/" in Path(target).as_posix()
        ]
        assert len(command_targets) == 2
        assert "~/.claude/commands/test-command.md" in command_targets
        assert "~/.claude/commands/another-command.md" in command_targets

    def test_excludes_filtered_symlinks(self, test_repo):
        config = Config(
            exclude_symlinks=[
                "~/.claude/settings.json",
                "~/.claude/agents/test-agent.md",
            ]
        )
        agent = ClaudeAgent(test_repo, config)

        symlinks = agent.get_filtered_symlinks()

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.claude/settings.json" not in targets
        assert "~/.claude/agents/test-agent.md" not in targets
        assert "~/.claude/CLAUDE.md" in targets
        assert "~/.claude/commands/test-command.md" in targets


@pytest.mark.unit
@pytest.mark.agents
class TestCodexAgent:
    """Test Codex CLI agent symlink discovery and filtering."""

    def test_discovers_all_symlinks(self, test_repo):
        agent = CodexAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.codex/AGENTS.md" in targets
        assert "~/.codex/config.toml" in targets
        assert len(targets) == 2

    def test_agents_md_points_to_shared_source(self, test_repo):
        agent = CodexAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks
        agents_md_entries = [(t, s) for t, s in symlinks if "AGENTS.md" in str(t)]

        assert len(agents_md_entries) == 1
        _, source = agents_md_entries[0]
        assert source == test_repo / "AGENTS.md"

    def test_excludes_filtered_symlinks(self, test_repo):
        config = Config(exclude_symlinks=["~/.codex/config.toml"])
        agent = CodexAgent(test_repo, config)

        symlinks = agent.get_filtered_symlinks()

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.codex/config.toml" not in targets
        assert "~/.codex/AGENTS.md" in targets


@pytest.mark.unit
@pytest.mark.agents
class TestAmpAgent:
    """Test Amp agent symlink discovery and filtering."""

    def test_discovers_all_symlinks(self, test_repo):
        agent = AmpAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.config/amp/AGENTS.md" in targets
        assert "~/.config/amp/settings.json" in targets
        assert len(targets) == 2

    def test_agents_md_points_to_amp_config_source(self, test_repo):
        agent = AmpAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks
        agents_md_entries = [(t, s) for t, s in symlinks if "AGENTS.md" in str(t)]

        assert len(agents_md_entries) == 1
        _, source = agents_md_entries[0]
        assert source == test_repo / "amp" / "AGENTS.md"

    def test_excludes_filtered_symlinks(self, test_repo):
        config = Config(exclude_symlinks=["~/.config/amp/settings.json"])
        agent = AmpAgent(test_repo, config)

        symlinks = agent.get_filtered_symlinks()

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.config/amp/settings.json" not in targets
        assert "~/.config/amp/AGENTS.md" in targets


@pytest.mark.unit
@pytest.mark.agents
class TestGeminiAgent:
    """Test Gemini CLI agent symlink discovery and filtering."""

    def test_discovers_all_symlinks(self, test_repo):
        agent = GeminiAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.gemini/GEMINI.md" in targets
        assert "~/.gemini/settings.json" in targets
        assert len(targets) == 2

    def test_gemini_md_points_to_agent_config_source(self, test_repo):
        agent = GeminiAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks
        gemini_md_entries = [(t, s) for t, s in symlinks if "GEMINI.md" in str(t)]

        assert len(gemini_md_entries) == 1
        _, source = gemini_md_entries[0]
        assert source == test_repo / "gemini" / "GEMINI.md"

    def test_excludes_filtered_symlinks(self, test_repo):
        config = Config(exclude_symlinks=["~/.gemini/settings.json"])
        agent = GeminiAgent(test_repo, config)

        symlinks = agent.get_filtered_symlinks()

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.gemini/settings.json" not in targets
        assert "~/.gemini/GEMINI.md" in targets


@pytest.mark.unit
@pytest.mark.agents
class TestGooseAgent:
    """Test Goose agent symlink discovery and filtering."""

    def test_discovers_all_symlinks(self, test_repo):
        agent = GooseAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.config/goose/.goosehints" in targets
        assert "~/.config/goose/config.yaml" in targets
        assert len(targets) == 2

    def test_excludes_filtered_symlinks(self, test_repo):
        config = Config(exclude_symlinks=["~/.config/goose/config.yaml"])
        agent = GooseAgent(test_repo, config)

        symlinks = agent.get_filtered_symlinks()

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/.config/goose/config.yaml" not in targets
        assert "~/.config/goose/.goosehints" in targets


@pytest.mark.unit
@pytest.mark.agents
class TestSharedAgent:
    """Test Shared agent symlink discovery and filtering."""

    def test_discovers_all_symlinks(self, test_repo):
        agent = SharedAgent(test_repo, Config(exclude_symlinks=[]))

        symlinks = agent.symlinks

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/AGENTS.md" in targets
        assert len(targets) == 1

    def test_excludes_filtered_symlinks(self, test_repo):
        config = Config(exclude_symlinks=["~/AGENTS.md"])
        agent = SharedAgent(test_repo, config)

        symlinks = agent.get_filtered_symlinks()

        targets = [Path(target).as_posix() for target, _ in symlinks]
        assert "~/AGENTS.md" not in targets
        assert len(targets) == 0


@pytest.mark.unit
@pytest.mark.agents
class TestGeminiAgentWindowsCopyMode:
    """Test Gemini agent Windows copy-mode behavior."""

    def test_copy_mode_targets_nonempty_on_windows(self, test_repo, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")

        agent = GeminiAgent(test_repo, Config(exclude_symlinks=[]))

        assert len(agent.copy_mode_targets) > 0

    def test_copy_mode_targets_empty_on_non_windows(self, test_repo, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.LINUX)

        agent = GeminiAgent(test_repo, Config(exclude_symlinks=[]))

        assert agent.copy_mode_targets == set()


@pytest.mark.unit
@pytest.mark.agents
class TestGooseAgentWindowsConfigDir:
    """Test Goose agent uses platform-aware config dir on Windows."""

    def test_settings_symlink_target_uses_appdata_on_windows(
        self, test_repo, monkeypatch
    ):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")

        agent = GooseAgent(test_repo, Config(exclude_symlinks=[]))

        target_str = str(agent.settings_symlink_target)
        assert "Block" in target_str
        assert "goose" in target_str
