"""MCP lifecycle component."""

from __future__ import annotations

from typing import Any

import click

from ai_rules.agents.base import Agent
from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    MCPPlan,
)


class MCPComponent(Component):
    label = "MCPs"
    display_name = "MCPs"
    component_id = "mcps"

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.mcp import OperationResult

        updated = 0
        skipped = 0
        errors = 0

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue
            if target.is_settings_file_excluded:
                continue
            mgr = target.get_mcp_manager()
            if mgr is None:
                continue

            result, message, conflicts = target.install_mcps(
                force=ctx.yes, dry_run=ctx.dry_run
            )

            if conflicts and not ctx.yes:
                ctx.console.print(
                    f"\n[bold yellow]MCP Conflicts Detected ({target.name}):[/bold yellow]"
                )
                expected_mcps = mgr.load_managed_mcps(ctx.config_dir, ctx.config)
                installed_mcps = mgr._read_installed()

                for conflict_name in conflicts:
                    expected = expected_mcps.get(conflict_name, {})
                    installed = installed_mcps.get(conflict_name, {})
                    if expected and installed:
                        diff = mgr.format_diff(conflict_name, expected, installed)
                        ctx.console.print(f"\n{diff}\n")

                if not ctx.dry_run and not click.confirm(
                    "Overwrite local changes?", default=False
                ):
                    from ai_rules.cli.display import print_warning

                    print_warning("Skipped MCP installation")
                    skipped += 1
                else:
                    result, message, _ = target.install_mcps(
                        force=True, dry_run=ctx.dry_run
                    )
                    from ai_rules.cli.display import print_success

                    print_success(f"{target.name}: {message}", indent=2)
                    updated += 1
            elif result == OperationResult.UPDATED:
                from ai_rules.cli.display import print_success

                print_success(f"{target.name}: {message}", indent=2)
                updated += 1
            elif result == OperationResult.ALREADY_INSTALLED:
                from ai_rules.cli.display import print_skipped

                print_skipped(f"{target.name}: {message}", indent=2)
            elif result != OperationResult.NOT_FOUND:
                from ai_rules.cli.display import print_warning

                print_warning(f"{target.name}: {message}", indent=2)
                errors += 1

        return ComponentResult(
            changed=updated > 0,
            counts={
                "mcp_updated": updated,
                "mcp_skipped": skipped,
                "mcp_errors": errors,
            },
        )

    def plan(self, ctx: CliContext) -> ComponentPlan:
        from ai_rules.mcp import OperationResult

        install_ops: list[tuple[str, dict[str, Any]]] = []
        conflict_targets: list[str] = []

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue
            if target.is_settings_file_excluded:
                continue
            mgr = target.get_mcp_manager()
            if mgr is None:
                continue

            # Dry-run detect to find what needs installing and what conflicts exist
            result, _message, conflicts = target.install_mcps(
                force=ctx.yes, dry_run=True
            )

            if result == OperationResult.NOT_FOUND:
                continue

            if conflicts and not ctx.yes:
                conflict_targets.append(target.name)
            else:
                native_mcps = mgr.load_managed_mcps(ctx.config_dir, ctx.config)
                install_ops.append((target.name, native_mcps))

        has_changes = bool(install_ops or conflict_targets)
        return MCPPlan(
            has_changes=has_changes,
            install_ops=install_ops,
            conflict_targets=conflict_targets,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, MCPPlan):
            return ComponentResult()

        from ai_rules.mcp import OperationResult

        updated = 0
        skipped = 0
        errors = 0

        from ai_rules.cli.display import (
            print_skipped,
            print_success,
            print_warning,
        )

        # Targets with conflicts that can't be resolved without a prompt — skip them.
        # The serial install() path handles prompt-based conflict resolution.
        for target_name in plan.conflict_targets:
            print_warning(
                f"{target_name}: MCP conflicts detected, skipping (use -y to force-apply)",
                indent=2,
            )
            skipped += 1

        # Install non-conflict targets
        install_target_names = {name for name, _ in plan.install_ops}
        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue
            if target.is_settings_file_excluded:
                continue
            if target.get_mcp_manager() is None:
                continue
            if target.name not in install_target_names:
                continue

            result, message, conflicts = target.install_mcps(
                force=ctx.yes, dry_run=ctx.dry_run
            )

            if result == OperationResult.UPDATED:
                print_success(f"{target.name}: {message}", indent=2)
                updated += 1
            elif result == OperationResult.ALREADY_INSTALLED:
                print_skipped(f"{target.name}: {message}", indent=2)
            elif result != OperationResult.NOT_FOUND:
                print_warning(f"{target.name}: {message}", indent=2)
                errors += 1

        return ComponentResult(
            changed=updated > 0,
            counts={
                "mcp_updated": updated,
                "mcp_skipped": skipped,
                "mcp_errors": errors,
            },
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.display import dim, print_dim
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        all_correct = True

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue
            if target.is_settings_file_excluded:
                continue

            mcp_status = target.get_mcp_status()
            if mcp_status is None or not (
                mcp_status.managed_mcps
                or mcp_status.unmanaged_mcps
                or mcp_status.pending_mcps
                or mcp_status.stale_mcps
            ):
                continue

            mgr = target.get_mcp_manager()
            console.print(f"[bold]{target.name}[/bold]")
            for name in sorted(mcp_status.managed_mcps.keys()):
                is_installed = mcp_status.installed.get(name, False)
                has_override = mcp_status.has_overrides.get(name, False)
                status_text = (
                    "[green]Installed[/green]"
                    if is_installed
                    else "[yellow]Outdated[/yellow]"
                )
                override_text = ", override" if has_override else ""
                console.print(
                    f"  {name:<20} {status_text} {dim(f'(managed{override_text})')}"
                )
                if not is_installed and mgr is not None:
                    expected = mgr.load_managed_mcps(ctx.config_dir, ctx.config).get(
                        name, {}
                    )
                    installed_config = mcp_status.managed_mcps.get(name, {})
                    diff = mgr.format_diff(name, expected, installed_config)
                    if diff:
                        for line in diff.split("\n"):
                            if line.startswith("MCP"):
                                continue
                            if line.strip():
                                print_dim(line, indent=4)
                    all_correct = False
            for name in sorted(mcp_status.pending_mcps.keys()):
                has_override = mcp_status.has_overrides.get(name, False)
                override_text = ", override" if has_override else ""
                console.print(
                    f"  {name:<20} [yellow]Not installed[/yellow] {dim(f'(managed{override_text})')}"
                )
                if mgr is not None:
                    expected = mcp_status.pending_mcps.get(name, {})
                    pending_output = mgr.format_pending(name, expected)
                    if pending_output:
                        console.print(pending_output)
                all_correct = False
            for name in sorted(mcp_status.stale_mcps.keys()):
                console.print(
                    f"  {name:<20} [red]Should be removed[/red] {dim('(no longer in config)')}"
                )
                all_correct = False
            for name in sorted(mcp_status.unmanaged_mcps.keys()):
                console.print(f"  {name:<20} {dim('Unmanaged')}")
            console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.mcp import OperationResult

        removed = 0
        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue
            if target.is_settings_file_excluded:
                continue
            if target.get_mcp_manager() is None:
                continue

            result, message = target.uninstall_mcps()
            if result == OperationResult.REMOVED:
                from ai_rules.cli.display import print_success

                print_success(message, indent=2)
                removed += 1
            elif result == OperationResult.NOT_FOUND:
                from ai_rules.cli.display import print_unchanged

                print_unchanged(message, indent=2)

        return ComponentResult(changed=removed > 0, counts={"removed": removed})
