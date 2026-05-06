from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

from ai_rules.cli.context import CliContext, Component, ComponentResult
from ai_rules.cli.runner import run_components
from ai_rules.config import Config


class FakeComponent(Component):
    def __init__(self, label: str, result: ComponentResult):
        self.label = label
        self.result = result
        self.calls = 0

    def install(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        return self.result


def make_context(tmp_path: Path) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=(),
        selected_targets=(),
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
