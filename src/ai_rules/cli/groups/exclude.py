from __future__ import annotations

import sys

import click

import ai_rules.cli as cli_facade

from ai_rules.cli.display import dim, print_dim


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
    from ai_rules.cli.display import print_success, print_warning
    from ai_rules.config import Config

    data = Config.load_user_config()

    if "exclude_symlinks" not in data:
        data["exclude_symlinks"] = []

    if pattern in data["exclude_symlinks"]:
        print_warning(f"Pattern already excluded: {pattern}")
        return

    data["exclude_symlinks"].append(pattern)
    Config.save_user_config(data)

    user_config_path = cli_facade.get_user_config_path()
    print_success(f"Added exclusion pattern: {pattern}")
    print_dim(f"Config updated: {user_config_path}")


@exclude.command("remove")
@click.argument("pattern")
def exclude_remove(pattern: str) -> None:
    """Remove an exclusion pattern from user config."""
    from ai_rules.cli.display import print_error, print_success, print_warning
    from ai_rules.config import Config

    user_config_path = cli_facade.get_user_config_path()

    if not user_config_path.exists():
        print_error("No user config found")
        sys.exit(1)

    data = Config.load_user_config()

    if "exclude_symlinks" not in data or pattern not in data["exclude_symlinks"]:
        print_warning(f"Pattern not found: {pattern}")
        sys.exit(1)

    data["exclude_symlinks"].remove(pattern)
    Config.save_user_config(data)

    print_success(f"Removed exclusion pattern: {pattern}")
    print_dim(f"Config updated: {user_config_path}")


@exclude.command("list")
def exclude_list() -> None:
    """List all exclusion patterns."""
    from ai_rules.cli.display import console
    from ai_rules.config import Config

    config = Config.load()

    if not config.exclude_symlinks:
        print_dim("No exclusion patterns configured")
        return

    console.print("[bold]Exclusion Patterns:[/bold]\n")

    for pattern in sorted(config.exclude_symlinks):
        console.print(f"  • {pattern} {dim('(user)')}")
