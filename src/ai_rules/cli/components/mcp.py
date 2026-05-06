"""MCP lifecycle component."""

from __future__ import annotations

from rich.prompt import Confirm

from ai_rules.agents.base import Agent
from ai_rules.cli.context import CliContext, Component, ComponentResult


class MCPComponent(Component):
    label = "MCPs"

    def install(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.mcp import OperationResult

        updated = 0
        skipped = 0
        errors = 0

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
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

                if not ctx.dry_run and not Confirm.ask(
                    "Overwrite local changes?", default=False
                ):
                    ctx.console.print("[yellow]Skipped MCP installation[/yellow]")
                    skipped += 1
                else:
                    result, message, _ = target.install_mcps(
                        force=True, dry_run=ctx.dry_run
                    )
                    ctx.console.print(f"[green]✓[/green] {target.name}: {message}")
                    updated += 1
            elif result == OperationResult.UPDATED:
                ctx.console.print(f"[green]✓[/green] {target.name}: {message}")
                updated += 1
            elif result == OperationResult.ALREADY_INSTALLED:
                ctx.console.print(f"[dim]○ {target.name}: {message}[/dim]")
            elif result != OperationResult.NOT_FOUND:
                ctx.console.print(f"[yellow]⚠[/yellow] {target.name}: {message}")
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
        all_correct = True
        rendered_header = False

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue

            mcp_status = target.get_mcp_status()
            if mcp_status is None or not (
                mcp_status.managed_mcps
                or mcp_status.unmanaged_mcps
                or mcp_status.pending_mcps
                or mcp_status.stale_mcps
            ):
                continue

            if not rendered_header:
                ctx.console.print("[bold cyan]MCPs[/bold cyan]\n")
                rendered_header = True

            mgr = target.get_mcp_manager()
            ctx.console.print(f"[bold]{target.name}:[/bold]")
            for name in sorted(mcp_status.managed_mcps.keys()):
                is_installed = mcp_status.installed.get(name, False)
                has_override = mcp_status.has_overrides.get(name, False)
                status_text = (
                    "[green]Installed[/green]"
                    if is_installed
                    else "[yellow]Outdated[/yellow]"
                )
                override_text = ", override" if has_override else ""
                ctx.console.print(
                    f"  {name:<20} {status_text} [dim](managed{override_text})[/dim]"
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
                                ctx.console.print(f"    [dim]{line}[/dim]")
                    all_correct = False
            for name in sorted(mcp_status.pending_mcps.keys()):
                has_override = mcp_status.has_overrides.get(name, False)
                override_text = ", override" if has_override else ""
                ctx.console.print(
                    f"  {name:<20} [yellow]Not installed[/yellow] [dim](managed{override_text})[/dim]"
                )
                if mgr is not None:
                    expected = mcp_status.pending_mcps.get(name, {})
                    pending_output = mgr.format_pending(name, expected)
                    if pending_output:
                        ctx.console.print(pending_output)
                all_correct = False
            for name in sorted(mcp_status.stale_mcps.keys()):
                ctx.console.print(
                    f"  {name:<20} [red]Should be removed[/red] [dim](no longer in config)[/dim]"
                )
                all_correct = False
            for name in sorted(mcp_status.unmanaged_mcps.keys()):
                ctx.console.print(f"  {name:<20} [dim]Unmanaged[/dim]")
            ctx.console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.mcp import OperationResult

        removed = 0
        for target in ctx.selected_targets:
            if not isinstance(target, Agent) or target.get_mcp_manager() is None:
                continue

            result, message = target.uninstall_mcps(force=ctx.yes, dry_run=False)
            if result == OperationResult.REMOVED:
                ctx.console.print(f"  [green]✓[/green] {message}")
                removed += 1
            elif result == OperationResult.NOT_FOUND:
                ctx.console.print(f"  [dim]•[/dim] {message}")

        return ComponentResult(changed=removed > 0, counts={"removed": removed})
