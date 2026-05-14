from __future__ import annotations

import sys

from typing import TYPE_CHECKING

import click

import ai_rules.cli as cli_facade

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem


def _complete_components(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    from ai_rules.cli.components import UNINSTALL_COMPONENTS

    ids = tuple(c.component_id for c in UNINSTALL_COMPONENTS)
    return cli_facade.complete_components(ctx, param, incomplete, component_ids=ids)


@click.command()
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@click.option(
    "--agents",
    help="Comma-separated list of agents to uninstall (default: all)",
    shell_complete=cli_facade.complete_targets,
)
@click.option(
    "--only",
    "component_filter",
    help="Comma-separated list of components to target (default: all)",
    shell_complete=_complete_components,
)
def uninstall(yes: bool, agents: str | None, component_filter: str | None) -> None:
    """Remove AI agent symlinks."""
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.cli.components import UNINSTALL_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.runner import run_uninstall_parallel
    from ai_rules.config import Config

    console = Console()

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    parsed_filter = cli_facade.select_components(UNINSTALL_COMPONENTS, component_filter)

    if not yes:
        console.print("[yellow]Warning:[/yellow] This will remove symlinks for:\n")
        console.print("[bold]Agents:[/bold]")
        for target in selected_targets:
            console.print(f"  • {target.name}")
        console.print()
        if not Confirm.ask("Continue?", default=False):
            console.print("[yellow]Uninstall cancelled[/yellow]")
            sys.exit(0)

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=config.profile_name,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
        component_filter=parsed_filter,
        yes=yes,
    )
    result = run_uninstall_parallel(UNINSTALL_COMPONENTS, cli_ctx)

    console.print(
        f"\n[bold]Summary:[/bold] Removed {result.counts.get('removed', 0)}, "
        f"skipped {result.counts.get('skipped', 0)}"
    )
