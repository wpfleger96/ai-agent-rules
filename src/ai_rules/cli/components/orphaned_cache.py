"""Orphaned settings cache cleanup lifecycle component."""

from __future__ import annotations

import os
import shutil

from pathlib import Path

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    OrphanedCachePlan,
)
from ai_rules.config import is_real_dir


def _links_repointed_this_run(ctx: CliContext) -> set[Path]:
    """Managed links Config Files re-points before this component applies.

    Their current destinations stop mattering, which lets a dry-run, where no
    link has moved yet, predict exactly what a real run deletes.
    """
    if ctx.component_filter is not None and "config" not in ctx.component_filter:
        return set()
    return {
        tgt.expanduser()
        for target in ctx.selected_targets
        for tgt, _ in target.get_filtered_symlinks()
    }


def _linked_dirs(ctx: CliContext, dirs: list[Path], ignore: set[Path]) -> set[Path]:
    """The dirs that a managed link, other than those in ignore, resolves into."""
    real_dirs = {Path(os.path.realpath(d)): d for d in dirs}
    linked: set[Path] = set()
    for target in ctx.all_targets:
        for tgt, _ in target.symlinks:
            link = tgt.expanduser()
            if link in ignore or not link.is_symlink():
                continue
            dest = Path(os.path.realpath(link))
            linked.update(
                d for real, d in real_dirs.items() if dest.is_relative_to(real)
            )
    return linked


class OrphanedCacheComponent(Component):
    label = "Orphaned Caches"
    # Shares the settings id so `--only settings` covers every cache change and
    # no other --only scope deletes caches as a side effect.
    component_id = "settings"
    # Deletes only after Config Files has re-pointed links away from the caches.
    install_after_symlinks = True

    def plan(self, ctx: CliContext) -> OrphanedCachePlan:
        # All targets, not just selected ones: a partial install must not delete
        # caches that unselected agents still use. An excluded agent's cache
        # holds the hooks and plugins Claude Code wrote, so it outlives the
        # exclusion.
        keep = {
            target.target_id
            for target in ctx.all_targets
            if target.needs_cache or target.is_settings_file_excluded
        }
        cache_root = ctx.config.get_cache_dir()
        candidates = [
            cache_root / name for name in ctx.config.find_orphaned_cache(keep)
        ]
        linked = _linked_dirs(ctx, candidates, ignore=_links_repointed_this_run(ctx))
        orphaned = [d for d in candidates if d not in linked]
        return OrphanedCachePlan(has_changes=bool(orphaned), orphaned_dirs=orphaned)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, OrphanedCachePlan):
            return ComponentResult()

        from ai_rules.cli.display import print_dim, print_done, print_warning

        if ctx.dry_run:
            for cache_dir in plan.orphaned_dirs:
                print_dim(f"Would remove orphaned cache: {cache_dir.name}", indent=2)
            return ComponentResult(
                changed=plan.has_changes,
                counts={"removed": len(plan.orphaned_dirs)},
            )

        # A link Config Files failed to re-point still resolves into its cache.
        still_linked = _linked_dirs(ctx, plan.orphaned_dirs, ignore=set())
        removed = 0
        for cache_dir in plan.orphaned_dirs:
            if not is_real_dir(cache_dir):
                continue
            if cache_dir in still_linked:
                print_warning(
                    f"Kept orphaned cache {cache_dir.name}: a managed link still "
                    "points into it",
                    indent=2,
                )
                continue
            try:
                shutil.rmtree(cache_dir)
            except OSError as exc:
                print_warning(
                    f"Could not remove orphaned cache {cache_dir}: {exc}", indent=2
                )
                continue
            print_done(f"Removed orphaned cache: {cache_dir.name}", indent=2)
            removed += 1

        return ComponentResult(changed=removed > 0, counts={"removed": removed})


def display_pending_orphaned_cache(ctx: CliContext) -> bool:
    """Show the caches install will delete. Returns True if there are any."""
    from ai_rules.cli.runner import _should_skip

    component = OrphanedCacheComponent()
    if _should_skip(component, ctx):
        return False
    plan = component.plan(ctx)
    if not plan.orphaned_dirs:
        return False

    from ai_rules.cli.display import console, print_would

    console.print(f"\n[bold]{component.label}[/bold]")
    for cache_dir in plan.orphaned_dirs:
        print_would(f"Remove: {cache_dir}", indent=2)
    return True
