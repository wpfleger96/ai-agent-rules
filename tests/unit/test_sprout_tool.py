"""Tests for SproutTool and _is_specialized_path."""

import json

from pathlib import Path

import pytest

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.cli.components.config import _is_specialized_path
from ai_rules.config import Config
from ai_rules.platform import Platform
from ai_rules.tools.sprout import SproutTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_pack_manifest(sprout_dir: Path, pack_id: str = "com.test.my-pack") -> None:
    plugin_dir = sprout_dir / ".plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"id": pack_id}))


# ---------------------------------------------------------------------------
# SproutTool.symlinks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sprout_tool_symlinks_on_macos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    sprout_dir = tmp_path / "sprout"
    sprout_dir.mkdir()
    _create_pack_manifest(sprout_dir)
    tool = SproutTool(tmp_path, Config())

    links = tool.symlinks

    assert len(links) == 2


@pytest.mark.unit
def test_sprout_tool_symlinks_empty_on_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # mock_platform_for_tests autouse fixture already sets Linux, but be explicit.
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.LINUX)
    sprout_dir = tmp_path / "sprout"
    sprout_dir.mkdir()
    _create_pack_manifest(sprout_dir)
    tool = SproutTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_sprout_tool_symlinks_empty_when_source_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    # Deliberately do NOT create tmp_path / "sprout"
    tool = SproutTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_sprout_tool_target_paths_use_correct_bundles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    sprout_dir = tmp_path / "sprout"
    sprout_dir.mkdir()
    _create_pack_manifest(sprout_dir, pack_id="com.test.my-pack")
    tool = SproutTool(tmp_path, Config())

    links = tool.symlinks
    assert len(links) == 2

    target_prod, source_prod = links[0]
    target_dev, source_dev = links[1]

    assert "xyz.block.sprout.app" in target_prod.as_posix()
    assert "xyz.block.sprout.app.dev" not in target_prod.as_posix()
    assert "xyz.block.sprout.app.dev" in target_dev.as_posix()
    assert target_prod.name == "com.test.my-pack"
    assert target_dev.name == "com.test.my-pack"


@pytest.mark.unit
def test_sprout_tool_symlink_sources_point_to_config_dir_sprout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    sprout_dir = tmp_path / "sprout"
    sprout_dir.mkdir()
    _create_pack_manifest(sprout_dir)
    tool = SproutTool(tmp_path, Config())

    for _target, source in tool.symlinks:
        assert source == sprout_dir


@pytest.mark.unit
def test_sprout_tool_needs_cache_always_false(tmp_path: Path) -> None:
    tool = SproutTool(tmp_path, Config())

    assert tool.needs_cache is False


@pytest.mark.unit
def test_sprout_tool_symlinks_empty_when_manifest_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    # sprout/ dir exists but no .plugin/plugin.json
    (tmp_path / "sprout").mkdir()
    tool = SproutTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_sprout_tool_symlinks_empty_when_manifest_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    sprout_dir = tmp_path / "sprout"
    sprout_dir.mkdir()
    plugin_dir = sprout_dir / ".plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text("not valid json {{{{")
    tool = SproutTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_sprout_tool_symlinks_use_pack_id_from_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    sprout_dir = tmp_path / "sprout"
    sprout_dir.mkdir()
    _create_pack_manifest(sprout_dir, pack_id="com.example.custom-pack")
    tool = SproutTool(tmp_path, Config())

    links = tool.symlinks
    assert len(links) == 2

    for target, _source in links:
        assert target.name == "com.example.custom-pack"


# ---------------------------------------------------------------------------
# _is_specialized_path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_is_specialized_path_returns_false_for_tool(tmp_path: Path) -> None:
    tool = SproutTool(tmp_path, Config())
    path_with_agents = tmp_path / "agents" / "something.md"

    assert _is_specialized_path(tool, path_with_agents) is False


@pytest.mark.unit
def test_is_specialized_path_returns_true_for_agent_with_agents_path(
    tmp_path: Path,
) -> None:
    agent = ClaudeAgent(tmp_path, Config())
    agents_path = Path("~/.claude/agents/foo.md")

    assert _is_specialized_path(agent, agents_path) is True


@pytest.mark.unit
def test_is_specialized_path_returns_false_for_agent_without_agents_path(
    tmp_path: Path,
) -> None:
    agent = ClaudeAgent(tmp_path, Config())
    settings_path = Path("~/.claude/settings.json")

    assert _is_specialized_path(agent, settings_path) is False
