"""Config files lifecycle component."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from ai_rules.targets.base import ConfigTarget

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    ConfigPlan,
)

SPECIALIZED_PATH_PARTS = ("/agents/", "/commands/", "/skills/", "/hooks/")


def _is_specialized_path(target_owner: ConfigTarget, target: Path) -> bool:
    from ai_rules.agents.base import Agent

    if not isinstance(target_owner, Agent):
        return False
    target_str = target.as_posix()
    return any(part in target_str for part in SPECIALIZED_PATH_PARTS)


def _get_copy_mode_targets(agents: list[ConfigTarget]) -> set[Path]:
    """Collect expanded copy-mode target paths from all agents."""
    result: set[Path] = set()
    for agent in agents:
        result.update(agent.copy_mode_targets)
    return result


# status_code -> (severity, fixed annotation or None to use the check message)
_STATUS_DISPLAY: dict[str, tuple[str, str | None]] = {
    "missing": ("error", "not installed"),
    "broken": ("error", "broken symlink"),
    "wrong_target": ("warning", None),
    "not_symlink": ("warning", "not a symlink"),
    "stale_copy": ("warning", "copy out of date"),
    "not_copy": ("warning", "expected managed copy, found symlink"),
    "error": ("error", None),
}


def _display_symlink_status(
    status_code: str,
    target: Path,
    source: Path,
    message: str,
    console: Console | None = None,
) -> bool:

    from ai_rules.cli.display import (
        dim,
        get_console,
        print_error,
        print_success,
        print_warning,
    )
    from ai_rules.symlinks import get_status_diff

    target_display = str(target)
    if source.is_dir():
        target_display = target_display.rstrip("/") + "/"

    if status_code == "correct":
        print_success(target_display, indent=2)
        return True

    if status_code not in _STATUS_DISPLAY:
        return True

    severity, annotation = _STATUS_DISPLAY[status_code]
    printer = print_error if severity == "error" else print_warning
    printer(f"{target_display} {dim(f'({annotation or message})')}", indent=2)

    diff_output = get_status_diff(status_code, target.expanduser(), source)
    if diff_output:
        active_console: Console = console or get_console()
        active_console.print(diff_output)

    return False


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
                if not _is_specialized_path(agent, tgt)
            ]
            symlink_ops.extend(config_symlinks)

        copy_targets = _get_copy_mode_targets(list(ctx.selected_targets))

        return ConfigPlan(
            has_changes=bool(symlink_ops),
            symlink_ops=symlink_ops,
            excluded_count=excluded_count,
            copy_targets=copy_targets,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, ConfigPlan):
            return ComponentResult()

        from ai_rules.cli import cleanup_deprecated_symlinks
        from ai_rules.cli.display import print_symlink_result
        from ai_rules.symlinks import create_file_copy, create_symlink

        counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}

        for target, source in plan.symlink_ops:
            if target.expanduser() in plan.copy_targets:
                result, message = create_file_copy(target, source, True, ctx.dry_run)
            else:
                result, message = create_symlink(target, source, True, ctx.dry_run)

            counts[print_symlink_result(result, target, source, message)] += 1

        cleanup_deprecated_symlinks(
            list(ctx.selected_targets), ctx.config_dir, ctx.dry_run
        )

        return ComponentResult(
            ok=counts["errors"] == 0,
            changed=bool(counts["created"] or counts["updated"]),
            counts={**counts, "excluded": plan.excluded_count},
        )

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli import cleanup_deprecated_symlinks
        from ai_rules.cli.display import print_dim, print_symlink_result
        from ai_rules.symlinks import create_file_copy, create_symlink

        counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}
        excluded = 0
        effective_force = ctx.yes or not ctx.dry_run
        copy_targets = _get_copy_mode_targets(list(ctx.selected_targets))

        for agent in ctx.selected_targets:
            ctx.console.print(f"\n[bold]{agent.name}[/bold]")

            filtered_symlinks = agent.get_filtered_symlinks()
            user_excluded_count = len(agent.symlinks) - len(filtered_symlinks)

            config_symlinks = [
                (tgt, src)
                for tgt, src in filtered_symlinks
                if not _is_specialized_path(agent, tgt)
            ]

            if user_excluded_count > 0:
                print_dim(f"({user_excluded_count} symlink(s) excluded)", indent=2)
                excluded += user_excluded_count

            for target, source in config_symlinks:
                if target.expanduser() in copy_targets:
                    result, message = create_file_copy(
                        target, source, effective_force, ctx.dry_run
                    )
                else:
                    result, message = create_symlink(
                        target, source, effective_force, ctx.dry_run
                    )

                counts[print_symlink_result(result, target, source, message)] += 1

        cleanup_deprecated_symlinks(
            list(ctx.selected_targets), ctx.config_dir, ctx.dry_run
        )

        return ComponentResult(
            ok=counts["errors"] == 0,
            changed=bool(counts["created"] or counts["updated"]),
            counts={**counts, "excluded": excluded},
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.display import dim, print_skipped
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import check_file_copy, check_symlink

        console = get_console(ctx)
        all_correct = True
        copy_targets = _get_copy_mode_targets(list(ctx.selected_targets))

        for target in ctx.selected_targets:
            console.print(f"[bold]{target.name}[/bold]")

            filtered_symlinks = target.get_filtered_symlinks()
            excluded_symlinks = [
                (tgt, source)
                for tgt, source in target.symlinks
                if (tgt, source) not in filtered_symlinks
            ]

            for tgt, source in filtered_symlinks:
                if _is_specialized_path(target, tgt):
                    continue

                if tgt.expanduser() in copy_targets:
                    status_code, message = check_file_copy(tgt, source)
                else:
                    status_code, message = check_symlink(tgt, source)
                is_correct = _display_symlink_status(
                    status_code, tgt, source, message, console
                )
                all_correct = all_correct and is_correct

            for tgt, _source in excluded_symlinks:
                print_skipped(f"{tgt} {dim('(excluded by config)')}", indent=2)

            console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.display import print_dim, print_error, print_warning
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import (
            check_file_copy,
            check_symlink,
            get_content_diff,
            get_status_diff,
        )

        console = get_console(ctx)
        found_differences = False
        copy_targets = _get_copy_mode_targets(list(ctx.selected_targets))

        for target in ctx.selected_targets:
            target_has_diff = False
            target_diffs: list[tuple[Path, Path, str, str, str | None]] = []

            for tgt, source in target.get_filtered_symlinks():
                if _is_specialized_path(target, tgt):
                    continue
                target_path = tgt.expanduser()
                if target_path in copy_targets:
                    status_code, message = check_file_copy(target_path, source)
                else:
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
                elif status_code in ("not_symlink", "stale_copy"):
                    diff_output = get_status_diff(status_code, target_path, source)
                    desc = (
                        "Copy out of date"
                        if status_code == "stale_copy"
                        else "Regular file (not symlink)"
                    )
                    target_diffs.append(
                        (
                            target_path,
                            source,
                            "file",
                            desc,
                            diff_output,
                        )
                    )
                    target_has_diff = True
                elif status_code == "not_copy":
                    target_diffs.append(
                        (
                            target_path,
                            source,
                            "file",
                            "Expected managed copy, found symlink",
                            None,
                        )
                    )
                    target_has_diff = True

            if target_has_diff:
                console.print(f"[bold]{target.name}[/bold]")
                for (
                    path,
                    expected_source,
                    diff_type,
                    desc,
                    content_diff,
                ) in target_diffs:
                    if diff_type == "missing":
                        print_error(str(path), indent=2)
                        print_dim(desc, indent=4)
                        print_dim(f"Expected: → {expected_source}", indent=4)
                    elif diff_type == "broken":
                        print_error(str(path), indent=2)
                        print_dim(desc, indent=4)
                    elif diff_type == "wrong":
                        print_warning(str(path), indent=2)
                        print_dim(desc, indent=4)
                        print_dim(f"Expected: → {expected_source}", indent=4)
                        if content_diff:
                            console.print(content_diff)
                    elif diff_type == "file":
                        print_warning(str(path), indent=2)
                        print_dim(desc, indent=4)
                        print_dim(f"Expected: → {expected_source}", indent=4)
                        if content_diff:
                            console.print(content_diff)

                console.print()
                found_differences = True

        return ComponentResult(ok=not found_differences, changed=found_differences)

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli import cleanup_deprecated_symlinks
        from ai_rules.cli.display import (
            dim,
            print_absent,
            print_success,
            print_unchanged,
        )
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import remove_file_copy, remove_symlink

        console = get_console(ctx)
        total_removed = 0
        total_skipped = 0
        copy_targets = _get_copy_mode_targets(list(ctx.selected_targets))

        for target in ctx.selected_targets:
            console.print(f"\n[bold]{target.name}[/bold]")

            for tgt, _source in target.get_filtered_symlinks():
                if _is_specialized_path(target, tgt):
                    continue
                if tgt.expanduser() in copy_targets:
                    success, message = remove_file_copy(tgt, ctx.yes)
                else:
                    success, message = remove_symlink(tgt, ctx.yes)

                if success:
                    print_success(f"{tgt} removed", indent=2)
                    total_removed += 1
                elif "Does not exist" in message:
                    print_unchanged(f"{tgt} {dim('(not installed)')}", indent=2)
                else:
                    print_absent(f"{tgt} {dim(f'({message})')}", indent=2)
                    total_skipped += 1

        cleanup_deprecated_symlinks(
            list(ctx.selected_targets), ctx.config_dir, ctx.dry_run
        )

        return ComponentResult(
            changed=total_removed > 0,
            counts={"removed": total_removed, "skipped": total_skipped},
        )
