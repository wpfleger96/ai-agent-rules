"""Settings lifecycle component."""

from __future__ import annotations

from pathlib import Path

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    SettingsPlan,
)


class SettingsComponent(Component):
    label = "Settings Cache"
    component_id = "settings"
    filterable = False

    def plan(self, ctx: CliContext) -> SettingsPlan:
        stale_targets = []
        for target in ctx.selected_targets:
            base_path = target._base_settings_path
            if not base_path.exists():
                continue
            if target.needs_cache and (ctx.rebuild_cache or target.is_cache_stale()):
                stale_targets.append(target)

        excluded_symlinks_to_clean: list[Path] = []
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
                    excluded_symlinks_to_clean.append(expanded)

        has_changes = bool(stale_targets or excluded_symlinks_to_clean)
        return SettingsPlan(
            has_changes=has_changes,
            stale_targets=stale_targets,
            excluded_symlinks_to_clean=excluded_symlinks_to_clean,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, SettingsPlan):
            return ComponentResult()

        if ctx.dry_run:
            return ComponentResult()

        built = 0
        for target in plan.stale_targets:
            try:
                if target.build_merged_settings(force_rebuild=ctx.rebuild_cache):
                    built += 1
            except ValueError as exc:
                from ai_rules.cli.display import print_error

                print_error(f"Error building {target.name} config: {exc}")
                return ComponentResult(ok=False, abort=True, counts={"errors": 1})

        for expanded in plan.excluded_symlinks_to_clean:
            expanded.unlink()

        from ai_rules.cli.display import print_done

        orphaned = ctx.config.cleanup_orphaned_cache(
            {target.target_id for target in ctx.all_targets if target.needs_cache}
        )
        if orphaned:
            print_done(
                f"Cleaned up orphaned cache for: {', '.join(orphaned)}", indent=2
            )

        return ComponentResult(
            changed=bool(built or orphaned),
            counts={"cache_updated": built, "cache_removed": len(orphaned)},
        )

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
                from ai_rules.cli.display import print_error

                print_error(f"Error building {target.name} config: {exc}")
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

        from ai_rules.cli.display import print_done

        targets_needing_cache = {
            target.target_id for target in ctx.all_targets if target.needs_cache
        }
        orphaned = ctx.config.cleanup_orphaned_cache(targets_needing_cache)
        if orphaned:
            print_done(
                f"Cleaned up orphaned cache for: {', '.join(orphaned)}", indent=2
            )

        return ComponentResult(
            changed=bool(built or orphaned),
            counts={"cache_updated": built, "cache_removed": len(orphaned)},
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.runner import get_console

        stale_targets = []
        for target in ctx.selected_targets:
            if target.needs_cache and target.is_cache_stale():
                stale_targets.append(target)

        if not stale_targets:
            return ComponentResult()

        from ai_rules.cli.display import print_warning

        console = get_console(ctx)
        for target in stale_targets:
            console.print(f"[bold]{target.name}[/bold]")
            print_warning("Cached settings are stale", indent=2)
            diff_output = target.get_cache_diff()
            if diff_output:
                console.print(diff_output)
            console.print()

        return ComponentResult(
            ok=False,
            changed=True,
            counts={"cache_stale": len(stale_targets)},
        )

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)
