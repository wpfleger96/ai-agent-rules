import threading
import time

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from rich.console import Console

from ai_rules.cli.context import CliContext, Component, ComponentPlan, ComponentResult
from ai_rules.cli.runner import (
    run_components,
    run_components_parallel,
    run_install,
    run_install_parallel,
    run_parallel,
    run_uninstall_parallel,
)
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
def test_run_install_skips_confirmation_when_yes(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult())
    semantic = FakeComponent("semantic", ComponentResult())

    # Confirm is only imported inside the branch guarded by `not ctx.yes and not
    # ctx.dry_run`. With yes=True the block is never entered, so both phases run
    # without any interactive prompt.
    with patch("click.confirm") as mock_ask:
        result = run_install([infra], [semantic], make_context(tmp_path, yes=True))

    mock_ask.assert_not_called()
    assert infra.calls == 1
    assert semantic.calls == 1
    assert result.ok is True


@pytest.mark.unit
def test_run_install_skips_confirmation_when_dry_run(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult())
    semantic = FakeComponent("semantic", ComponentResult())

    with patch("click.confirm") as mock_ask:
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


class _SubclassPlan(ComponentPlan):
    """Subclass of ComponentPlan used by test fixtures.

    run_install_parallel skips apply for components whose plan() returns the
    base ComponentPlan type exactly (used as error fallback). Tests that need
    apply() to run must return a subclass.
    """


class PlanApplyComponent(Component):
    component_id = "plannable"
    filterable = True

    def __init__(
        self,
        label: str,
        *,
        plan_result: ComponentPlan | None = None,
        plan_error: Exception | None = None,
        apply_result: ComponentResult | None = None,
        apply_error: Exception | None = None,
        uninstall_result: ComponentResult | None = None,
        uninstall_error: Exception | None = None,
    ):
        self.label = label
        self._plan_result = plan_result or _SubclassPlan(has_changes=True)
        self._plan_error = plan_error
        self._apply_result = apply_result or ComponentResult()
        self._apply_error = apply_error
        self._uninstall_result = uninstall_result or ComponentResult()
        self._uninstall_error = uninstall_error
        self.plan_calls = 0
        self.apply_calls = 0
        self.uninstall_calls = 0

    def plan(self, ctx: CliContext) -> ComponentPlan:
        self.plan_calls += 1
        if self._plan_error:
            raise self._plan_error
        return self._plan_result

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        self.apply_calls += 1
        if self._apply_error:
            raise self._apply_error
        return self._apply_result

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        self.uninstall_calls += 1
        if self._uninstall_error:
            raise self._uninstall_error
        return self._uninstall_result


class PlanApplyInfraComponent(Component):
    component_id = "infra_plannable"
    filterable = False

    def __init__(
        self,
        label: str,
        *,
        plan_result: ComponentPlan | None = None,
        apply_result: ComponentResult | None = None,
        apply_error: Exception | None = None,
    ):
        self.label = label
        self._plan_result = plan_result or _SubclassPlan(has_changes=True)
        self._apply_result = apply_result or ComponentResult()
        self._apply_error = apply_error
        self.plan_calls = 0
        self.apply_calls = 0

    def plan(self, ctx: CliContext) -> ComponentPlan:
        self.plan_calls += 1
        return self._plan_result

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        self.apply_calls += 1
        if self._apply_error:
            raise self._apply_error
        return self._apply_result


@pytest.mark.unit
def test_run_install_parallel_infra_runs_before_semantic(tmp_path: Path) -> None:
    call_order: list[str] = []

    class OrderedInfra(PlanApplyInfraComponent):
        def plan(self, ctx: CliContext) -> ComponentPlan:
            call_order.append("infra_plan")
            return super().plan(ctx)

        def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
            call_order.append("infra_apply")
            return super().apply(ctx, plan)

    class OrderedSemantic(PlanApplyComponent):
        def plan(self, ctx: CliContext) -> ComponentPlan:
            call_order.append("semantic_plan")
            return super().plan(ctx)

        def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
            call_order.append("semantic_apply")
            return super().apply(ctx, plan)

    infra = OrderedInfra("infra")
    semantic = OrderedSemantic("semantic")

    result = run_install_parallel([infra], [semantic], make_context(tmp_path, yes=True))

    assert result.ok is True
    assert call_order.index("infra_plan") < call_order.index("semantic_plan")
    assert call_order.index("infra_apply") < call_order.index("semantic_apply")


