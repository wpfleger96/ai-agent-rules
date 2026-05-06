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


def run_components(
    components: Iterable[Component],
    operation: LifecycleOperation,
    ctx: CliContext,
) -> ComponentRunResult:
    ok = True
    changed = False
    aborted = False
    counts: dict[str, int] = {}
    results: list[tuple[str, ComponentResult]] = []

    for component in components:
        result = _run_component(component, operation, ctx)
        results.append((component.label, result))

        ok = ok and result.ok
        changed = changed or result.changed
        for key, value in result.counts.items():
            counts[key] = counts.get(key, 0) + value

        if result.abort:
            aborted = True
            break

    return ComponentRunResult(
        ok=ok,
        changed=changed,
        aborted=aborted,
        counts=counts,
        results=tuple(results),
    )
