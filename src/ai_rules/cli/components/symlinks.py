"""Symlink lifecycle component."""

from __future__ import annotations

from pathlib import Path

from ai_rules.cli.context import CliContext, Component, ComponentResult

SPECIALIZED_STATUS_PATH_PARTS = ("/agents/", "/commands/", "/skills/", "/hooks/")


def _display_symlink_status(
    status_code: str,
    target: Path,
    source: Path,
    message: str,
    agent_label: str | None = None,
) -> bool:
    from rich.console import Console

    from ai_rules.symlinks import get_content_diff

    console = Console()

    target_str = str(target)
    if source.is_dir():
        target_str = target_str.rstrip("/") + "/"
    target_display = f"{agent_label} {target.name}" if agent_label else target_str

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


class SymlinkComponent(Component):
    label = "User-Level Configuration"

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli import install_user_symlinks

        results = install_user_symlinks(
            list(ctx.selected_targets), ctx.yes, ctx.dry_run
        )
        return ComponentResult(
            ok=results["errors"] == 0,
            changed=bool(results["created"] or results["updated"]),
            counts=results,
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.symlinks import check_symlink

        ctx.console.print("[bold cyan]User-Level Configuration[/bold cyan]\n")
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
                target_str = str(tgt)
                if any(part in target_str for part in SPECIALIZED_STATUS_PATH_PARTS):
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
        from ai_rules.symlinks import remove_symlink

        total_removed = 0
        total_skipped = 0

        ctx.console.print("\n[bold cyan]User-Level Configuration[/bold cyan]")
        for target in ctx.selected_targets:
            ctx.console.print(f"\n[bold]{target.name}[/bold]")

            for tgt, _source in target.get_filtered_symlinks():
                success, message = remove_symlink(tgt, ctx.yes)

                if success:
                    ctx.console.print(f"  [green]✓[/green] {tgt} removed")
                    total_removed += 1
                elif "Does not exist" in message:
                    ctx.console.print(
                        f"  [dim]•[/dim] {tgt} [dim](not installed)[/dim]"
                    )
                else:
                    ctx.console.print(
                        f"  [yellow]○[/yellow] {tgt} [dim]({message})[/dim]"
                    )
                    total_skipped += 1

        return ComponentResult(
            changed=total_removed > 0,
            counts={"removed": total_removed, "skipped": total_skipped},
        )
