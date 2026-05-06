"""Claude extension lifecycle component."""

from __future__ import annotations

from typing import Any

from ai_rules.cli.context import CliContext, Component, ComponentResult


class ClaudeExtensionsComponent(Component):
    label = "Claude Extensions"

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

        ext_manager = ClaudeExtensionManager(ctx.config_dir)
        all_orphaned = ext_manager.get_all_orphaned()
        all_correct = True
        rendered_header = False

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

            if not rendered_header:
                ctx.console.print("[bold cyan]Claude Extensions[/bold cyan]\n")
                rendered_header = True
            ctx.console.print(f"[bold]{type_name}:[/bold]")

            for name in sorted(type_status.managed_installed.keys()):
                ctx.console.print(
                    f"  {name:<20} [green]Installed[/green] [dim](managed)[/dim]"
                )

            for name, item in sorted(type_status.managed_wrong_target.items()):
                if item.is_broken:
                    ctx.console.print(
                        f"  {name:<20} [red]Broken symlink[/red] [dim](managed)[/dim]"
                    )
                else:
                    ctx.console.print(
                        f"  {name:<20} [yellow]Wrong target[/yellow] [dim](managed)[/dim]"
                    )
                    if item.actual_source and item.expected_source:
                        from ai_rules.symlinks import get_content_diff

                        diff_output = get_content_diff(
                            item.actual_source, item.expected_source
                        )
                        if diff_output:
                            ctx.console.print(diff_output)
                all_correct = False

            for name in sorted(type_status.managed_pending.keys()):
                ctx.console.print(
                    f"  {name:<20} [yellow]Not installed[/yellow] [dim](managed)[/dim]"
                )
                all_correct = False

            for name in sorted(type_status.unmanaged.keys()):
                if ext_type in all_orphaned and name in all_orphaned[ext_type]:
                    ctx.console.print(f"  {name:<20} [yellow]Orphaned[/yellow]")
                else:
                    ctx.console.print(f"  {name:<20} [dim]Unmanaged[/dim]")

            for name in sorted(orphaned_hooks.keys()):
                ctx.console.print(
                    f"  {name:<20} [yellow]No configuration[/yellow] [dim](orphaned)[/dim]"
                )
                all_correct = False
            ctx.console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)
