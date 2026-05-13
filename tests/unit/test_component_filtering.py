"""Tests for component filtering by component_id."""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rich.console import Console

from ai_rules.cli.context import CliContext, Component, ComponentResult
from ai_rules.cli.helpers import complete_components, select_components
from ai_rules.cli.runner import run_components
from ai_rules.config import Config


class _TrackingComponent(Component):
    """Base for fake components that record call counts."""

    calls: int


def FakeComponent(
    label: str, cid: str, result: ComponentResult | None = None
) -> _TrackingComponent:
    """Factory that creates a filterable Component subclass with the given component_id."""

    class _Fake(_TrackingComponent):
        component_id = cid
        filterable = True

        def __init__(self) -> None:
            self.label = label
            self._result = result or ComponentResult()
            self.calls = 0

        def install(self, ctx: CliContext) -> ComponentResult:
            self.calls += 1
            return self._result

        def status(self, ctx: CliContext) -> ComponentResult:
            self.calls += 1
            return self._result

    return _Fake()


class InfraComponent(Component):
    component_id = "infra"
    filterable = False
    label = "infra"

    def __init__(self) -> None:
        self.calls = 0

    def install(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        return ComponentResult()

    def status(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        return ComponentResult()


def make_context(
    tmp_path: Path, component_filter: tuple[str, ...] | None = None
) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=(),
        selected_targets=(),
        component_filter=component_filter,
    )


@pytest.mark.unit
def test_run_components_filter_skips_non_matching(tmp_path: Path) -> None:
    matching = FakeComponent("matching", "config")
    skipped = FakeComponent("skipped", "settings")
    ctx = make_context(tmp_path, component_filter=("config",))

    run_components([matching, skipped], "install", ctx)

    assert matching.calls == 1
    assert skipped.calls == 0


@pytest.mark.unit
def test_run_components_filter_respects_filterable_false(tmp_path: Path) -> None:
    infra = InfraComponent()
    semantic = FakeComponent("semantic", "settings")
    ctx = make_context(tmp_path, component_filter=("config",))

    run_components([infra, semantic], "install", ctx)

    assert infra.calls == 1
    assert semantic.calls == 0


@pytest.mark.unit
def test_select_components_returns_none_for_empty_input(tmp_path: Path) -> None:
    components: tuple[Component, ...] = (
        FakeComponent("a", "config"),
        FakeComponent("b", "settings"),
    )

    result = select_components(components, None)

    assert result is None


@pytest.mark.unit
def test_select_components_validates_ids(tmp_path: Path) -> None:
    components: tuple[Component, ...] = (FakeComponent("a", "config"),)

    with pytest.raises(SystemExit):
        select_components(components, "nonexistent")


@pytest.mark.unit
def test_select_components_returns_valid_tuple(tmp_path: Path) -> None:
    components: tuple[Component, ...] = (
        FakeComponent("a", "config"),
        FakeComponent("b", "settings"),
    )

    result = select_components(components, "config,settings")

    assert result == ("config", "settings")


@pytest.mark.unit
def test_complete_components_respects_component_ids_param() -> None:
    ctx = MagicMock()
    param = MagicMock()

    results = complete_components(ctx, param, "", component_ids=("config", "mcps"))

    completion_values = [item.value for item in results]
    assert "config" in completion_values
    assert "mcps" in completion_values
    assert "skills" not in completion_values
