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
    from ai_rules.cli.components import VALIDATE_COMPONENTS

    ids = tuple(c.component_id for c in VALIDATE_COMPONENTS)
    return cli_facade.complete_components(ctx, param, incomplete, component_ids=ids)


@click.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to validate (default: all)",
    shell_complete=cli_facade.complete_targets,
)
@click.option(
    "--only",
    "component_filter",
    help="Comma-separated list of components to target (default: all)",
    shell_complete=_complete_components,
)
def validate(agents: str | None, component_filter: str | None) -> None:
    """Validate configuration and source files."""
    from ai_rules.cli.components import VALIDATE_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.display import console
    from ai_rules.cli.runner import run_validate_parallel
    from ai_rules.config import Config

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    parsed_filter = cli_facade.select_components(VALIDATE_COMPONENTS, component_filter)

    console.print("[bold]Validating AI Rules Configuration[/bold]\n")

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=config.profile_name,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
        component_filter=parsed_filter,
    )
    result = run_validate_parallel(VALIDATE_COMPONENTS, cli_ctx)
    total_checked = result.counts.get("checked", 0)
    total_issues = result.counts.get("errors", 0)

    console.print(f"[bold]Summary:[/bold] Checked {total_checked} source file(s)")

    if result.ok:
        console.print("[green]All source files are valid![/green]")
    else:
        console.print(f"[red]Found {total_issues} issue(s)[/red]")
        sys.exit(1)
