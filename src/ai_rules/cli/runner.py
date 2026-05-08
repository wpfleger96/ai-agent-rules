"""Lifecycle component runner."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentResult,
    LifecycleOperation,
)


@dataclass
class _RunAccumulator:
    ok: bool = True
    changed: bool = False
    aborted: bool = False
    counts: dict[str, int] = field(default_factory=dict)
    results: list[tuple[str, ComponentResult]] = field(default_factory=list)

    def fold(self, component: Component, result: ComponentResult) -> None:
        self.results.append((component.label, result))
        self.ok = self.ok and result.ok
        self.changed = self.changed or result.changed
        for key, value in result.counts.items():
            self.counts[key] = self.counts.get(key, 0) + value

    def to_result(self) -> ComponentRunResult:
        return ComponentRunResult(
            ok=self.ok,
            changed=self.changed,
            aborted=self.aborted,
            counts=self.counts,
            results=tuple(self.results),
        )


@dataclass(frozen=True)
class ComponentRunResult:
    ok: bool = True
    changed: bool = False
    aborted: bool = False
    counts: dict[str, int] = field(default_factory=dict)
    results: tuple[tuple[str, ComponentResult], ...] = ()


def _run_component(
    component: Component, operation: LifecycleOperation, ctx: CliContext
) -> ComponentResult:
    if operation == "install":
        return component.install(ctx)
    if operation == "status":
        return component.status(ctx)
    if operation == "diff":
        return component.diff(ctx)
    if operation == "validate":
        return component.validate(ctx)
    return component.uninstall(ctx)


def _should_skip(component: Component, ctx: CliContext) -> bool:
    return (
        ctx.component_filter is not None
        and component.filterable
        and component.component_id not in ctx.component_filter
    )


def run_components(
    components: Iterable[Component],
    operation: LifecycleOperation,
    ctx: CliContext,
) -> ComponentRunResult:
    acc = _RunAccumulator()

    for component in components:
        if _should_skip(component, ctx):
            continue

        result = _run_component(component, operation, ctx)
        acc.fold(component, result)

        if result.abort:
            acc.aborted = True
            break

    return acc.to_result()


def run_install(
    infrastructure: Iterable[Component],
    semantic: Iterable[Component],
    ctx: CliContext,
) -> ComponentRunResult:
    acc = _RunAccumulator()

    for component in infrastructure:
        result = component.install(ctx)
        acc.fold(component, result)

        if result.abort or not result.ok:
            acc.aborted = True
            return acc.to_result()

    if not ctx.yes and not ctx.dry_run:
        from rich.prompt import Confirm

        from ai_rules.cli import (
            _display_pending_changes,
            check_first_run,
        )

        if not check_first_run(list(ctx.selected_targets), ctx.yes):
            acc.aborted = True
            return acc.to_result()

        if _display_pending_changes(ctx):
            if not Confirm.ask("Apply these changes?"):
                acc.aborted = True
                return acc.to_result()

    for component in semantic:
        if _should_skip(component, ctx):
            continue

        result = component.install(ctx)
        acc.fold(component, result)

        if result.abort:
            acc.aborted = True
            break

    return acc.to_result()
