"""Lifecycle component runner."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from rich.console import Console as RichConsole

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    LifecycleOperation,
)
from ai_rules.cli.display import _console_override, _real_console

_BUFFERED_METHODS: frozenset[str] = frozenset(
    {"apply", "uninstall", "status", "diff", "validate"}
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
        import click

        from ai_rules.cli import (
            _display_pending_changes,
            check_first_run,
        )
        from ai_rules.cli.display import print_warning

        if not check_first_run(list(ctx.selected_targets), ctx.yes):
            acc.aborted = True
            return acc.to_result()

        if _display_pending_changes(ctx):
            try:
                click.confirm("Apply these changes?", abort=True)
            except click.exceptions.Abort:
                print_warning("Cancelled")
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


def run_install_parallel(
    infrastructure: Iterable[Component],
    semantic: Iterable[Component],
    ctx: CliContext,
) -> ComponentRunResult:
    acc = _RunAccumulator()

    for component in infrastructure:
        plan = component.plan(ctx)
        if plan.has_changes:
            result = component.apply(ctx, plan)
        else:
            result = ComponentResult()
        acc.fold(component, result)
        if result.abort or not result.ok:
            acc.aborted = True
            return acc.to_result()

    if not ctx.yes and not ctx.dry_run:
        import click

        from ai_rules.cli import (
            _display_pending_changes,
            check_first_run,
        )
        from ai_rules.cli.display import print_warning

        if not check_first_run(list(ctx.selected_targets), ctx.yes):
            acc.aborted = True
            return acc.to_result()

        if _display_pending_changes(ctx):
            try:
                click.confirm("Apply these changes?", abort=True)
            except click.exceptions.Abort:
                print_warning("Cancelled")
                acc.aborted = True
                return acc.to_result()

    semantic_list = list(semantic)
    plans = run_components_parallel(semantic_list, "plan", ctx)

    apply_list = [c for c in semantic_list if type(plans.get(c)) is not ComponentPlan]
    results = run_components_parallel(apply_list, "apply", ctx, plans=plans)

    for component in semantic_list:
        if _should_skip(component, ctx):
            continue
        result = results.get(component, ComponentResult())
        acc.fold(component, result)

    return acc.to_result()


def run_uninstall_parallel(
    components: Iterable[Component],
    ctx: CliContext,
) -> ComponentRunResult:
    """Run uninstall across all components in parallel."""
    acc = _RunAccumulator()
    comp_list = list(components)
    results = run_components_parallel(comp_list, "uninstall", ctx)
    for comp in comp_list:
        if _should_skip(comp, ctx):
            continue
        result = results.get(comp, ComponentResult())
        acc.fold(comp, result)
    return acc.to_result()


def run_status_parallel(
    components: Iterable[Component],
    ctx: CliContext,
) -> ComponentRunResult:
    """Run status across all components in parallel."""
    acc = _RunAccumulator()
    comp_list = list(components)
    results = run_components_parallel(comp_list, "status", ctx)
    for comp in comp_list:
        if _should_skip(comp, ctx):
            continue
        result = results.get(comp, ComponentResult())
        acc.fold(comp, result)
    return acc.to_result()


def run_diff_parallel(
    components: Iterable[Component],
    ctx: CliContext,
) -> ComponentRunResult:
    """Run diff across all components in parallel."""
    acc = _RunAccumulator()
    comp_list = list(components)
    results = run_components_parallel(comp_list, "diff", ctx)
    for comp in comp_list:
        if _should_skip(comp, ctx):
            continue
        result = results.get(comp, ComponentResult())
        acc.fold(comp, result)
    return acc.to_result()


def run_validate_parallel(
    components: Iterable[Component],
    ctx: CliContext,
) -> ComponentRunResult:
    """Run validate across all components in parallel."""
    acc = _RunAccumulator()
    comp_list = list(components)
    results = run_components_parallel(comp_list, "validate", ctx)
    for comp in comp_list:
        if _should_skip(comp, ctx):
            continue
        result = results.get(comp, ComponentResult())
        acc.fold(comp, result)
    return acc.to_result()


def get_console(ctx: CliContext) -> RichConsole:
    """Return the active console — thread override if set, else ctx.console."""
    return _console_override.get() or ctx.console


def run_components_parallel(
    components: Iterable[Component],
    method: LifecycleOperation,
    ctx: CliContext,
    plans: dict[Component, ComponentPlan] | None = None,
    max_workers: int | None = None,
) -> dict[Component, Any]:
    """Run a component method across all components in parallel.

    For methods in ``_BUFFERED_METHODS``, each component's console output is
    captured into a per-thread buffer and replayed atomically in original
    component order after the Progress bar closes.

    For ``plan`` and other methods: no buffering — a Progress bar shows
    per-component spinner rows.

    Errors are collected rather than aborting on first failure. After all futures
    settle, per-component errors are printed and partial results are returned.
    """
    comp_list = [c for c in components if not _should_skip(c, ctx)]
    if not comp_list:
        return {}

    should_buffer = method in _BUFFERED_METHODS
    results: dict[Component, Any] = {}
    errors: dict[Component, BaseException] = {}
    futures: dict[Future[Any], Component] = {}

    buffers: dict[Component, StringIO] = {}
    buffered_consoles: dict[Component, RichConsole] = {}

    if should_buffer:
        for comp in comp_list:
            buf = StringIO()
            buffers[comp] = buf
            buffered_consoles[comp] = RichConsole(
                file=buf,
                force_terminal=_real_console.is_terminal,
                color_system=_real_console.color_system,  # type: ignore[arg-type]
                highlight=False,
            )

    def _make_task(
        comp: Component,
        override: RichConsole | None = None,
        plan: ComponentPlan | None = None,
    ) -> Any:
        def _run() -> Any:
            token = None
            try:
                if override is not None:
                    token = _console_override.set(override)
                else:
                    token = _console_override.set(None)
                if plan is not None:
                    return comp.apply(ctx, plan)
                return getattr(comp, method)(ctx)
            finally:
                if token is not None:
                    _console_override.reset(token)

        return _run

    with ThreadPoolExecutor(max_workers=max_workers or len(comp_list)) as pool:
        if should_buffer:
            _run_buffered(
                pool,
                comp_list,
                _make_task,
                buffered_consoles,
                buffers,
                plans,
                futures,
                results,
                errors,
                _real_console,
            )
        else:
            _run_unbuffered(
                pool,
                comp_list,
                method,
                _make_task,
                futures,
                results,
                errors,
                _real_console,
            )

    if errors:
        from ai_rules.cli.display import print_error

        for comp, exc in errors.items():
            print_error(f"{comp.label}: {type(exc).__name__}: {exc}")
            results[comp] = ComponentResult(ok=False, counts={"errors": 1})
        if len(errors) == len(comp_list):
            raise next(iter(errors.values()))

    return results


def _make_progress(real_console: RichConsole) -> Any:
    from rich.progress import Progress, SpinnerColumn, TextColumn

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=real_console,
        transient=True,
    )


def _run_buffered(
    pool: ThreadPoolExecutor,
    components: list[Component],
    make_task: Any,
    buffered_consoles: dict[Component, RichConsole],
    buffers: dict[Component, StringIO],
    plans: dict[Component, ComponentPlan] | None,
    futures: dict[Future[Any], Component],
    results: dict[Component, Any],
    errors: dict[Component, BaseException],
    real_console: RichConsole,
) -> None:
    """Execute components with per-thread output buffering and a Progress bar."""
    with _make_progress(real_console) as progress:
        task_ids: dict[Component, Any] = {}
        for comp in components:
            task_ids[comp] = progress.add_task(f"[cyan]{comp.label}[/cyan]", total=None)
            plan = (plans or {}).get(comp)
            future = pool.submit(make_task(comp, buffered_consoles[comp], plan))
            futures[future] = comp

        for future in as_completed(futures):
            comp = futures[future]
            exc = future.exception()
            if exc is not None:
                errors[comp] = exc
                progress.update(
                    task_ids[comp],
                    description=f"[red]{comp.label} (failed)[/red]",
                    completed=True,
                )
            else:
                results[comp] = future.result()
                progress.update(
                    task_ids[comp],
                    description=f"[green]{comp.label}[/green]",
                    completed=True,
                )

    # Replay buffers in original component order (not completion order)
    first = True
    for comp in components:
        buf_content = buffers[comp].getvalue()
        if buf_content.strip():
            if not first:
                real_console.print()
            header = comp.display_name or comp.label
            real_console.print(f"[bold cyan]{header}[/bold cyan]")
            first = False
            try:
                real_console.file.write(buf_content.rstrip("\n") + "\n")
                real_console.file.flush()
            except OSError:
                pass


def _run_unbuffered(
    pool: ThreadPoolExecutor,
    components: list[Component],
    method: LifecycleOperation,
    make_task: Any,
    futures: dict[Future[Any], Component],
    results: dict[Component, Any],
    errors: dict[Component, BaseException],
    real_console: RichConsole,
) -> None:
    """Execute components under a Progress bar (no output buffering)."""
    from ai_rules.cli.display import print_warning

    with _make_progress(real_console) as progress:
        task_ids: dict[Component, Any] = {}
        for comp in components:
            task_ids[comp] = progress.add_task(f"[cyan]{comp.label}[/cyan]", total=None)
            future = pool.submit(make_task(comp))
            futures[future] = comp

        for future in as_completed(futures):
            comp = futures[future]
            exc = future.exception()
            if exc is not None:
                if method == "plan":
                    results[comp] = ComponentPlan(has_changes=False)
                    print_warning(f"{comp.label} plan failed: {exc}")
                else:
                    errors[comp] = exc
                progress.update(
                    task_ids[comp],
                    description=f"[red]{comp.label} (failed)[/red]",
                    completed=True,
                )
            else:
                results[comp] = future.result()
                progress.update(
                    task_ids[comp],
                    description=f"[green]{comp.label}[/green]",
                    completed=True,
                )
