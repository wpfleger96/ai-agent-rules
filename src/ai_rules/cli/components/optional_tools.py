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
    component_id = "tools"

    def plan(self, ctx: CliContext) -> OptionalToolsPlan:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.installer import _is_recall_configured

        stale: list[str] = []
        if is_command_available("recall") and not _is_recall_configured(ctx.config):
            stale.append("recall")

        return OptionalToolsPlan(has_changes=True, stale_tool_names=stale)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, OptionalToolsPlan):
            return ComponentResult()

        from ai_rules.bootstrap import (
            ToolSource,
            ensure_recall_installed,
            ensure_statusline_installed,
            get_effective_install_source,
        )
        from ai_rules.bootstrap.installer import ensure_recall_uninstalled
        from ai_rules.cli.display import print_dim, print_success, print_warning
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)

        # Remove stale tools first
        for tool_name in plan.stale_tool_names:
            if tool_name == "recall":
                result, message = ensure_recall_uninstalled(dry_run=ctx.dry_run)
                if result == "uninstalled":
                    print_success("Removed stale tool: recall")
                    console.print()
                elif result == "would_uninstall" and ctx.dry_run and message:
                    print_dim(message)
                    console.print()
                elif result == "failed":
                    print_warning(f"Failed to remove recall: {message}")
                    console.print()

        recall_result, recall_message = ensure_recall_installed(
            dry_run=ctx.dry_run, config=ctx.config
        )
        if recall_result == "installed":
            if ctx.dry_run and recall_message:
                print_dim(recall_message)
                console.print()
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
            print_dim(recall_message)
            console.print()
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
                print_dim(statusline_message)
                console.print()
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
            is_command_available,
        )
        from ai_rules.bootstrap.installer import (
            _is_recall_configured,
            ensure_recall_uninstalled,
        )
        from ai_rules.cli.display import print_dim, print_success, print_warning

        # Remove stale tools first
        if is_command_available("recall") and not _is_recall_configured(ctx.config):
            result, message = ensure_recall_uninstalled(dry_run=ctx.dry_run)
            if result == "uninstalled":
                print_success("Removed stale tool: recall")
                ctx.console.print()
            elif result == "would_uninstall" and ctx.dry_run and message:
                print_dim(message)
                ctx.console.print()
            elif result == "failed":
                print_warning(f"Failed to remove recall: {message}")
                ctx.console.print()

        recall_result, recall_message = ensure_recall_installed(
            dry_run=ctx.dry_run, config=ctx.config
        )
        if recall_result == "installed":
            if ctx.dry_run and recall_message:
                print_dim(recall_message)
                ctx.console.print()
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
            print_dim(recall_message)
            ctx.console.print()
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
                print_dim(statusline_message)
                ctx.console.print()
            else:
                print_success("Installed claude-statusline")
                ctx.console.print()
        elif statusline_result == "failed":
            print_warning("Failed to install claude-statusline (continuing anyway)")
            ctx.console.print()

        return ComponentResult()

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap.installer import ensure_recall_uninstalled
        from ai_rules.cli.display import print_success, print_unchanged, print_warning

        result, message = ensure_recall_uninstalled(dry_run=ctx.dry_run)
        if result == "uninstalled":
            print_success("Removed recall", indent=2)
        elif result == "failed":
            print_warning(f"Failed to remove recall: {message}", indent=2)
        elif result == "not_installed":
            print_unchanged("recall not installed", indent=2)

        return ComponentResult(changed=(result == "uninstalled"))

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.installer import _is_recall_configured
        from ai_rules.cli.display import print_absent, print_success, print_warning
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
        elif is_command_available("recall"):
            # recall is installed but not configured — stale
            print_warning(
                "recall installed but not configured (will be removed on next install)",
                indent=2,
            )
            missing += 1

        console.print()
        return ComponentResult(counts={"optional_missing": missing})
