from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to check (default: all)",
    shell_complete=cli_facade.complete_targets,
)
def status(agents: str | None) -> None:
    """Check status of AI agent symlinks."""
    from rich.console import Console

    from ai_rules.cli.components import STATUS_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.runner import run_components
    from ai_rules.config import Config
    from ai_rules.state import get_active_profile

    console = Console()

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    console.print("[bold]AI Rules Status[/bold]\n")

    active_profile = get_active_profile()
    if active_profile:
        console.print(f"[dim]Profile: {active_profile}[/dim]\n")

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=config.profile_name or active_profile,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
    )
    result = run_components(STATUS_COMPONENTS, "status", cli_ctx)

    if not result.ok:
        if result.counts.get("cache_stale", 0):
            console.print(
                "[yellow]💡 Run 'ai-agent-rules install --rebuild-cache' to fix issues[/yellow]"
            )
        else:
            console.print(
                "[yellow]💡 Run 'ai-agent-rules install' to fix issues[/yellow]"
            )
        sys.exit(1)

    if result.counts.get("optional_missing", 0):
        console.print("[green]All symlinks are correct![/green]")
        console.print(
            "[yellow]💡 Run 'ai-agent-rules install' to install optional tools[/yellow]"
        )
    else:
        console.print("[green]All symlinks are correct![/green]")
