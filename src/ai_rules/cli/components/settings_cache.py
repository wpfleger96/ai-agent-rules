"""Settings cache lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class SettingsCacheComponent(Component):
    label = "Settings Cache"

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.dry_run:
            return ComponentResult()

        built = 0
        for target in ctx.all_targets:
            base_path = target._base_settings_path
            if not base_path.exists():
                continue
            try:
                if target.build_merged_settings(force_rebuild=ctx.rebuild_cache):
                    built += 1
            except ValueError as exc:
                ctx.console.print(
                    f"[red]Error building {target.name} config:[/red] {exc}"
                )
                return ComponentResult(ok=False, abort=True, counts={"errors": 1})

        return ComponentResult(changed=bool(built), counts={"cache_updated": built})

    def status(self, ctx: CliContext) -> ComponentResult:
        stale_targets = []
        for target in ctx.selected_targets:
            if target.needs_cache and target.is_cache_stale():
                stale_targets.append(target)

        if not stale_targets:
            return ComponentResult()

        ctx.console.print("[bold cyan]Settings Cache[/bold cyan]\n")
        for target in stale_targets:
            ctx.console.print(f"[bold]{target.name}:[/bold]")
            ctx.console.print("  [yellow]⚠[/yellow] Cached settings are stale")
            diff_output = target.get_cache_diff()
            if diff_output:
                ctx.console.print(diff_output)
            ctx.console.print()

        return ComponentResult(
            ok=False,
            changed=True,
            counts={"cache_stale": len(stale_targets)},
        )

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)


class CacheCleanupComponent(Component):
    label = "Settings Cache Cleanup"

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.dry_run:
            return ComponentResult()

        targets_needing_cache = {
            target.target_id for target in ctx.all_targets if target.needs_cache
        }
        orphaned = ctx.config.cleanup_orphaned_cache(targets_needing_cache)
        if orphaned:
            ctx.console.print(
                f"[dim]✓ Cleaned up orphaned cache for: {', '.join(orphaned)}[/dim]"
            )

        return ComponentResult(
            changed=bool(orphaned),
            counts={"cache_removed": len(orphaned)},
        )
