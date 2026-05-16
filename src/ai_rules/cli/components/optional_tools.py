"""Optional tool lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    OptionalToolsPlan,
)


class OptionalToolsComponent(Component):
    label = "Optional Tools"
    display_name = "Optional Tools"
    component_id = "tools"

    def plan(self, ctx: CliContext) -> OptionalToolsPlan:
        return OptionalToolsPlan(has_changes=True)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, OptionalToolsPlan):
            return ComponentResult()

        from ai_rules.bootstrap import (
            ToolSource,
            ensure_recall_installed,
            ensure_statusline_installed,
            get_effective_install_source,
        )
        from ai_rules.cli.display import print_success, print_warning
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)

        recall_result, recall_message = ensure_recall_installed(
            dry_run=ctx.dry_run, config=ctx.config
        )
        if recall_result == "installed":
            if ctx.dry_run and recall_message:
                console.print(f"[dim]{recall_message}[/dim]\n")
            else:
                print_success("Installed recall")
                console.print()
        elif recall_result in ("upgraded", "source_switched"):
            if recall_message:
                print_success(f"Updated recall ({recall_message})")
            else:
                print_success("Updated recall")
            console.print()
        elif recall_result == "upgrade_available" and ctx.dry_run and recall_message:
            console.print(f"[dim]{recall_message}[/dim]\n")
        elif recall_result == "failed":
            print_warning("Failed to install recall (continuing anyway)")
            console.print()

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
                console.print(f"[dim]{statusline_message}[/dim]\n")
            else:
                print_success("Installed claude-statusline")
                console.print()
        elif statusline_result == "failed":
            print_warning("Failed to install claude-statusline (continuing anyway)")
            console.print()

        return ComponentResult()

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import (
            ToolSource,
            ensure_recall_installed,
            ensure_statusline_installed,
            get_effective_install_source,
        )
        from ai_rules.cli.display import print_success, print_warning

        recall_result, recall_message = ensure_recall_installed(
            dry_run=ctx.dry_run, config=ctx.config
        )
        if recall_result == "installed":
            if ctx.dry_run and recall_message:
                ctx.console.print(f"[dim]{recall_message}[/dim]\n")
            else:
                print_success("Installed recall")
                ctx.console.print()
        elif recall_result in ("upgraded", "source_switched"):
            if recall_message:
                print_success(f"Updated recall ({recall_message})")
            else:
                print_success("Updated recall")
            ctx.console.print()
        elif recall_result == "upgrade_available" and ctx.dry_run and recall_message:
            ctx.console.print(f"[dim]{recall_message}[/dim]\n")
        elif recall_result == "failed":
            print_warning("Failed to install recall (continuing anyway)")
            ctx.console.print()

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
                print_success("Installed claude-statusline")
                ctx.console.print()
        elif statusline_result == "failed":
            print_warning("Failed to install claude-statusline (continuing anyway)")
            ctx.console.print()

        return ComponentResult()

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.installer import _is_recall_configured
        from ai_rules.cli.display import print_absent, print_success
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        missing = 0
        if is_command_available("claude-statusline"):
            print_success("claude-statusline installed", indent=2)
        else:
            print_absent("claude-statusline not installed", indent=2)
            missing += 1

        if _is_recall_configured(ctx.config):
            if is_command_available("recall"):
                print_success("recall installed", indent=2)
            else:
                print_absent("recall not installed", indent=2)
                missing += 1

        console.print()
        return ComponentResult(counts={"optional_missing": missing})
