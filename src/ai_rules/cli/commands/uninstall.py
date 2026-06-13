from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.command()
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@cli_facade.agents_option("uninstall")
@cli_facade.only_option("UNINSTALL_COMPONENTS")
def uninstall(yes: bool, agents: str | None, component_filter: str | None) -> None:
    """Remove AI agent symlinks."""
    from ai_rules.cli.components import UNINSTALL_COMPONENTS
    from ai_rules.cli.display import console, print_warning
    from ai_rules.cli.runner import run_parallel

    cli_ctx = cli_facade.build_cli_context(
        UNINSTALL_COMPONENTS, agents, component_filter, yes=yes
    )

    if not yes:
        print_warning("This will remove symlinks for:\n")
        console.print("[bold]Agents:[/bold]")
        for target in cli_ctx.selected_targets:
            console.print(f"  • {target.name}")
        console.print()
        if not click.confirm("Continue?", default=False):
            print_warning("Uninstall cancelled")
            sys.exit(0)

    result = run_parallel(UNINSTALL_COMPONENTS, "uninstall", cli_ctx)

    console.print(
        f"\n[bold]Summary:[/bold] Removed {result.counts.get('removed', 0)}, "
        f"skipped {result.counts.get('skipped', 0)}"
    )
