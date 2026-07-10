"""Tests for BuzzTool, get_buzz_teams_dir, and _is_specialized_path."""

import json

from pathlib import Path

import pytest

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.cli.components.config import _is_specialized_path
from ai_rules.config import Config
from ai_rules.platform import Platform, get_buzz_teams_dir
from ai_rules.tools.buzz import BuzzTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_pack_manifest(buzz_dir: Path, pack_id: str = "com.test.my-pack") -> None:
    plugin_dir = buzz_dir / ".plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"id": pack_id}))


# ---------------------------------------------------------------------------
# BuzzTool.symlinks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_buzz_tool_symlinks_on_macos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir)
    tool = BuzzTool(tmp_path, Config())

    links = tool.symlinks

    assert len(links) == 2


@pytest.mark.unit
def test_buzz_tool_symlinks_on_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.LINUX)
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir)
    tool = BuzzTool(tmp_path, Config())

    assert len(tool.symlinks) == 2


@pytest.mark.unit
def test_buzz_tool_symlinks_empty_when_source_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    tool = BuzzTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_buzz_tool_target_paths_use_correct_bundles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir, pack_id="com.test.my-pack")
    tool = BuzzTool(tmp_path, Config())

    links = tool.symlinks
    assert len(links) == 2

    target_prod, _ = links[0]
    target_dev, _ = links[1]

    assert "xyz.block.buzz.app" in target_prod.as_posix()
    assert "xyz.block.buzz.app.dev" not in target_prod.as_posix()
    assert "xyz.block.buzz.app.dev" in target_dev.as_posix()
    assert target_prod.name == "com.test.my-pack"
    assert target_dev.name == "com.test.my-pack"


@pytest.mark.unit
def test_buzz_tool_symlink_sources_point_to_config_dir_buzz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir)
    tool = BuzzTool(tmp_path, Config())

    for _target, source in tool.symlinks:
        assert source == buzz_dir


@pytest.mark.unit
def test_buzz_tool_needs_cache_always_false(tmp_path: Path) -> None:
    tool = BuzzTool(tmp_path, Config())

    assert tool.needs_cache is False


@pytest.mark.unit
def test_buzz_tool_symlinks_empty_when_manifest_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    (tmp_path / "buzz").mkdir()
    tool = BuzzTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_buzz_tool_symlinks_empty_when_manifest_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    plugin_dir = buzz_dir / ".plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text("not valid json {{{{")
    tool = BuzzTool(tmp_path, Config())

    assert tool.symlinks == []


@pytest.mark.unit
def test_buzz_tool_symlinks_use_pack_id_from_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir, pack_id="com.example.custom-pack")
    tool = BuzzTool(tmp_path, Config())

    links = tool.symlinks
    assert len(links) == 2

    for target, _source in links:
        assert target.name == "com.example.custom-pack"


# ---------------------------------------------------------------------------
# get_buzz_teams_dir
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_buzz_teams_dir_macos(
    monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)

    result = get_buzz_teams_dir(dev=False)

    assert (
        result
        == mock_home
        / "Library"
        / "Application Support"
        / "xyz.block.buzz.app"
        / "agents"
        / "teams"
    )


@pytest.mark.unit
def test_get_buzz_teams_dir_macos_dev(
    monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)

    result = get_buzz_teams_dir(dev=True)

    assert (
        result
        == mock_home
        / "Library"
        / "Application Support"
        / "xyz.block.buzz.app.dev"
        / "agents"
        / "teams"
    )


@pytest.mark.unit
def test_get_buzz_teams_dir_linux_xdg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.LINUX)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    result = get_buzz_teams_dir(dev=False)

    assert result == tmp_path / "data" / "xyz.block.buzz.app" / "agents" / "teams"


@pytest.mark.unit
def test_get_buzz_teams_dir_linux_fallback(
    monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.LINUX)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    result = get_buzz_teams_dir(dev=False)

    assert (
        result
        == mock_home / ".local" / "share" / "xyz.block.buzz.app" / "agents" / "teams"
    )


@pytest.mark.unit
def test_get_buzz_teams_dir_wsl(
    monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.WSL)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    result = get_buzz_teams_dir(dev=False)

    assert (
        result
        == mock_home / ".local" / "share" / "xyz.block.buzz.app" / "agents" / "teams"
    )


@pytest.mark.unit
def test_get_buzz_teams_dir_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.WINDOWS)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))

    result = get_buzz_teams_dir(dev=False)

    assert (
        result
        == tmp_path / "AppData" / "Roaming" / "xyz.block.buzz.app" / "agents" / "teams"
    )


# ---------------------------------------------------------------------------
# _is_specialized_path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_is_specialized_path_returns_false_for_tool(tmp_path: Path) -> None:
    tool = BuzzTool(tmp_path, Config())
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


# ---------------------------------------------------------------------------
# BuzzTool.get_deprecated_symlinks — legacy Sprout cleanup
# ---------------------------------------------------------------------------

_SPROUT_BUNDLES = ("xyz.block.sprout.app", "xyz.block.sprout.app.dev")


def _sprout_legacy_path(mock_home: Path, bundle: str, pack_id: str) -> Path:
    return (
        mock_home
        / "Library"
        / "Application Support"
        / bundle
        / "agents"
        / "teams"
        / pack_id
    )


@pytest.mark.unit
def test_legacy_sprout_symlinks_removed_on_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    from ai_rules.cli import cleanup_deprecated_symlinks

    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)

    pack_id = "com.test.my-pack"
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir, pack_id=pack_id)

    for bundle in _SPROUT_BUNDLES:
        legacy = _sprout_legacy_path(mock_home, bundle, pack_id)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.symlink_to(buzz_dir)

    tool = BuzzTool(tmp_path, Config())
    removed = cleanup_deprecated_symlinks([tool], tmp_path, dry_run=False)

    assert removed == 2
    for bundle in _SPROUT_BUNDLES:
        legacy = _sprout_legacy_path(mock_home, bundle, pack_id)
        assert not legacy.exists()
        assert not legacy.is_symlink()


@pytest.mark.unit
def test_legacy_sprout_regular_file_left_untouched_on_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    from ai_rules.cli import cleanup_deprecated_symlinks

    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)

    pack_id = "com.test.my-pack"
    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir, pack_id=pack_id)

    for bundle in _SPROUT_BUNDLES:
        legacy = _sprout_legacy_path(mock_home, bundle, pack_id)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("not a symlink")

    tool = BuzzTool(tmp_path, Config())
    removed = cleanup_deprecated_symlinks([tool], tmp_path, dry_run=False)

    assert removed == 0
    for bundle in _SPROUT_BUNDLES:
        legacy = _sprout_legacy_path(mock_home, bundle, pack_id)
        assert legacy.exists()
        assert legacy.read_text() == "not a symlink"


@pytest.mark.unit
def test_legacy_sprout_cleanup_no_error_when_paths_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_home: Path
) -> None:
    from ai_rules.cli import cleanup_deprecated_symlinks

    monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)

    buzz_dir = tmp_path / "buzz"
    buzz_dir.mkdir()
    _create_pack_manifest(buzz_dir)

    tool = BuzzTool(tmp_path, Config())
    removed = cleanup_deprecated_symlinks([tool], tmp_path, dry_run=False)

    assert removed == 0


@pytest.mark.unit
def test_legacy_sprout_deprecated_symlinks_empty_when_manifest_absent(
    tmp_path: Path,
) -> None:
    tool = BuzzTool(tmp_path, Config())

    assert tool.get_deprecated_symlinks() == []
