from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.command()
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@click.option(
    "--agents",
    help="Comma-separated list of agents to uninstall (default: all)",
    shell_complete=cli_facade.complete_targets,
)
def uninstall(yes: bool, agents: str | None) -> None:
    """Remove AI agent symlinks."""
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.cli.components import UNINSTALL_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.runner import run_components
    from ai_rules.config import Config

    console = Console()

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

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
        yes=yes,
    )
    result = run_components(UNINSTALL_COMPONENTS, "uninstall", cli_ctx)

    console.print(
        f"\n[bold]Summary:[/bold] Removed {result.counts.get('removed', 0)}, "
        f"skipped {result.counts.get('skipped', 0)}"
    )
