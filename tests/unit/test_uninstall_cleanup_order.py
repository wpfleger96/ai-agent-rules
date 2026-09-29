import builtins
import json
import os

from collections.abc import Callable, Iterable
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from click.testing import CliRunner
from rich.console import Console

from ai_rules.agents.base import Agent
from ai_rules.agents.claude import ClaudeAgent
from ai_rules.cli.components import UNINSTALL_WAVES
from ai_rules.cli.components.mcp import MCPComponent
from ai_rules.cli.context import CliContext, Component, ComponentResult
from ai_rules.cli.runner import run_uninstall_parallel
from ai_rules.config import Config
from ai_rules.mcp import OperationResult
from ai_rules.plugins import PluginManager

CONFIG_DIR = Path(__file__).parents[2] / "src" / "ai_rules" / "config"


def _ctx(tmp_path: Path, targets: tuple[Any, ...] = ()) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=targets,
        selected_targets=targets,
        yes=True,
    )


@pytest.mark.unit
def test_uninstall_waves_order_writers_before_deleters() -> None:
    ids = [[c.component_id for c in wave] for wave in UNINSTALL_WAVES]

    assert ids == [
        ["mcps", "plugins"],
        ["config", "skills", "extensions", "tools", "agents-md"],
        ["settings"],
    ]


def _agent(name: str, outcome: Exception | tuple[OperationResult, str]) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.name = name
    agent.is_settings_file_excluded = False
    if isinstance(outcome, Exception):
        agent.uninstall_mcps.side_effect = outcome
    else:
        agent.uninstall_mcps.return_value = outcome
    return agent


@pytest.mark.unit
def test_mcp_uninstall_failure_on_one_agent_still_cleans_the_rest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    amp = _agent("Amp", OSError(22, "Invalid argument"))
    claude = _agent("Claude", (OperationResult.REMOVED, "removed"))

    result = MCPComponent().uninstall(_ctx(tmp_path, (amp, claude)))

    claude.uninstall_mcps.assert_called_once()
    assert result.ok is False
    assert result.counts == {"removed": 1, "errors": 1}
    assert "Amp: OSError: [Errno 22] Invalid argument" in capsys.readouterr().out


@pytest.mark.unit
def test_mcp_manager_lookup_failure_does_not_skip_later_agents(tmp_path: Path) -> None:
    broken = _agent("Amp", (OperationResult.REMOVED, "removed"))
    broken.get_mcp_manager.side_effect = OSError(22, "Invalid argument")
    claude = _agent("Claude", (OperationResult.REMOVED, "removed"))

    result = MCPComponent().uninstall(_ctx(tmp_path, (broken, claude)))

    claude.uninstall_mcps.assert_called_once()
    assert result.ok is False


class _Uninstaller(Component):
    filterable = False

    def __init__(self, label: str, error: Exception | None = None) -> None:
        self.label = label
        self.error = error
        self.calls = 0

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        if self.error:
            raise self.error
        return ComponentResult()


@pytest.mark.unit
def test_failed_wave_still_runs_remaining_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_rules.cli import main

    mcps = _Uninstaller("mcps", RuntimeError("boom"))
    config, cache = _Uninstaller("config"), _Uninstaller("cache")
    waves = ((mcps,), (config,), (cache,))

    result = run_uninstall_parallel(waves, _ctx(tmp_path))

    assert (config.calls, cache.calls) == (1, 1)
    assert result.ok is False

    monkeypatch.setenv("HOME", str(tmp_path))
    Config._load_cached.cache_clear()
    monkeypatch.setattr("ai_rules.cli.components.UNINSTALL_WAVES", waves)
    cli_result = CliRunner().invoke(main, ["uninstall", "-y"])

    assert cli_result.exit_code == 1, cli_result.output
    assert "boom" in cli_result.output
    assert (config.calls, cache.calls) == (2, 2)


def _worst_case_waves(
    monkeypatch: pytest.MonkeyPatch,
    victim_id: str,
    patch_target: tuple[Any, str],
    is_critical: Callable[..., bool],
) -> None:
    """Run each real wave serially, executing the victim's wave peers at its
    critical point: the worst interleaving parallel execution allows."""
    owner, name = patch_target
    original = getattr(owner, name)
    untested = {"mcps", "tools", "skills", "extensions"}

    def execute(
        comps: Iterable[Component], method: str, ctx: CliContext, **_: Any
    ) -> dict[Component, ComponentResult]:
        peers = [c for c in comps if c.component_id not in untested | {victim_id}]
        victim = [c for c in comps if c.component_id == victim_id]

        def hooked(*args: Any, **kwargs: Any) -> Any:
            if is_critical(*args, **kwargs):
                for peer in peers:
                    peer.uninstall(ctx)
                peers.clear()
            return original(*args, **kwargs)

        with monkeypatch.context() as m:
            m.setattr(owner, name, hooked)
            results = {c: c.uninstall(ctx) for c in victim}
        return results | {c: c.uninstall(ctx) for c in peers}

    monkeypatch.setattr("ai_rules.cli.runner.run_components_parallel", execute)


def _claude_ctx() -> CliContext:
    claude = ClaudeAgent(CONFIG_DIR, Config())
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=CONFIG_DIR,
        config=Config(),
        profile_name=None,
        all_targets=(claude,),
        selected_targets=(claude,),
        yes=True,
    )


@pytest.mark.unit
def test_plugin_cleanup_cannot_recreate_removed_settings_link(
    mock_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugins = mock_home / ".claude" / "plugins"
    settings = mock_home / ".claude" / "settings.json"
    monkeypatch.setattr(PluginManager, "SETTINGS_PATH", settings)
    monkeypatch.setattr(
        PluginManager, "INSTALLED_PLUGINS_PATH", plugins / "installed_plugins.json"
    )
    cached = Config.get_cache_dir() / "claude" / "settings.json"
    cached.parent.mkdir(parents=True)
    cached.write_text(json.dumps({"enabledPlugins": {"probe@local": True}}))
    plugins.mkdir(parents=True)
    settings.symlink_to(os.path.relpath(cached, settings.parent))
    PluginManager.INSTALLED_PLUGINS_PATH.write_text(
        json.dumps({"version": 2, "plugins": {"probe@local": []}})
    )
    PluginManager().save_managed_plugins({"probe@local"})
    _worst_case_waves(
        monkeypatch,
        "plugins",
        (builtins, "open"),
        lambda file, mode="r", *a, **k: Path(file) == settings and mode == "w",
    )

    result = run_uninstall_parallel(UNINSTALL_WAVES, _claude_ctx())

    assert result.ok
    assert not settings.exists() and not settings.is_symlink()
    assert not Config.get_cache_dir().exists()


@pytest.mark.unit
def test_instruction_cache_cleanup_survives_whole_cache_delete(
    mock_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = Config.get_cache_dir() / "shared" / "AGENTS.md"
    shared.parent.mkdir(parents=True)
    shared.write_text("fixture\n")
    _worst_case_waves(
        monkeypatch, "agents-md", (Path, "unlink"), lambda p, *a, **k: p == shared
    )

    result = run_uninstall_parallel(UNINSTALL_WAVES, _claude_ctx())

    assert result.ok
    assert not Config.get_cache_dir().exists()
