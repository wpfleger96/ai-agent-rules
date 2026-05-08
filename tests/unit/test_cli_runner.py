from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from rich.console import Console

from ai_rules.cli.context import CliContext, Component, ComponentResult
from ai_rules.cli.runner import run_components, run_install
from ai_rules.config import Config


class FakeComponent(Component):
    component_id = "fake"
    filterable = True

    def __init__(self, label: str, result: ComponentResult):
        self.label = label
        self.result = result
        self.calls = 0

    def install(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        return self.result


class InfraComponent(Component):
    component_id = "infra"
    filterable = False

    def __init__(self, label: str, result: ComponentResult):
        self.label = label
        self.result = result
        self.calls = 0

    def install(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        return self.result


def make_context(
    tmp_path: Path, *, yes: bool = False, dry_run: bool = False
) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=(),
        selected_targets=(),
        yes=yes,
        dry_run=dry_run,
    )


@pytest.mark.unit
def test_run_components_aggregates_counts(tmp_path: Path) -> None:
    first = FakeComponent("first", ComponentResult(counts={"created": 1}))
    second = FakeComponent(
        "second", ComponentResult(counts={"created": 2, "errors": 1})
    )

    result = run_components([first, second], "install", make_context(tmp_path))

    assert result.counts == {"created": 3, "errors": 1}


@pytest.mark.unit
def test_run_components_stops_after_abort(tmp_path: Path) -> None:
    first = FakeComponent("first", ComponentResult(abort=True))
    second = FakeComponent("second", ComponentResult())

    result = run_components([first, second], "install", make_context(tmp_path))

    assert result.aborted is True
    assert first.calls == 1
    assert second.calls == 0


@pytest.mark.unit
def test_run_components_reports_failure_if_any_component_fails(tmp_path: Path) -> None:
    first = FakeComponent("first", ComponentResult())
    second = FakeComponent("second", ComponentResult(ok=False))

    result = run_components([first, second], "install", make_context(tmp_path))

    assert result.ok is False


@pytest.mark.unit
def test_run_components_reports_changed_if_any_component_changes(
    tmp_path: Path,
) -> None:
    first = FakeComponent("first", ComponentResult(changed=False))
    second = FakeComponent("second", ComponentResult(changed=True))

    result = run_components([first, second], "install", make_context(tmp_path))

    assert result.changed is True


@pytest.mark.unit
def test_run_install_infrastructure_runs_before_semantic(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult())
    semantic = FakeComponent("semantic", ComponentResult())

    result = run_install([infra], [semantic], make_context(tmp_path, yes=True))

    assert infra.calls == 1
    assert semantic.calls == 1
    assert result.ok is True


@pytest.mark.unit
def test_run_install_aborts_if_infrastructure_fails_with_abort(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult(ok=False, abort=True))
    semantic = FakeComponent("semantic", ComponentResult())

    result = run_install([infra], [semantic], make_context(tmp_path, yes=True))

    assert result.aborted is True
    assert semantic.calls == 0


@pytest.mark.unit
def test_run_install_aborts_if_infrastructure_not_ok(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult(ok=False))
    semantic = FakeComponent("semantic", ComponentResult())

    result = run_install([infra], [semantic], make_context(tmp_path, yes=True))

    assert result.aborted is True
    assert result.ok is False
    assert semantic.calls == 0


@pytest.mark.unit
def test_run_install_semantic_respects_component_filter(tmp_path: Path) -> None:
    class ConfigComponent(FakeComponent):
        component_id = "config"

    class SettingsComponent(FakeComponent):
        component_id = "settings"

    config_comp = ConfigComponent("config", ComponentResult())
    settings_comp = SettingsComponent("settings", ComponentResult())

    ctx = CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=(),
        selected_targets=(),
        yes=True,
        component_filter=("config",),
    )

    run_install([], [config_comp, settings_comp], ctx)

    assert config_comp.calls == 1
    assert settings_comp.calls == 0


@pytest.mark.unit
def test_run_install_skips_confirmation_when_yes(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult())
    semantic = FakeComponent("semantic", ComponentResult())

    # Confirm is only imported inside the branch guarded by `not ctx.yes and not
    # ctx.dry_run`. With yes=True the block is never entered, so both phases run
    # without any interactive prompt.
    with patch("rich.prompt.Confirm.ask") as mock_ask:
        result = run_install([infra], [semantic], make_context(tmp_path, yes=True))

    mock_ask.assert_not_called()
    assert infra.calls == 1
    assert semantic.calls == 1
    assert result.ok is True


@pytest.mark.unit
def test_run_install_skips_confirmation_when_dry_run(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult())
    semantic = FakeComponent("semantic", ComponentResult())

    with patch("rich.prompt.Confirm.ask") as mock_ask:
        result = run_install([infra], [semantic], make_context(tmp_path, dry_run=True))

    mock_ask.assert_not_called()
    assert infra.calls == 1
    assert semantic.calls == 1
    assert result.ok is True


@pytest.mark.unit
def test_run_install_aggregates_counts_across_phases(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult(counts={"cache_updated": 1}))
    semantic = FakeComponent("semantic", ComponentResult(counts={"created": 2}))

    result = run_install([infra], [semantic], make_context(tmp_path, yes=True))

    assert result.counts == {"cache_updated": 1, "created": 2}
