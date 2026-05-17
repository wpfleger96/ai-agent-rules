"""Claude plugin lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    PluginPlan,
)


class ClaudePluginComponent(Component):
    label = "Claude Plugins"
    component_id = "plugins"

    def _claude_selected(self, ctx: CliContext) -> bool:
        return ctx.selected_target("claude") is not None

    def plan(self, ctx: CliContext) -> PluginPlan:
        if not self._claude_selected(ctx) or not (
            ctx.config.plugins or ctx.config.marketplaces
        ):
            return PluginPlan()
        return PluginPlan(has_changes=True)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, PluginPlan):
            return ComponentResult()

        if not plan.has_changes:
            return ComponentResult()

        from ai_rules.cli.display import (
            print_dim,
            print_skipped,
            print_success,
            print_warning,
        )
        from ai_rules.plugins import OperationResult, PluginManager

        plugin_manager = PluginManager()

        if not plugin_manager.is_cli_available():
            if not ctx.dry_run:
                print_skipped("Skipped plugin sync (claude CLI not available)")
            return ComponentResult()

        desired_plugins = ctx.config.get_plugin_configs()
        desired_marketplaces = ctx.config.get_marketplace_configs()

        plugin_result, message, warnings = plugin_manager.sync_plugins(
            desired_plugins, desired_marketplaces, dry_run=ctx.dry_run
        )

        if plugin_result == OperationResult.SUCCESS:
            print_success(message)
        elif plugin_result == OperationResult.ALREADY_INSTALLED:
            print_skipped(message)
        elif plugin_result == OperationResult.DRY_RUN:
            print_dim(message)
        elif plugin_result == OperationResult.ERROR:
            print_warning(message)

        for warning in warnings:
            print_warning(warning)

        return ComponentResult(
            changed=plugin_result in (OperationResult.SUCCESS, OperationResult.DRY_RUN),
            counts={"plugin_errors": int(plugin_result == OperationResult.ERROR)},
        )

    def install(self, ctx: CliContext) -> ComponentResult:
        if not self._claude_selected(ctx) or not (
            ctx.config.plugins or ctx.config.marketplaces
        ):
            return ComponentResult()

        from ai_rules.cli.display import (
            print_dim,
            print_skipped,
            print_success,
            print_warning,
        )
        from ai_rules.plugins import OperationResult, PluginManager

        plugin_manager = PluginManager()
        if not plugin_manager.is_cli_available():
            if not ctx.dry_run:
                print_skipped("Skipped plugin sync (claude CLI not available)")
            return ComponentResult()

        desired_plugins = ctx.config.get_plugin_configs()
        desired_marketplaces = ctx.config.get_marketplace_configs()

        plugin_result, message, warnings = plugin_manager.sync_plugins(
            desired_plugins, desired_marketplaces, dry_run=ctx.dry_run
        )

        if plugin_result == OperationResult.SUCCESS:
            print_success(message)
        elif plugin_result == OperationResult.ALREADY_INSTALLED:
            print_skipped(message)
        elif plugin_result == OperationResult.DRY_RUN:
            print_dim(message)
        elif plugin_result == OperationResult.ERROR:
            print_warning(message)

        for warning in warnings:
            print_warning(warning)

        return ComponentResult(
            changed=plugin_result in (OperationResult.SUCCESS, OperationResult.DRY_RUN),
            counts={"plugin_errors": int(plugin_result == OperationResult.ERROR)},
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        if not self._claude_selected(ctx):
            return ComponentResult()

        from ai_rules.cli import _get_plugin_status
        from ai_rules.cli.runner import get_console

        plugin_result = _get_plugin_status(ctx.config)
        if plugin_result is None:
            return ComponentResult()

        _plugin_manager, plugin_status = plugin_result
        desired_plugins = ctx.config.get_plugin_configs()
        all_correct = True

        if (
            plugin_status.installed
            or plugin_status.pending
            or plugin_status.extra
            or plugin_status.marketplaces_missing
        ):
            from ai_rules.cli.display import dim

            console = get_console(ctx)

            for marketplace in plugin_status.marketplaces_missing:
                mp_source = marketplace["source"]
                console.print(
                    f"  {marketplace['name']:<20} [yellow]Marketplace missing[/yellow] {dim(f'({mp_source})')}"
                )
                all_correct = False

            for plugin_config in desired_plugins:
                plugin_key = plugin_config.key
                if plugin_key in plugin_status.installed:
                    console.print(
                        f"  {plugin_config.name:<20} [green]Installed[/green] {dim('(managed)')}"
                    )
                else:
                    console.print(
                        f"  {plugin_config.name:<20} [yellow]Not installed[/yellow] {dim('(managed)')}"
                    )
                    all_correct = False

            for key in sorted(plugin_status.extra):
                console.print(f"  {key:<20} {dim('Unmanaged')}")
            console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)
