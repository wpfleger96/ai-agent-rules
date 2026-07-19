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
        assert source == test_repo / "codex" / "AGENTS.md"


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

    def test_symlinks_agents_md_points_to_config_dir_when_no_agents_md(self, test_repo):
        agent = SharedAgent(test_repo, Config(agents_md=""))

        symlinks = agent.symlinks
        agents_md_entries = [(t, s) for t, s in symlinks if "AGENTS.md" in str(t)]

        assert len(agents_md_entries) == 1
        _, source = agents_md_entries[0]
        assert source == test_repo / "AGENTS.md"

    def test_symlinks_agents_md_points_to_cache_when_agents_md_set(
        self, test_repo, mock_home
    ):
        config = Config(agents_md="## Extra content")
        agent = SharedAgent(test_repo, config)

        symlinks = agent.symlinks
        agents_md_entries = [(t, s) for t, s in symlinks if "AGENTS.md" in str(t)]

        assert len(agents_md_entries) == 1
        _, source = agents_md_entries[0]
        assert source == config.get_merged_agents_md_path()

    def test_needs_agents_md_cache_true_when_agents_md_set(self, test_repo):
        agent = SharedAgent(test_repo, Config(agents_md="## Extra content"))

        assert agent.needs_agents_md_cache is True

    def test_needs_agents_md_cache_false_when_agents_md_empty(self, test_repo):
        agent = SharedAgent(test_repo, Config(agents_md=""))

        assert agent.needs_agents_md_cache is False

    def test_build_merged_agents_md_writes_base_plus_appended_content(
        self, test_repo, mock_home
    ):
        config = Config(agents_md="## Extra content")
        agent = SharedAgent(test_repo, config)

        cache_path = agent.build_merged_agents_md()

        assert cache_path is not None
        assert cache_path.exists()
        content = cache_path.read_text(encoding="utf-8")
        assert content == "# Shared Agent Rules\nTest content\n\n## Extra content\n"

    def test_build_merged_agents_md_ends_with_single_newline(
        self, test_repo, mock_home
    ):
        config = Config(agents_md="## Extra")
        agent = SharedAgent(test_repo, config)

        cache_path = agent.build_merged_agents_md()

        assert cache_path is not None
        content = cache_path.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert not content.endswith("\n\n")

    def test_build_merged_agents_md_returns_none_when_no_agents_md(
        self, test_repo, mock_home
    ):
        agent = SharedAgent(test_repo, Config(agents_md=""))

        result = agent.build_merged_agents_md()

        assert result is None

    def test_is_agents_md_cache_stale_true_when_cache_missing(
        self, test_repo, mock_home
    ):
        config = Config(agents_md="## Extra content")
        agent = SharedAgent(test_repo, config)

        # Cache file does not exist yet
        assert agent.is_agents_md_cache_stale() is True

    def test_is_agents_md_cache_stale_false_when_content_matches(
        self, test_repo, mock_home
    ):
        config = Config(agents_md="## Extra content")
        agent = SharedAgent(test_repo, config)

        # Build the cache so content is up to date
        agent.build_merged_agents_md()
        # Clear cached_property so symlinks and staleness checks re-evaluate
        agent.__dict__.pop("symlinks", None)

        assert agent.is_agents_md_cache_stale() is False


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
