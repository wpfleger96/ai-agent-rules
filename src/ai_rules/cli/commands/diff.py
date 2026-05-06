from __future__ import annotations

import click

import ai_rules.cli as cli_facade


@click.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to check (default: all)",
    shell_complete=cli_facade.complete_targets,
)
def diff(agents: str | None) -> None:
    """Show differences between repo configs and installed symlinks."""
    from rich.console import Console

    from ai_rules.cli.components import DIFF_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.runner import run_components
    from ai_rules.config import Config

    console = Console()

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    console.print("[bold]Configuration Differences[/bold]\n")

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=config.profile_name,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
    )
    result = run_components(DIFF_COMPONENTS, "diff", cli_ctx)

    if not result.changed:
        console.print("[green]No differences found - all symlinks are correct![/green]")
    else:
        console.print(
            "[yellow]💡 Run 'ai-agent-rules install' to fix these differences[/yellow]"
        )
