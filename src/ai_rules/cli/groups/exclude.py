from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade


@click.group()
def exclude() -> None:
    """Manage exclusion patterns."""
    pass


@exclude.command("add")
@click.argument("pattern")
def exclude_add(pattern: str) -> None:
    """Add an exclusion pattern to user config.

    PATTERN can be an exact path or glob pattern (e.g., ~/.claude/*.json)
    """
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    data = Config.load_user_config()

    if "exclude_symlinks" not in data:
        data["exclude_symlinks"] = []

    if pattern in data["exclude_symlinks"]:
        console.print(f"[yellow]Pattern already excluded:[/yellow] {pattern}")
        return

    data["exclude_symlinks"].append(pattern)
    Config.save_user_config(data)

    user_config_path = cli_facade.get_user_config_path()
    console.print(f"[green]✓[/green] Added exclusion pattern: {pattern}")
    console.print(f"[dim]Config updated: {user_config_path}[/dim]")


@exclude.command("remove")
@click.argument("pattern")
def exclude_remove(pattern: str) -> None:
    """Remove an exclusion pattern from user config."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    user_config_path = cli_facade.get_user_config_path()

    if not user_config_path.exists():
        console.print("[red]No user config found[/red]")
        sys.exit(1)

    data = Config.load_user_config()

    if "exclude_symlinks" not in data or pattern not in data["exclude_symlinks"]:
        console.print(f"[yellow]Pattern not found:[/yellow] {pattern}")
        sys.exit(1)

    data["exclude_symlinks"].remove(pattern)
    Config.save_user_config(data)

    console.print(f"[green]✓[/green] Removed exclusion pattern: {pattern}")
    console.print(f"[dim]Config updated: {user_config_path}[/dim]")


@exclude.command("list")
def exclude_list() -> None:
    """List all exclusion patterns."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    config = Config.load()

    if not config.exclude_symlinks:
        console.print("[dim]No exclusion patterns configured[/dim]")
        return

    console.print("[bold]Exclusion Patterns:[/bold]\n")

    for pattern in sorted(config.exclude_symlinks):
        console.print(f"  • {pattern} [dim](user)[/dim]")
