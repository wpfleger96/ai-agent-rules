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
    from ai_rules.cli.components import STATUS_COMPONENTS

    ids = tuple(c.component_id for c in STATUS_COMPONENTS)
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
def status(agents: str | None, component_filter: str | None) -> None:
    """Check status of AI agent symlinks."""
    from ai_rules.cli.components import STATUS_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.display import console, print_hint
    from ai_rules.cli.runner import run_status_parallel
    from ai_rules.config import Config
    from ai_rules.state import get_active_profile

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    parsed_filter = cli_facade.select_components(STATUS_COMPONENTS, component_filter)

    console.print("[bold]AI Rules Status[/bold]\n")

    active_profile = get_active_profile()
    if active_profile:
        from ai_rules.cli.display import print_label

        print_label("Profile", active_profile)
        console.print()

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=config.profile_name or active_profile,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
        component_filter=parsed_filter,
    )
    result = run_status_parallel(STATUS_COMPONENTS, cli_ctx)

    if not result.ok:
        if result.counts.get("cache_stale", 0):
            print_hint("Run 'ai-agent-rules install --rebuild-cache' to fix issues")
        else:
            print_hint("Run 'ai-agent-rules install' to fix issues")
        sys.exit(1)

    if result.counts.get("optional_missing", 0):
        console.print("[green]All symlinks are correct![/green]")
        print_hint("Run 'ai-agent-rules install' to install optional tools")
    else:
        console.print("[green]All symlinks are correct![/green]")
