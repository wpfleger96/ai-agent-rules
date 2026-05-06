"""Install confirmation lifecycle component."""

from __future__ import annotations

from rich.prompt import Confirm

from ai_rules.cli.context import CliContext, Component, ComponentResult


class InstallConfirmationComponent(Component):
    label = "Install Confirmation"

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.dry_run or ctx.yes:
            return ComponentResult()

        from ai_rules.cli import (
            _display_pending_plugin_changes,
            _display_pending_symlink_changes,
            check_first_run,
        )

        has_changes = _display_pending_symlink_changes(list(ctx.selected_targets))
        has_plugin_changes = _display_pending_plugin_changes(ctx.config)

        if has_changes or has_plugin_changes:
            ctx.console.print()
            if not Confirm.ask("Apply these changes?", default=True):
                ctx.console.print("[yellow]Installation cancelled[/yellow]")
                return ComponentResult(abort=True)
        elif not check_first_run(list(ctx.selected_targets), ctx.yes):
            ctx.console.print("[yellow]Installation cancelled[/yellow]")
            return ComponentResult(abort=True)

        return ComponentResult()
