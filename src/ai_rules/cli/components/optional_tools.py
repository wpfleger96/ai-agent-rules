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

    def _remove_stale_tools(
        self,
        stale_tool_ids: list[str],
        ctx: CliContext,
    ) -> None:
        from ai_rules.bootstrap.installer import ensure_tool_uninstalled
        from ai_rules.bootstrap.registry import DEPRECATED_TOOLS
        from ai_rules.cli.display import print_dim, print_success, print_warning

        specs_by_id = {s.tool_id: s for s in DEPRECATED_TOOLS}
        for tool_id in stale_tool_ids:
            spec = specs_by_id.get(tool_id)
            if spec is None:
                continue
            result, message = ensure_tool_uninstalled(
                spec.command_name, spec.package_name, dry_run=ctx.dry_run
            )
            if result == "uninstalled":
                print_success(f"Removed stale tool: {spec.tool_id}")
                ctx.console.print()
            elif result == "would_uninstall" and ctx.dry_run and message:
                print_dim(message)
                ctx.console.print()
            elif result == "failed":
                print_warning(f"Failed to remove {spec.tool_id}: {message}")
                ctx.console.print()

    def plan(self, ctx: CliContext) -> OptionalToolsPlan:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.registry import DEPRECATED_TOOLS

        stale: list[str] = []
        for spec in DEPRECATED_TOOLS:
            if not is_command_available(spec.command_name):
                continue
            if spec.is_configured is not None and spec.is_configured(ctx.config):
                continue
            stale.append(spec.tool_id)

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
        from ai_rules.cli.display import print_dim, print_success, print_warning
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)

        self._remove_stale_tools(plan.stale_tool_names, ctx)

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
        from ai_rules.bootstrap.registry import DEPRECATED_TOOLS
        from ai_rules.cli.display import print_dim, print_success, print_warning

        # Detect and remove stale tools
        stale: list[str] = []
        for spec in DEPRECATED_TOOLS:
            if not is_command_available(spec.command_name):
                continue
            if spec.is_configured is not None and spec.is_configured(ctx.config):
                continue
            stale.append(spec.tool_id)
        self._remove_stale_tools(stale, ctx)

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
        from ai_rules.bootstrap.installer import ensure_tool_uninstalled
        from ai_rules.bootstrap.registry import DEPRECATED_TOOLS
        from ai_rules.cli.display import (
            print_dim,
            print_success,
            print_unchanged,
            print_warning,
        )

        removed = 0
        for spec in DEPRECATED_TOOLS:
            result, message = ensure_tool_uninstalled(
                spec.command_name, spec.package_name, dry_run=ctx.dry_run
            )
            if result == "uninstalled":
                print_success(f"Removed {spec.tool_id}", indent=2)
                removed += 1
            elif result == "would_uninstall" and message:
                print_dim(message, indent=2)
                removed += 1
            elif result == "failed":
                print_warning(f"Failed to remove {spec.tool_id}: {message}", indent=2)
            elif result == "not_installed":
                print_unchanged(f"{spec.tool_id} not installed", indent=2)

        return ComponentResult(changed=removed > 0)

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.registry import DEPRECATED_TOOLS
        from ai_rules.cli.display import print_absent, print_success, print_warning
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        missing = 0
        stale = 0

        if is_command_available("claude-statusline"):
            print_success("claude-statusline installed", indent=2)
        else:
            print_absent("claude-statusline not installed", indent=2)
            missing += 1

        for spec in DEPRECATED_TOOLS:
            is_configured = spec.is_configured is not None and spec.is_configured(
                ctx.config
            )
            is_installed = is_command_available(spec.command_name)

            if is_configured:
                if is_installed:
                    print_success(f"{spec.tool_id} installed", indent=2)
                else:
                    print_absent(f"{spec.tool_id} not installed", indent=2)
                    missing += 1
            elif is_installed:
                print_warning(
                    f"{spec.tool_id} installed but not configured (will be removed on next install)",
                    indent=2,
                )
                stale += 1

        console.print()
        return ComponentResult(
            counts={"optional_missing": missing, "optional_stale": stale}
        )
