"""Source file validation lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class SourceFilesComponent(Component):
    label = "Source Files"
    display_name = "Source Files"
    component_id = "source-files"

    def validate(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.display import print_dim, print_error, print_success
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        all_valid = True
        total_checked = 0
        total_issues = 0

        for target in ctx.selected_targets:
            console.print(f"[bold]{target.name}[/bold]")
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
                    print_success(source.name, indent=2)

            excluded_symlinks = [
                (tgt, source)
                for tgt, source in target.symlinks
                if (tgt, source) not in target.get_filtered_symlinks()
            ]
            if excluded_symlinks:
                print_dim(
                    f"({len(excluded_symlinks)} symlink(s) excluded by config)",
                    indent=2,
                )

            for path, issue in target_issues:
                print_error(str(path), indent=2)
                print_dim(issue, indent=4)
                total_issues += 1

            console.print()

        return ComponentResult(
            ok=all_valid,
            changed=not all_valid,
            counts={"checked": total_checked, "errors": total_issues},
        )
