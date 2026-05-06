"""Optional tool lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class OptionalToolsComponent(Component):
    label = "Optional Tools"

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import (
            ToolSource,
            ensure_recall_installed,
            ensure_statusline_installed,
            get_effective_install_source,
        )

        recall_result, recall_message = ensure_recall_installed(
            dry_run=ctx.dry_run, config=ctx.config
        )
        if recall_result == "installed":
            if ctx.dry_run and recall_message:
                ctx.console.print(f"[dim]{recall_message}[/dim]\n")
            else:
                ctx.console.print("[green]✓[/green] Installed recall\n")
        elif recall_result in ("upgraded", "source_switched"):
            ctx.console.print(
                f"[green]✓[/green] Updated recall ({recall_message})\n"
                if recall_message
                else "[green]✓[/green] Updated recall\n"
            )
        elif recall_result == "upgrade_available" and ctx.dry_run and recall_message:
            ctx.console.print(f"[dim]{recall_message}[/dim]\n")
        elif recall_result == "failed":
            ctx.console.print(
                "[yellow]⚠[/yellow] Failed to install recall (continuing anyway)\n"
            )

        sl_source, sl_local_path = get_effective_install_source(
            "statusline", config=ctx.config
        )
        statusline_result, statusline_message = ensure_statusline_installed(
            dry_run=ctx.dry_run,
            from_github=sl_source == ToolSource.GITHUB,
            local_path=sl_local_path,
        )
        if statusline_result == "installed":
            if ctx.dry_run and statusline_message:
                ctx.console.print(f"[dim]{statusline_message}[/dim]\n")
            else:
                ctx.console.print("[green]✓[/green] Installed claude-statusline\n")
        elif statusline_result == "failed":
            ctx.console.print(
                "[yellow]⚠[/yellow] Failed to install claude-statusline (continuing anyway)\n"
            )

        return ComponentResult()

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.installer import _is_recall_configured

        ctx.console.print("[bold cyan]Optional Tools[/bold cyan]\n")

        missing = 0
        if is_command_available("claude-statusline"):
            ctx.console.print("  [green]✓[/green] claude-statusline installed")
        else:
            ctx.console.print("  [yellow]○[/yellow] claude-statusline not installed")
            missing += 1

        if _is_recall_configured(ctx.config):
            if is_command_available("recall"):
                ctx.console.print("  [green]✓[/green] recall installed")
            else:
                ctx.console.print("  [yellow]○[/yellow] recall not installed")
                missing += 1

        ctx.console.print()
        return ComponentResult(counts={"optional_missing": missing})
