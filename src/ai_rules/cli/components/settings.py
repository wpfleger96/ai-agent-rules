"""Settings lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class SettingsComponent(Component):
    label = "Settings"
    component_id = "settings"
    filterable = False

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.dry_run:
            return ComponentResult()

        built = 0
        for target in ctx.selected_targets:
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

        for target in ctx.all_targets:
            if not target.is_settings_file_excluded:
                continue
            symlink_target = target.settings_symlink_target
            if symlink_target is None:
                continue
            expanded = symlink_target.expanduser()
            if expanded.is_symlink():
                link_dest = expanded.resolve()
                cache_dir = ctx.config.get_cache_dir()
                if cache_dir:
                    try:
                        link_dest.relative_to(cache_dir)
                    except ValueError:
                        continue
                    expanded.unlink()

        targets_needing_cache = {
            target.target_id for target in ctx.all_targets if target.needs_cache
        }
        orphaned = ctx.config.cleanup_orphaned_cache(targets_needing_cache)
        if orphaned:
            ctx.console.print(
                f"[dim]✓ Cleaned up orphaned cache for: {', '.join(orphaned)}[/dim]"
            )

        return ComponentResult(
            changed=bool(built or orphaned),
            counts={"cache_updated": built, "cache_removed": len(orphaned)},
        )

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
