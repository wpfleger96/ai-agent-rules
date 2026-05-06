"""Orphan cleanup lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class CleanupComponent(Component):
    label = "Cleanup"

    def install(self, ctx: CliContext) -> ComponentResult:
        if not ctx.selected_targets:
            return ComponentResult()

        from ai_rules.cli import cleanup_orphaned_symlinks

        removed = cleanup_orphaned_symlinks(
            list(ctx.selected_targets),
            ctx.config_dir,
            ctx.config,
            ctx.yes,
            ctx.dry_run,
        )
        return ComponentResult(
            changed=removed > 0,
            counts={"cleanup_removed": removed},
        )
