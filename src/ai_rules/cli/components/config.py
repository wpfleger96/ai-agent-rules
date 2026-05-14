"""Config files lifecycle component."""

from __future__ import annotations

from pathlib import Path

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    ConfigPlan,
)

SPECIALIZED_PATH_PARTS = ("/agents/", "/commands/", "/skills/", "/hooks/")


def _is_specialized_path(target: Path) -> bool:
    target_str = str(target)
    return any(part in target_str for part in SPECIALIZED_PATH_PARTS)


def _display_symlink_status(
    status_code: str,
    target: Path,
    source: Path,
    message: str,
) -> bool:
    from rich.console import Console

    from ai_rules.symlinks import get_content_diff

    console = Console()

    target_str = str(target)
    if source.is_dir():
        target_str = target_str.rstrip("/") + "/"
    target_display = target_str

    if status_code == "correct":
        console.print(f"  [green]✓[/green] {target_display}")
        return True
    if status_code == "missing":
        console.print(f"  [red]✗[/red] {target_display} [dim](not installed)[/dim]")
        return False
    if status_code == "broken":
        console.print(f"  [red]✗[/red] {target_display} [dim](broken symlink)[/dim]")
        return False
    if status_code == "wrong_target":
        console.print(f"  [yellow]⚠[/yellow] {target_display} [dim]({message})[/dim]")

        try:
            actual = target.expanduser().resolve()
            diff_output = get_content_diff(actual, source)
            if diff_output:
                console.print(diff_output)
        except (OSError, RuntimeError):
            pass

        return False
    if status_code == "not_symlink":
        console.print(
            f"  [yellow]⚠[/yellow] {target_display} [dim](not a symlink)[/dim]"
        )

        try:
            diff_output = get_content_diff(target.expanduser(), source)
            if diff_output:
                console.print(diff_output)
        except (OSError, RuntimeError):
            pass

        return False
    return True


