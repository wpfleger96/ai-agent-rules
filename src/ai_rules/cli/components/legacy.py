"""Legacy symlink migration component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class LegacyMigrationComponent(Component):
    label = "Legacy Migration"

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.dry_run:
            return ComponentResult()

        from ai_rules.cli import detect_old_config_symlinks

        old_symlinks = detect_old_config_symlinks()
        if not old_symlinks:
            return ComponentResult()

        ctx.console.print(
            "\n[yellow]Detected config migration from v0.4.1 → v0.5.0[/yellow]"
        )
        ctx.console.print(
            f"Found {len(old_symlinks)} symlink(s) pointing to old config location"
        )
        ctx.console.print(
            "[dim]Automatically migrating symlinks to new location...[/dim]\n"
        )

        removed = 0
        errors = 0
        for symlink_path, _old_target in old_symlinks:
            try:
                symlink_path.unlink()
                ctx.console.print(f"  [dim]✓ Removed old symlink: {symlink_path}[/dim]")
                removed += 1
            except Exception as exc:
                ctx.console.print(
                    f"  [yellow]⚠ Could not remove {symlink_path}: {exc}[/yellow]"
                )
                errors += 1

        ctx.console.print("\n[green]✓ Migration complete[/green]")
        ctx.console.print("[dim]New symlinks will be created below...[/dim]\n")

        return ComponentResult(
            ok=errors == 0,
            changed=removed > 0,
            counts={"removed": removed, "errors": errors},
        )
