"""Claude extension lifecycle component."""

from __future__ import annotations

from typing import Any

from ai_rules.cli.context import (
    ClaudeExtensionsPlan,
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
)


class ClaudeExtensionsComponent(Component):
    label = "Claude Extensions"
    display_name = "Claude Extensions"
    component_id = "extensions"

    def install(self, ctx: CliContext) -> ComponentResult:
        target = ctx.selected_target("claude")
        if target is None:
            return ComponentResult()

        from ai_rules.claude_extensions import ClaudeExtensionManager
        from ai_rules.cli.display import print_error
        from ai_rules.symlinks import SymlinkResult, create_symlink

        ext_manager = ClaudeExtensionManager(ctx.config_dir)
        created = updated = unchanged = skipped = errors = 0

        ctx.console.print("\n[bold cyan]Claude Extensions[/bold cyan]")
        for ext_type in ClaudeExtensionManager.USER_DIRS:
            managed = ext_manager._get_managed_extensions(ext_type)
            if not managed:
                continue

            ctx.console.print(f"\n[bold]{ext_type.capitalize()}:[/bold]")
            user_dir = ClaudeExtensionManager.USER_DIRS[ext_type].expanduser()
            pattern = ClaudeExtensionManager.PATTERNS[ext_type]
            suffix = pattern.lstrip("*")

            for name, source_path in managed.items():
                filename = f"{name}{suffix}"
                target_path = user_dir / filename
                result, message = create_symlink(
                    target_path,
                    source_path,
                    force=ctx.yes or not ctx.dry_run,
                    dry_run=ctx.dry_run,
                )

                if result == SymlinkResult.CREATED:
                    ctx.console.print(
                        f"  [green]✓[/green] {target_path} → {source_path}"
                    )
                    created += 1
                elif result == SymlinkResult.ALREADY_CORRECT:
                    ctx.console.print(
                        f"  [dim]•[/dim] {target_path} [dim](already correct)[/dim]"
                    )
                    unchanged += 1
                elif result == SymlinkResult.UPDATED:
                    ctx.console.print(
                        f"  [yellow]↻[/yellow] {target_path} → {source_path}"
                    )
                    updated += 1
                elif result == SymlinkResult.SKIPPED:
                    ctx.console.print(
                        f"  [yellow]○[/yellow] {target_path} [dim](skipped)[/dim]"
                    )
                    skipped += 1
                elif result == SymlinkResult.ERROR:
                    print_error(f"{target_path}: {message}", indent=2)
                    errors += 1

        return ComponentResult(
            ok=errors == 0,
            changed=bool(created or updated),
            counts={
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "skipped": skipped,
                "errors": errors,
            },
        )

    def plan(self, ctx: CliContext) -> ComponentPlan:
        target = ctx.selected_target("claude")
        if target is None:
            return ClaudeExtensionsPlan()

        from ai_rules.claude_extensions import ClaudeExtensionManager

        ext_manager = ClaudeExtensionManager(ctx.config_dir)
        symlink_ops: list[tuple[str, Any, Any]] = []

        for ext_type in ClaudeExtensionManager.USER_DIRS:
            managed = ext_manager._get_managed_extensions(ext_type)
            if not managed:
                continue

            user_dir = ClaudeExtensionManager.USER_DIRS[ext_type].expanduser()
            pattern = ClaudeExtensionManager.PATTERNS[ext_type]
            suffix = pattern.lstrip("*")

            for name, source_path in managed.items():
                filename = f"{name}{suffix}"
                target_path = user_dir / filename
                symlink_ops.append((ext_type, target_path, source_path))

        return ClaudeExtensionsPlan(
            has_changes=bool(symlink_ops),
            symlink_ops=symlink_ops,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, ClaudeExtensionsPlan):
            return ComponentResult()

        from ai_rules.cli.display import print_error
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import SymlinkResult, create_symlink

        console = get_console(ctx)
        created = updated = unchanged = skipped = errors = 0

        console.print("\n[bold cyan]Claude Extensions[/bold cyan]")

        current_section = None
        for ext_type, target_path, source_path in plan.symlink_ops:
            if ext_type != current_section:
                console.print(f"\n[bold]{ext_type.capitalize()}:[/bold]")
                current_section = ext_type

            result, message = create_symlink(
                target_path,
                source_path,
                force=True,
                dry_run=ctx.dry_run,
            )

            if result == SymlinkResult.CREATED:
                console.print(f"  [green]✓[/green] {target_path} → {source_path}")
                created += 1
            elif result == SymlinkResult.ALREADY_CORRECT:
                console.print(
                    f"  [dim]•[/dim] {target_path} [dim](already correct)[/dim]"
                )
                unchanged += 1
            elif result == SymlinkResult.UPDATED:
                console.print(f"  [yellow]↻[/yellow] {target_path} → {source_path}")
                updated += 1
            elif result == SymlinkResult.SKIPPED:
                console.print(
                    f"  [yellow]○[/yellow] {target_path} [dim](skipped)[/dim]"
                )
                skipped += 1
            elif result == SymlinkResult.ERROR:
                print_error(f"{target_path}: {message}", indent=2)
                errors += 1

        return ComponentResult(
            ok=errors == 0,
            changed=bool(created or updated),
            counts={
                "created": created,
                "updated": updated,
                "unchanged": unchanged,
                "skipped": skipped,
                "errors": errors,
            },
        )

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        target = ctx.selected_target("claude")
        if target is None:
            return ComponentResult()

        from ai_rules.claude_extensions import ClaudeExtensionManager
        from ai_rules.cli.runner import get_console
        from ai_rules.symlinks import remove_symlink

        console = get_console(ctx)
        ext_manager = ClaudeExtensionManager(ctx.config_dir)
        removed = skipped = 0

        console.print("\n[bold cyan]Claude Extensions[/bold cyan]")
        for ext_type in ClaudeExtensionManager.USER_DIRS:
            managed = ext_manager._get_managed_extensions(ext_type)
            if not managed:
                continue

            console.print(f"\n[bold]{ext_type.capitalize()}:[/bold]")
            user_dir = ClaudeExtensionManager.USER_DIRS[ext_type].expanduser()
            pattern = ClaudeExtensionManager.PATTERNS[ext_type]
            suffix = pattern.lstrip("*")

            for name in managed:
                filename = f"{name}{suffix}"
                target_path = user_dir / filename
                success, message = remove_symlink(target_path, force=ctx.yes)

                if success:
                    console.print(f"  [green]✓[/green] {target_path} removed")
                    removed += 1
                elif "Does not exist" in message:
                    console.print(
                        f"  [dim]•[/dim] {target_path} [dim](not installed)[/dim]"
                    )
                else:
                    console.print(
                        f"  [yellow]○[/yellow] {target_path} [dim]({message})[/dim]"
                    )
                    skipped += 1

        return ComponentResult(
            changed=removed > 0,
            counts={"removed": removed, "skipped": skipped},
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        target = ctx.selected_target("claude")
        if target is None:
            return ComponentResult()

        extension_status = target.get_extension_status()  # type: ignore[attr-defined]

        merged_settings_for_hooks: dict[str, Any] = {}
        base_settings_path = target._base_settings_path
        if base_settings_path.exists():
            from ai_rules.config import CONFIG_PARSE_ERRORS, load_config_file

            try:
                base_settings = load_config_file(
                    base_settings_path, target.config_file_format
                )
                merged_settings_for_hooks = ctx.config.merge_settings(
                    target.target_id, base_settings
                )
            except CONFIG_PARSE_ERRORS:
                pass

        from ai_rules.claude_extensions import ClaudeExtensionManager
        from ai_rules.cli.runner import get_console

        ext_manager = ClaudeExtensionManager(ctx.config_dir)
        all_orphaned = ext_manager.get_all_orphaned()
        all_correct = True
        console = get_console(ctx)

        for ext_type, type_name in [
            ("agents", "Agents"),
            ("commands", "Commands"),
            ("hooks", "Hooks"),
        ]:
            type_status = getattr(extension_status, ext_type)

            orphaned_hooks = {}
            if ext_type == "hooks" and merged_settings_for_hooks:
                orphaned_hooks = ext_manager.get_orphaned_hooks(
                    merged_settings_for_hooks
                )

            if not any(
                [
                    type_status.managed_installed,
                    type_status.managed_pending,
                    type_status.managed_wrong_target,
                    type_status.unmanaged,
                    orphaned_hooks,
                ]
            ):
                continue

            console.print(f"[bold]{type_name}[/bold]")

            for name in sorted(type_status.managed_installed.keys()):
                console.print(
                    f"  {name:<20} [green]Installed[/green] [dim](managed)[/dim]"
                )

            for name, item in sorted(type_status.managed_wrong_target.items()):
                if item.is_broken:
                    console.print(
                        f"  {name:<20} [red]Broken symlink[/red] [dim](managed)[/dim]"
                    )
                else:
                    console.print(
                        f"  {name:<20} [yellow]Wrong target[/yellow] [dim](managed)[/dim]"
                    )
                    if item.actual_source and item.expected_source:
                        console.print(f"    [dim]Points to {item.actual_source}[/dim]")
                        console.print(
                            f"    [dim]Expected: → {item.expected_source}[/dim]"
                        )
                        from ai_rules.symlinks import get_content_diff

                        diff_output = get_content_diff(
                            item.actual_source, item.expected_source
                        )
                        if diff_output:
                            console.print(diff_output)
                all_correct = False

            for name in sorted(type_status.managed_pending.keys()):
                console.print(
                    f"  {name:<20} [yellow]Not installed[/yellow] [dim](managed)[/dim]"
                )
                all_correct = False

            for name in sorted(type_status.unmanaged.keys()):
                if ext_type in all_orphaned and name in all_orphaned[ext_type]:
                    console.print(f"  {name:<20} [yellow]Orphaned[/yellow]")
                else:
                    console.print(f"  {name:<20} [dim]Unmanaged[/dim]")

            for name in sorted(orphaned_hooks.keys()):
                console.print(
                    f"  {name:<20} [yellow]No configuration[/yellow] [dim](orphaned)[/dim]"
                )
                all_correct = False
            console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)