@pytest.mark.unit
def test_run_install_parallel_aborts_if_infrastructure_fails(tmp_path: Path) -> None:
    infra = PlanApplyInfraComponent("infra", apply_result=ComponentResult(ok=False))
    semantic = PlanApplyComponent("semantic")

    result = run_install_parallel([infra], [semantic], make_context(tmp_path, yes=True))

    assert result.ok is False
    assert result.aborted is True
    assert semantic.plan_calls == 0
    assert semantic.apply_calls == 0


@pytest.mark.unit
def test_run_install_parallel_skips_confirmation_when_yes(tmp_path: Path) -> None:
    infra = PlanApplyInfraComponent("infra")
    semantic = PlanApplyComponent("semantic")

    with patch("click.confirm") as mock_ask:
        result = run_install_parallel(
            [infra], [semantic], make_context(tmp_path, yes=True)
        )

    mock_ask.assert_not_called()
    assert result.ok is True


@pytest.mark.unit
def test_run_install_parallel_skips_confirmation_when_dry_run(tmp_path: Path) -> None:
    infra = PlanApplyInfraComponent("infra")
    semantic = PlanApplyComponent("semantic")

    with patch("click.confirm") as mock_ask:
        result = run_install_parallel(
            [infra], [semantic], make_context(tmp_path, dry_run=True)
        )

    mock_ask.assert_not_called()
    assert result.ok is True


@pytest.mark.unit
def test_run_install_parallel_aggregates_counts_across_phases(tmp_path: Path) -> None:
    infra = PlanApplyInfraComponent(
        "infra", apply_result=ComponentResult(counts={"cache_updated": 1})
    )
    semantic = PlanApplyComponent(
        "semantic", apply_result=ComponentResult(counts={"created": 3})
    )

    result = run_install_parallel([infra], [semantic], make_context(tmp_path, yes=True))

    assert result.counts == {"cache_updated": 1, "created": 3}


@pytest.mark.unit
def test_run_install_parallel_skips_apply_for_failed_plan(tmp_path: Path) -> None:
    failing = PlanApplyComponent("failing", plan_error=RuntimeError("plan exploded"))
    succeeding = PlanApplyComponent("succeeding")

    result = run_install_parallel(
        [], [failing, succeeding], make_context(tmp_path, yes=True)
    )

    assert failing.apply_calls == 0
    assert succeeding.apply_calls == 1
    assert result.ok is True


@pytest.mark.unit
def test_run_install_parallel_reports_failure_on_apply_error(tmp_path: Path) -> None:
    bad = PlanApplyComponent("bad", apply_error=RuntimeError("apply exploded"))
    good = PlanApplyComponent("good")

    result = run_install_parallel([], [bad, good], make_context(tmp_path, yes=True))

    assert result.ok is False


@pytest.mark.unit
def test_run_uninstall_parallel_aggregates_counts(tmp_path: Path) -> None:
    first = PlanApplyComponent(
        "first", uninstall_result=ComponentResult(counts={"removed": 2})
    )
    second = PlanApplyComponent(
        "second", uninstall_result=ComponentResult(counts={"removed": 1, "errors": 0})
    )

    result = run_uninstall_parallel([first, second], make_context(tmp_path, yes=True))

    assert result.counts == {"removed": 3, "errors": 0}


@pytest.mark.unit
def test_run_uninstall_parallel_reports_failure_on_error(tmp_path: Path) -> None:
    bad = PlanApplyComponent("bad", uninstall_error=RuntimeError("uninstall exploded"))
    good = PlanApplyComponent("good")

    result = run_uninstall_parallel([bad, good], make_context(tmp_path, yes=True))

    assert result.ok is False


@pytest.mark.unit
def test_run_components_parallel_plan_fallback_on_error(tmp_path: Path) -> None:
    failing = PlanApplyComponent("failing", plan_error=ValueError("plan failed"))
    succeeding = PlanApplyComponent(
        "succeeding", plan_result=ComponentPlan(has_changes=True)
    )

    results = run_components_parallel(
        [failing, succeeding], "plan", make_context(tmp_path, yes=True)
    )

    assert type(results[failing]) is ComponentPlan
    assert results[failing].has_changes is False
    assert results[succeeding].has_changes is True


class _IncludedComponent(PlanApplyComponent):
    component_id = "plannable"


class _ExcludedComponent(PlanApplyComponent):
    component_id = "other"


