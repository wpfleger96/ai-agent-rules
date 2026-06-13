from __future__ import annotations

import click

import ai_rules.cli as cli_facade


@click.command()
@cli_facade.agents_option("check")
@cli_facade.only_option("DIFF_COMPONENTS")
def diff(agents: str | None, component_filter: str | None) -> None:
    """Show differences between repo configs and installed symlinks."""
    from ai_rules.cli.components import DIFF_COMPONENTS
    from ai_rules.cli.display import console, print_hint
    from ai_rules.cli.runner import run_parallel

    cli_ctx = cli_facade.build_cli_context(DIFF_COMPONENTS, agents, component_filter)

    console.print("[bold]Configuration Differences[/bold]\n")

    result = run_parallel(DIFF_COMPONENTS, "diff", cli_ctx)

    if not result.changed:
        console.print("[green]No differences found - all symlinks are correct![/green]")
    else:
        print_hint("Run 'ai-agent-rules install' to fix these differences")
