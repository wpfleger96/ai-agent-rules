from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from click.testing import CliRunner
from rich.console import Console

from ai_rules.agents.base import Agent
from ai_rules.cli.components.mcp import MCPComponent
from ai_rules.cli.context import CliContext, Component, ComponentResult
from ai_rules.cli.runner import ComponentRunResult, run_uninstall_parallel
from ai_rules.config import Config
from ai_rules.mcp import OperationResult


def _ctx(tmp_path: Path, targets: tuple = ()) -> CliContext:
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
def test_uninstall_finishes_mcps_before_other_components_start(tmp_path, monkeypatch):
    class Named(Component):
        filterable = False

        def __init__(self, label: str, after_symlinks: bool = False):
            self.label = self.component_id = label
            self.install_after_symlinks = after_symlinks

    waves: list[list[str]] = []

    def record_wave(components, method, ctx, **_):
        waves.append([c.label for c in components])
        return {}

    monkeypatch.setattr("ai_rules.cli.runner.run_components_parallel", record_wave)

    run_uninstall_parallel(
        [Named("config"), Named("mcps", after_symlinks=True), Named("cache")],
        _ctx(tmp_path),
    )

    assert waves == [["mcps"], ["config", "cache"]]


def _agent(name: str, outcome) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.name = name
    agent.is_settings_file_excluded = False
    if isinstance(outcome, Exception):
        agent.uninstall_mcps.side_effect = outcome
    else:
        agent.uninstall_mcps.return_value = outcome
    return agent


@pytest.mark.unit
def test_mcp_uninstall_failure_on_one_agent_still_cleans_the_rest(tmp_path):
    amp = _agent("Amp", OSError(22, "Invalid argument"))
    claude = _agent("Claude", (OperationResult.REMOVED, "removed"))

    result = MCPComponent().uninstall(_ctx(tmp_path, (amp, claude)))

    claude.uninstall_mcps.assert_called_once()
    assert result.ok is False
    assert result.counts == {"removed": 1, "errors": 1}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("args", "runner_fn"),
    [
        (["uninstall", "-y"], "run_uninstall_parallel"),
        (["diff"], "run_parallel"),
    ],
)
def test_failed_component_result_exits_nonzero(tmp_path, monkeypatch, args, runner_fn):
    from ai_rules.cli import main

    monkeypatch.setenv("HOME", str(tmp_path))
    Config._load_cached.cache_clear()
    monkeypatch.setattr(
        f"ai_rules.cli.runner.{runner_fn}",
        lambda *a, **k: ComponentRunResult(ok=False),
    )

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 1, result.output


class _Uninstaller(Component):
    filterable = False

    def __init__(self, label: str, *, after_symlinks: bool = False, error=None):
        self.label = self.component_id = label
        self.install_after_symlinks = after_symlinks
        self.error = error
        self.calls = 0

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        if self.error:
            raise self.error
        return ComponentResult()


@pytest.mark.unit
def test_failed_mcp_wave_still_runs_remaining_uninstall(tmp_path, monkeypatch):
    from ai_rules.cli import main

    mcps = _Uninstaller("mcps", after_symlinks=True, error=RuntimeError("boom"))
    config, cache = _Uninstaller("config"), _Uninstaller("cache")

    result = run_uninstall_parallel([mcps, config, cache], _ctx(tmp_path))

    assert (config.calls, cache.calls) == (1, 1)
    assert result.ok is False

    monkeypatch.setenv("HOME", str(tmp_path))
    Config._load_cached.cache_clear()
    monkeypatch.setattr(
        "ai_rules.cli.components.UNINSTALL_COMPONENTS", (mcps, config, cache)
    )
    cli_result = CliRunner().invoke(main, ["uninstall", "-y"])

    assert cli_result.exit_code == 1, cli_result.output
    assert (config.calls, cache.calls) == (2, 2)


@pytest.mark.unit
def test_mcp_manager_lookup_failure_does_not_skip_later_agents(tmp_path):
    broken = _agent("Amp", (OperationResult.REMOVED, "removed"))
    broken.get_mcp_manager.side_effect = OSError(22, "Invalid argument")
    claude = _agent("Claude", (OperationResult.REMOVED, "removed"))

    result = MCPComponent().uninstall(_ctx(tmp_path, (broken, claude)))

    claude.uninstall_mcps.assert_called_once()
    assert result.ok is False
