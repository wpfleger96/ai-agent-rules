from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from rich.console import Console

from ai_rules.cli.components.completions import CompletionsComponent
from ai_rules.cli.components.plugins import ClaudePluginComponent
from ai_rules.cli.components.settings import SettingsComponent
from ai_rules.cli.context import CliContext, Component, ComponentResult
from ai_rules.cli.runner import run_components
from ai_rules.config import Config


class CacheTarget:
    needs_cache = True
    is_settings_file_excluded = False

    def __init__(self, target_id: str):
        self.target_id = target_id
        self._base_settings_path = Path("/nonexistent/settings.json")


class FailingCacheTarget:
    target_id = "failing"
    name = "Failing"
    needs_cache = True
    is_settings_file_excluded = False

    def __init__(self, base_settings_path: Path):
        self._base_settings_path = base_settings_path

    def build_merged_settings(self, force_rebuild: bool = False) -> Path | None:
        raise ValueError("invalid override")


class Target:
    def __init__(self, target_id: str):
        self.target_id = target_id


class UnavailablePluginManager:
    def is_cli_available(self) -> bool:
        return False

    def sync_plugins(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("plugin sync should not run without claude CLI")


class FailIfRunComponent(Component):
    label = "Must Not Run"
    component_id = "fail-if-run"

    def install(self, ctx: CliContext) -> ComponentResult:
        raise AssertionError("install pipeline should stop after cache build failure")


def make_context(
    tmp_path: Path,
    *,
    config: Config | None = None,
    all_targets: tuple[Any, ...] = (),
    selected_targets: tuple[Any, ...] = (),
    skip_completions: bool = False,
) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=config or Config(),
        profile_name=None,
        all_targets=all_targets,
        selected_targets=selected_targets,
        skip_completions=skip_completions,
    )


@pytest.mark.unit
def test_cache_cleanup_uses_all_targets_not_selected_subset(
    tmp_path: Path, mock_home: Path
) -> None:
    claude_cache = mock_home / ".ai-agent-rules" / "cache" / "claude"
    codex_cache = mock_home / ".ai-agent-rules" / "cache" / "codex"
    old_cache = mock_home / ".ai-agent-rules" / "cache" / "old-agent"
    for cache_dir in (claude_cache, codex_cache, old_cache):
        cache_dir.mkdir(parents=True)
        (cache_dir / "settings.json").write_text("{}")

    ctx = make_context(
        tmp_path,
        all_targets=(CacheTarget("claude"), CacheTarget("codex")),
        selected_targets=(CacheTarget("claude"),),
    )

    result = SettingsComponent().install(ctx)

    assert result.counts.get("cache_removed") == 1
    assert claude_cache.exists()
    assert codex_cache.exists()
    assert not old_cache.exists()


@pytest.mark.unit
def test_settings_cache_failure_aborts_install_components(tmp_path: Path) -> None:
    base_settings_path = tmp_path / "settings.json"
    base_settings_path.write_text("{}")
    failing_target = FailingCacheTarget(base_settings_path)
    ctx = make_context(
        tmp_path,
        all_targets=(failing_target,),
        selected_targets=(failing_target,),
    )

    result = run_components(
        (SettingsComponent(), FailIfRunComponent()),
        "install",
        ctx,
    )

    assert result.ok is False
    assert result.aborted is True
    assert result.counts == {"errors": 1}


@pytest.mark.unit
def test_completions_component_honors_skip_completions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_detect_shell() -> str:
        raise AssertionError("shell detection should not run")

    monkeypatch.setattr("ai_rules.completions.detect_shell", fail_detect_shell)

    result = CompletionsComponent().install(
        make_context(tmp_path, skip_completions=True)
    )

    assert result.changed is False


@pytest.mark.unit
def test_settings_component_removes_dangling_symlink_when_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache" / "goose"
    cache_dir.mkdir(parents=True)
    cached_config = cache_dir / "config.yaml"
    cached_config.write_text("cached")

    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    settings_symlink = settings_dir / "config.yaml"
    settings_symlink.symlink_to(cached_config)

    assert settings_symlink.is_symlink()

    class ExcludedTarget:
        target_id = "goose"
        name = "Goose"
        needs_cache = False
        is_settings_file_excluded = True
        settings_symlink_target = settings_symlink
        _base_settings_path = Path("/nonexistent/settings.yaml")

    monkeypatch.setattr(Config, "get_cache_dir", lambda self: tmp_path / "cache")
    monkeypatch.setattr(Config, "cleanup_orphaned_cache", lambda self, targets: [])

    ctx = make_context(
        tmp_path,
        all_targets=(ExcludedTarget(),),
        selected_targets=(ExcludedTarget(),),
    )
    SettingsComponent().install(ctx)

    assert not settings_symlink.exists()
    assert not settings_symlink.is_symlink()


@pytest.mark.unit
def test_claude_plugin_component_treats_missing_claude_cli_as_nonfatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.plugins.PluginManager", UnavailablePluginManager)
    config = Config(plugins=[{"name": "example", "marketplace": "local"}])

    result = ClaudePluginComponent().install(
        make_context(
            tmp_path,
            config=config,
            selected_targets=(Target("claude"),),
        )
    )

    assert result.ok is True
    assert result.changed is False
