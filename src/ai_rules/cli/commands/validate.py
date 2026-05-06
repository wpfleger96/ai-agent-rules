from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to validate (default: all)",
    shell_complete=cli_facade.complete_targets,
)
def validate(agents: str | None) -> None:
    """Validate configuration and source files."""
    from rich.console import Console

    from ai_rules.cli.components import VALIDATE_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.runner import run_components
    from ai_rules.config import Config

    console = Console()

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    console.print("[bold]Validating AI Rules Configuration[/bold]\n")

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=config.profile_name,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
    )
    result = run_components(VALIDATE_COMPONENTS, "validate", cli_ctx)
    total_checked = result.counts.get("checked", 0)
    total_issues = result.counts.get("errors", 0)

    console.print(f"[bold]Summary:[/bold] Checked {total_checked} source file(s)")

    if result.ok:
        console.print("[green]All source files are valid![/green]")
    else:
        console.print(f"[red]Found {total_issues} issue(s)[/red]")
        sys.exit(1)