@pytest.mark.unit
def test_run_components_parallel_respects_component_filter(tmp_path: Path) -> None:
    included = _IncludedComponent("included")
    excluded = _ExcludedComponent("excluded")

    from dataclasses import replace

    ctx = make_context(tmp_path, yes=True)
    ctx_filtered = replace(ctx, component_filter=("plannable",))

    results = run_components_parallel([included, excluded], "plan", ctx_filtered)

    assert included in results
    assert excluded not in results


@pytest.mark.unit
def test_run_install_user_cancels_confirmation(tmp_path: Path) -> None:
    infra = InfraComponent("infra", ComponentResult())
    semantic = FakeComponent("semantic", ComponentResult())

    with (
        patch("ai_rules.cli.check_first_run", return_value=True),
        patch("ai_rules.cli._display_pending_changes", return_value=True),
        patch("click.confirm", side_effect=click.exceptions.Abort()),
    ):
        result = run_install([infra], [semantic], make_context(tmp_path))

    assert result.aborted is True
    assert semantic.calls == 0


@pytest.mark.unit
def test_run_install_parallel_user_cancels_confirmation(tmp_path: Path) -> None:
    infra = PlanApplyInfraComponent("infra")
    semantic = PlanApplyComponent("semantic")

    with (
        patch("ai_rules.cli.check_first_run", return_value=True),
        patch("ai_rules.cli._display_pending_changes", return_value=True),
        patch("click.confirm", side_effect=click.exceptions.Abort()),
    ):
        result = run_install_parallel([infra], [semantic], make_context(tmp_path))

    assert result.aborted is True
    assert semantic.plan_calls == 0
    assert semantic.apply_calls == 0


class _StatusComponent(Component):
    component_id = "status-test"
    filterable = True

    def __init__(
        self,
        label: str,
        *,
        result: ComponentResult | None = None,
        output: str = "",
        delay: float = 0.0,
        barrier: threading.Barrier | None = None,
    ):
        self.label = label
        self._result = result or ComponentResult()
        self._output = output
        self._delay = delay
        self._barrier = barrier
        self.calls = 0

    def status(self, ctx: CliContext) -> ComponentResult:
        self.calls += 1
        if self._barrier is not None:
            self._barrier.wait()
        if self._delay:
            time.sleep(self._delay)
        if self._output:
            from ai_rules.cli.display import get_console

            get_console().print(self._output, markup=False, highlight=False)
        return self._result

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self._result

    def validate(self, ctx: CliContext) -> ComponentResult:
        return self._result


@pytest.mark.unit
def test_run_parallel_status_aggregates_ok(tmp_path: Path) -> None:
    first = _StatusComponent("first", result=ComponentResult(ok=True))
    second = _StatusComponent("second", result=ComponentResult(ok=False))

    result = run_parallel([first, second], "status", make_context(tmp_path))

    assert result.ok is False


@pytest.mark.unit
def test_run_parallel_diff_aggregates_changed(tmp_path: Path) -> None:
    comp = _StatusComponent("comp", result=ComponentResult(changed=True))

    result = run_parallel([comp], "diff", make_context(tmp_path))

    assert result.changed is True


@pytest.mark.unit
def test_run_parallel_validate_aggregates_failure(tmp_path: Path) -> None:
    comp = _StatusComponent("comp", result=ComponentResult(ok=False))

    result = run_parallel([comp], "validate", make_context(tmp_path))

    assert result.ok is False


@pytest.mark.unit
def test_run_parallel_buffer_replay_preserves_definition_order(tmp_path: Path) -> None:
    barrier = threading.Barrier(2)

    first = _StatusComponent(
        "Alpha",
        output="alpha-output",
        delay=0.05,
        barrier=barrier,
        result=ComponentResult(),
    )
    second = _StatusComponent(
        "Beta",
        output="beta-output",
        barrier=barrier,
        result=ComponentResult(),
    )

    buf = StringIO()
    replay_console = Console(file=buf, highlight=False, markup=False)

    comp_list = [first, second]
    ctx = make_context(tmp_path)

    with (
        patch("ai_rules.cli.runner._real_console", replay_console),
        patch("ai_rules.cli.display._real_console", replay_console),
    ):
        run_components_parallel(comp_list, "status", ctx)

    output = buf.getvalue()

    assert output.index("Alpha") < output.index("Beta")
    assert output.index("alpha-output") < output.index("Beta")
