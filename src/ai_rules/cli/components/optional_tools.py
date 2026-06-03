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

    def _install_active_tools(self, ctx: CliContext) -> None:
        from ai_rules.bootstrap import (
            ensure_tool_installed,
            get_effective_install_source,
        )
        from ai_rules.bootstrap.registry import ACTIVE_TOOLS

        for active in ACTIVE_TOOLS:
            if active.is_configured is not None and not active.is_configured(
                ctx.config
            ):
                continue

            spec = active.get_install_spec()
            source, local_path = get_effective_install_source(
                active.tool_id, config=ctx.config
            )

            result, message = ensure_tool_installed(
                spec, dry_run=ctx.dry_run, source=source, local_path=local_path
            )
            self._emit_install_result(active.tool_id, result, message, ctx)

    def _emit_install_result(
        self,
        tool_id: str,
        result: str,
        message: str | None,
        ctx: CliContext,
    ) -> None:
        from ai_rules.cli.display import print_dim, print_success, print_warning

        if result == "installed":
            if ctx.dry_run and message:
                print_dim(message)
            else:
                print_success(f"Installed {tool_id}")
            ctx.console.print()
        elif result in ("upgraded", "source_switched"):
            msg = f"Updated {tool_id}"
            if message:
                msg += f" ({message})"
            print_success(msg)
            ctx.console.print()
        elif result == "upgrade_available" and ctx.dry_run and message:
            print_dim(message)
            ctx.console.print()
        elif result == "failed":
            print_warning(f"Failed to install {tool_id} (continuing anyway)")
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

        self._remove_stale_tools(plan.stale_tool_names, ctx)
        self._install_active_tools(ctx)

        return ComponentResult()

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.bootstrap import is_command_available
        from ai_rules.bootstrap.registry import DEPRECATED_TOOLS

        stale: list[str] = []
        for spec in DEPRECATED_TOOLS:
            if not is_command_available(spec.command_name):
                continue
            if spec.is_configured is not None and spec.is_configured(ctx.config):
                continue
            stale.append(spec.tool_id)
        self._remove_stale_tools(stale, ctx)

        self._install_active_tools(ctx)

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
        from ai_rules.bootstrap.registry import ACTIVE_TOOLS, DEPRECATED_TOOLS
        from ai_rules.cli.display import print_absent, print_success, print_warning
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        missing = 0
        stale = 0

        for active in ACTIVE_TOOLS:
            spec = active.get_install_spec()
            if spec.is_installed():
                print_success(f"{active.tool_id} installed", indent=2)
            else:
                print_absent(f"{active.tool_id} not installed", indent=2)
                missing += 1

        for deprecated in DEPRECATED_TOOLS:
            is_configured = (
                deprecated.is_configured is not None
                and deprecated.is_configured(ctx.config)
            )
            is_installed = is_command_available(deprecated.command_name)

            if is_configured:
                if is_installed:
                    print_success(f"{deprecated.tool_id} installed", indent=2)
                else:
                    print_absent(f"{deprecated.tool_id} not installed", indent=2)
                    missing += 1
            elif is_installed:
                print_warning(
                    f"{deprecated.tool_id} installed but not configured (will be removed on next install)",
                    indent=2,
                )
                stale += 1

        console.print()
        return ComponentResult(
            counts={"optional_missing": missing, "optional_stale": stale}
        )
