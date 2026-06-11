from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.command()
@cli_facade.agents_option("validate")
@cli_facade.only_option("VALIDATE_COMPONENTS")
def validate(agents: str | None, component_filter: str | None) -> None:
    """Validate configuration and source files."""
    from ai_rules.cli.components import VALIDATE_COMPONENTS
    from ai_rules.cli.display import console, print_error
    from ai_rules.cli.runner import run_parallel

    cli_ctx = cli_facade.build_cli_context(
        VALIDATE_COMPONENTS, agents, component_filter
    )

    console.print("[bold]Validating AI Rules Configuration[/bold]\n")

    result = run_parallel(VALIDATE_COMPONENTS, "validate", cli_ctx)
    total_checked = result.counts.get("checked", 0)
    total_issues = result.counts.get("errors", 0)

    console.print(f"[bold]Summary:[/bold] Checked {total_checked} source file(s)")

    if result.ok:
        console.print("[green]All source files are valid![/green]")
    else:
        print_error(f"Found {total_issues} issue(s)")
        sys.exit(1)
