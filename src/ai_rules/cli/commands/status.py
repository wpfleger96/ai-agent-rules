from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.command()
@cli_facade.agents_option("check")
@cli_facade.only_option("STATUS_COMPONENTS")
def status(agents: str | None, component_filter: str | None) -> None:
    """Check status of AI agent symlinks."""
    from ai_rules.cli.components import STATUS_COMPONENTS
    from ai_rules.cli.display import console, print_hint
    from ai_rules.cli.runner import run_parallel
    from ai_rules.state import get_active_profile

    cli_ctx = cli_facade.build_cli_context(STATUS_COMPONENTS, agents, component_filter)

    console.print("[bold]AI Rules Status[/bold]\n")

    active_profile = get_active_profile()
    if active_profile:
        from ai_rules.cli.display import print_label

        print_label("Profile", active_profile)
        console.print()

    result = run_parallel(STATUS_COMPONENTS, "status", cli_ctx)

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