class ConfigComponent(Component):
    label = "Config Files"
    component_id = "config"

    def plan(self, ctx: CliContext) -> ConfigPlan:
        symlink_ops: list[tuple[Path, Path]] = []
        excluded_count = 0

        for agent in ctx.selected_targets:
            filtered_symlinks = agent.get_filtered_symlinks()
            excluded_count += len(agent.symlinks) - len(filtered_symlinks)

            config_symlinks = [
                (tgt, src)
                for tgt, src in filtered_symlinks
                if not _is_specialized_path(tgt)
            ]
            excluded_count += len(filtered_symlinks) - len(config_symlinks)
            symlink_ops.extend(config_symlinks)

        return ConfigPlan(
            has_changes=bool(symlink_ops),
            symlink_ops=symlink_ops,
            excluded_count=excluded_count,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, ConfigPlan):
            return ComponentResult()

        from ai_rules.cli import cleanup_deprecated_symlinks
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import SymlinkResult, create_symlink

        console = get_console(ctx)

        created = updated = skipped = excluded = errors = 0

        excluded = plan.excluded_count

        for target, source in plan.symlink_ops:
            result, message = create_symlink(target, source, True, ctx.dry_run)

            if result == SymlinkResult.CREATED:
                console.print(f"  [green]✓[/green] {target} → {source}")
                created += 1
            elif result == SymlinkResult.ALREADY_CORRECT:
                console.print(f"  [dim]•[/dim] {target} [dim](already correct)[/dim]")
            elif result == SymlinkResult.UPDATED:
                console.print(f"  [yellow]↻[/yellow] {target} → {source}")
                updated += 1
            elif result == SymlinkResult.SKIPPED:
                console.print(f"  [yellow]○[/yellow] {target} [dim](skipped)[/dim]")
                skipped += 1
            elif result == SymlinkResult.ERROR:
                console.print(f"  [red]✗[/red] {target}: {message}")
                errors += 1

        cleanup_deprecated_symlinks(
            list(ctx.selected_targets), ctx.config_dir, ctx.dry_run
        )

        return ComponentResult(
            ok=errors == 0,
            changed=bool(created or updated),
            counts={
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "excluded": excluded,
                "errors": errors,
            },
        )

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli import cleanup_deprecated_symlinks
        from ai_rules.symlinks import SymlinkResult, create_symlink

        created = updated = skipped = excluded = errors = 0
        effective_force = ctx.yes or not ctx.dry_run

        for agent in ctx.selected_targets:
            ctx.console.print(f"\n[bold]{agent.name}[/bold]")

            filtered_symlinks = agent.get_filtered_symlinks()
            excluded_count = len(agent.symlinks) - len(filtered_symlinks)

            config_symlinks = [
                (tgt, src)
                for tgt, src in filtered_symlinks
                if not _is_specialized_path(tgt)
            ]
            excluded_count += len(filtered_symlinks) - len(config_symlinks)

            if excluded_count > 0:
                ctx.console.print(
                    f"  [dim]({excluded_count} symlink(s) excluded)[/dim]"
                )
                excluded += excluded_count

            for target, source in config_symlinks:
                result, message = create_symlink(
                    target, source, effective_force, ctx.dry_run
                )

                if result == SymlinkResult.CREATED:
                    ctx.console.print(f"  [green]✓[/green] {target} → {source}")
                    created += 1
                elif result == SymlinkResult.ALREADY_CORRECT:
                    ctx.console.print(
                        f"  [dim]•[/dim] {target} [dim](already correct)[/dim]"
                    )
                elif result == SymlinkResult.UPDATED:
                    ctx.console.print(f"  [yellow]↻[/yellow] {target} → {source}")
                    updated += 1
                elif result == SymlinkResult.SKIPPED:
                    ctx.console.print(
                        f"  [yellow]○[/yellow] {target} [dim](skipped)[/dim]"
                    )
                    skipped += 1
                elif result == SymlinkResult.ERROR:
                    ctx.console.print(f"  [red]✗[/red] {target}: {message}")
                    errors += 1

        cleanup_deprecated_symlinks(
            list(ctx.selected_targets), ctx.config_dir, ctx.dry_run
        )

        results = {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "excluded": excluded,
            "errors": errors,
        }
        return ComponentResult(
            ok=errors == 0,
            changed=bool(created or updated),
            counts=results,
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.symlinks import check_symlink

        ctx.console.print("[bold cyan]Config Files[/bold cyan]\n")
        all_correct = True

        for target in ctx.selected_targets:
            ctx.console.print(f"[bold]{target.name}:[/bold]")

            filtered_symlinks = target.get_filtered_symlinks()
            excluded_symlinks = [
                (tgt, source)
                for tgt, source in target.symlinks
                if (tgt, source) not in filtered_symlinks
            ]

            for tgt, source in filtered_symlinks:
                if _is_specialized_path(tgt):
                    continue

                status_code, message = check_symlink(tgt, source)
                is_correct = _display_symlink_status(status_code, tgt, source, message)
                all_correct = all_correct and is_correct

            for tgt, _source in excluded_symlinks:
                ctx.console.print(
                    f"  [dim]○[/dim] {tgt} [dim](excluded by config)[/dim]"
                )

            ctx.console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.symlinks import check_symlink, get_content_diff

        found_differences = False

        for target in ctx.selected_targets:
            target_has_diff = False
            target_diffs: list[tuple[Path, Path, str, str, str | None]] = []

            for tgt, source in target.get_filtered_symlinks():
                if _is_specialized_path(tgt):
                    continue
                target_path = tgt.expanduser()
                status_code, message = check_symlink(target_path, source)

                if status_code == "missing":
                    target_diffs.append(
                        (target_path, source, "missing", "Not installed", None)
                    )
                    target_has_diff = True
                elif status_code == "broken":
                    target_diffs.append(
                        (target_path, source, "broken", "Broken symlink", None)
                    )
                    target_has_diff = True
                elif status_code == "wrong_target":
                    try:
                        actual = target_path.resolve()
                        diff_output = get_content_diff(actual, source)
                        target_diffs.append(
                            (
                                target_path,
                                source,
                                "wrong",
                                f"Points to {actual}",
                                diff_output,
                            )
                        )
                        target_has_diff = True
                    except (OSError, RuntimeError):
                        target_diffs.append(
                            (target_path, source, "broken", "Broken symlink", None)
                        )
                        target_has_diff = True
                elif status_code == "not_symlink":
                    try:
                        diff_output = get_content_diff(target_path, source)
                    except (OSError, RuntimeError):
                        diff_output = None
                    target_diffs.append(
                        (
                            target_path,
                            source,
                            "file",
                            "Regular file (not symlink)",
                            diff_output,
                        )
                    )
                    target_has_diff = True

            if target_has_diff:
                ctx.console.print(f"[bold]{target.name}:[/bold]")
                for (
                    path,
                    expected_source,
                    diff_type,
                    desc,
                    content_diff,
                ) in target_diffs:
                    if diff_type == "missing":
                        ctx.console.print(f"  [red]✗[/red] {path}")
                        ctx.console.print(f"    [dim]{desc}[/dim]")
                        ctx.console.print(
                            f"    [dim]Expected: → {expected_source}[/dim]"
                        )
                    elif diff_type == "broken":
                        ctx.console.print(f"  [red]✗[/red] {path}")
                        ctx.console.print(f"    [dim]{desc}[/dim]")
                    elif diff_type == "wrong":
                        ctx.console.print(f"  [yellow]⚠[/yellow] {path}")
                        ctx.console.print(f"    [dim]{desc}[/dim]")
                        ctx.console.print(
                            f"    [dim]Expected: → {expected_source}[/dim]"
                        )
                        if content_diff:
                            ctx.console.print(content_diff)
                    elif diff_type == "file":
                        ctx.console.print(f"  [yellow]⚠[/yellow] {path}")
                        ctx.console.print(f"    [dim]{desc}[/dim]")
                        ctx.console.print(
                            f"    [dim]Expected: → {expected_source}[/dim]"
                        )
                        if content_diff:
                            ctx.console.print(content_diff)

                ctx.console.print()
                found_differences = True

        return ComponentResult(ok=not found_differences, changed=found_differences)

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import remove_symlink

        console = get_console(ctx)
        total_removed = 0
        total_skipped = 0

        console.print("\n[bold cyan]Config Files[/bold cyan]")
        for target in ctx.selected_targets:
            console.print(f"\n[bold]{target.name}[/bold]")

            for tgt, _source in target.get_filtered_symlinks():
                if _is_specialized_path(tgt):
                    continue
                success, message = remove_symlink(tgt, ctx.yes)

                if success:
                    console.print(f"  [green]✓[/green] {tgt} removed")
                    total_removed += 1
                elif "Does not exist" in message:
                    console.print(f"  [dim]•[/dim] {tgt} [dim](not installed)[/dim]")
                else:
                    console.print(f"  [yellow]○[/yellow] {tgt} [dim]({message})[/dim]")
                    total_skipped += 1

        return ComponentResult(
            changed=total_removed > 0,
            counts={"removed": total_removed, "skipped": total_skipped},
        )
