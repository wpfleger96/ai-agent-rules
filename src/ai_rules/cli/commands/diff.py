from __future__ import annotations

from typing import TYPE_CHECKING

import click

import ai_rules.cli as cli_facade

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem


def _complete_components(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    from ai_rules.cli.components import DIFF_COMPONENTS

    ids = tuple(c.component_id for c in DIFF_COMPONENTS)
    return cli_facade.complete_components(ctx, param, incomplete, component_ids=ids)


@click.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to check (default: all)",
    shell_complete=cli_facade.complete_targets,
)
@click.option(
    "--only",
    "component_filter",
    help="Comma-separated list of components to target (default: all)",
    shell_complete=_complete_components,
)
def diff(agents: str | None, component_filter: str | None) -> None:
    """Show differences between repo configs and installed symlinks."""
    from ai_rules.cli.components import DIFF_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.display import console, print_hint
    from ai_rules.cli.runner import run_diff_parallel
    from ai_rules.config import Config

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    parsed_filter = cli_facade.select_components(DIFF_COMPONENTS, component_filter)

    console.print("[bold]Configuration Differences[/bold]\n")

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
    result = run_diff_parallel(DIFF_COMPONENTS, cli_ctx)

    if not result.changed:
        console.print("[green]No differences found - all symlinks are correct![/green]")
    else:
        print_hint("Run 'ai-agent-rules install' to fix these differences")
