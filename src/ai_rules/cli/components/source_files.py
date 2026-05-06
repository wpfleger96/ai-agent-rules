"""Source file validation lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class SourceFilesComponent(Component):
    label = "Source Files"

    def validate(self, ctx: CliContext) -> ComponentResult:
        all_valid = True
        total_checked = 0
        total_issues = 0

        for target in ctx.selected_targets:
            ctx.console.print(f"[bold]{target.name}:[/bold]")
            target_issues = []

            for _tgt, source in target.symlinks:
                total_checked += 1

                if not source.exists():
                    target_issues.append((source, "Source file does not exist"))
                    all_valid = False
                elif not source.is_file() and not source.is_dir():
                    target_issues.append((source, "Source is not a file or directory"))
                    all_valid = False
                else:
                    ctx.console.print(f"  [green]✓[/green] {source.name}")

            excluded_symlinks = [
                (tgt, source)
                for tgt, source in target.symlinks
                if (tgt, source) not in target.get_filtered_symlinks()
            ]
            if excluded_symlinks:
                ctx.console.print(
                    f"  [dim]({len(excluded_symlinks)} symlink(s) excluded by config)[/dim]"
                )

            for path, issue in target_issues:
                ctx.console.print(f"  [red]✗[/red] {path}")
                ctx.console.print(f"    [dim]{issue}[/dim]")
                total_issues += 1

            ctx.console.print()

        return ComponentResult(
            ok=all_valid,
            changed=not all_valid,
            counts={"checked": total_checked, "errors": total_issues},
        )
