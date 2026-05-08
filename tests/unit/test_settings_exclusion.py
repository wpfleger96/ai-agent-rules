"""Tests for ConfigTarget settings file exclusion behavior."""

from pathlib import Path

import pytest

from ai_rules.agents.amp import AmpAgent
from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.codex import CodexAgent
from ai_rules.agents.gemini import GeminiAgent
from ai_rules.agents.goose import GooseAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.config import Config


@pytest.mark.unit
def test_needs_cache_false_when_settings_excluded(test_repo):
    config = Config(exclude_symlinks=["~/.config/goose/config.yaml"])
    agent = GooseAgent(test_repo, config)

    assert agent.needs_cache is False


@pytest.mark.unit
def test_needs_cache_true_when_settings_not_excluded(test_repo):
    config = Config(exclude_symlinks=[])
    agent = GooseAgent(test_repo, config)

    assert agent.needs_cache is True


@pytest.mark.unit
def test_is_settings_file_excluded_returns_true(test_repo):
    config = Config(exclude_symlinks=["~/.config/goose/config.yaml"])
    agent = GooseAgent(test_repo, config)

    assert agent.is_settings_file_excluded is True


@pytest.mark.unit
def test_is_settings_file_excluded_returns_false_no_exclusion(test_repo):
    config = Config(exclude_symlinks=[])
    agent = GooseAgent(test_repo, config)

    assert agent.is_settings_file_excluded is False


@pytest.mark.unit
def test_settings_symlink_target_per_agent(test_repo):
    config = Config(exclude_symlinks=[])

    assert ClaudeAgent(test_repo, config).settings_symlink_target == Path(
        "~/.claude/settings.json"
    )
    assert GooseAgent(test_repo, config).settings_symlink_target == Path(
        "~/.config/goose/config.yaml"
    )
    assert AmpAgent(test_repo, config).settings_symlink_target == Path(
        "~/.config/amp/settings.json"
    )
    assert GeminiAgent(test_repo, config).settings_symlink_target == Path(
        "~/.gemini/settings.json"
    )
    assert CodexAgent(test_repo, config).settings_symlink_target == Path(
        "~/.codex/config.toml"
    )


@pytest.mark.unit
def test_shared_agent_settings_symlink_target_is_none(test_repo):
    config = Config(exclude_symlinks=[])
    agent = SharedAgent(test_repo, config)

    assert agent.settings_symlink_target is None
