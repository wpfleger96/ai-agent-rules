"""Shared CLI helper functions."""

from __future__ import annotations

import sys

from importlib.resources import files as resource_files
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem

    from ai_rules.cli.context import Component
    from ai_rules.config import Config
    from ai_rules.targets.base import ConfigTarget


def get_user_config_path() -> Path:
    from ai_rules.config import get_user_config_path as _get_user_config_path

    return _get_user_config_path()


def get_config_dir() -> Path:
    """Get the bundled config directory in development or installed mode."""
    try:
        config_resource = resource_files("ai_rules") / "config"
        return Path(str(config_resource))
    except Exception:
        return Path(__file__).parents[1] / "config"


def get_targets(config_dir: Path, config: Config) -> list[ConfigTarget]:
    """Get all config target instances."""
    from ai_rules.targets.registry import get_targets as get_registered_targets

    return get_registered_targets(config_dir, config)


def complete_targets(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Dynamically discover and complete target names for `--agents`."""
    from click.shell_completion import CompletionItem

    from ai_rules.config import Config

    config_dir = get_config_dir()
    config = Config.load()
    target_ids = [target.target_id for target in get_targets(config_dir, config)]

    return [
        CompletionItem(target_id)
        for target_id in target_ids
        if target_id.startswith(incomplete)
    ]


def complete_profiles(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Dynamically complete profile names for `--profile`."""
    from click.shell_completion import CompletionItem

    from ai_rules.profiles import ProfileLoader

    loader = ProfileLoader()
    profiles = loader.list_profiles()

    return [
        CompletionItem(profile)
        for profile in profiles
        if profile.startswith(incomplete)
    ]


def select_targets(
    all_targets: list[ConfigTarget], filter_string: str | None
) -> list[ConfigTarget]:
    """Select targets based on a comma-separated target filter."""
    from ai_rules.cli.display import console, print_error

    if not filter_string:
        return all_targets

    requested_ids = {
        agent.strip() for agent in filter_string.split(",") if agent.strip()
    }
    selected = [target for target in all_targets if target.target_id in requested_ids]

    if not selected:
        invalid_ids = requested_ids - {target.target_id for target in all_targets}
        available_ids = [target.target_id for target in all_targets]
        print_error(f"Invalid agent ID(s): {', '.join(sorted(invalid_ids))}")
        console.print(f"[dim]Available agents: {', '.join(available_ids)}[/dim]")
        sys.exit(1)

    return selected


def select_components(
    components: tuple[Component, ...], filter_string: str | None
) -> tuple[str, ...] | None:
    """Parse --only filter string into validated component IDs.

    Returns None if no filter, or a tuple of valid component_id strings.
    """
    if not filter_string:
        return None

    requested_ids = [cid.strip() for cid in filter_string.split(",") if cid.strip()]
    known_ids = {component.component_id for component in components}

    invalid_ids = [cid for cid in requested_ids if cid not in known_ids]
    if invalid_ids:
        from ai_rules.cli.display import console, print_error

        print_error(f"Invalid component ID(s): {', '.join(sorted(invalid_ids))}")
        console.print(
            f"[dim]Available components: {', '.join(sorted(known_ids))}[/dim]"
        )
        sys.exit(1)

    return tuple(requested_ids)


def complete_components(
    ctx: click.Context,
    param: click.Parameter,
    incomplete: str,
    *,
    component_ids: tuple[str, ...],
) -> list[CompletionItem]:
    """Shell completion callback for --only flag."""
    from click.shell_completion import CompletionItem

    return [
        CompletionItem(component_id)
        for component_id in component_ids
        if component_id.startswith(incomplete)
    ]


def format_summary(
    dry_run: bool,
    created: int,
    updated: int,
    skipped: int,
    excluded: int = 0,
    errors: int = 0,
    unchanged: int = 0,
) -> None:
    """Format and print operation summary."""
    from ai_rules.cli.display import console, print_error

    console.print()

    has_actions = created or updated or skipped or errors
    if not has_actions and unchanged > 0:
        console.print(f"[bold]Summary:[/bold] All up to date ({unchanged} unchanged)")
    elif dry_run:
        parts = []
        if created:
            parts.append(f"create {created}")
        if updated:
            parts.append(f"update {updated}")
        if skipped:
            parts.append(f"skip {skipped}")
        if unchanged:
            parts.append(f"skip {unchanged} unchanged")
        console.print(
            f"[bold]Summary:[/bold] Would {', '.join(parts)}"
            if parts
            else "[bold]Summary:[/bold] No changes"
        )
    else:
        parts = []
        if created:
            parts.append(f"Created {created}")
        if updated:
            parts.append(f"updated {updated}")
        if skipped:
            parts.append(f"skipped {skipped}")
        if unchanged:
            parts.append(f"{unchanged} unchanged")
        console.print(
            f"[bold]Summary:[/bold] {', '.join(parts)}"
            if parts
            else "[bold]Summary:[/bold] No changes"
        )

    if excluded > 0:
        console.print(f"  ({excluded} excluded by config)")

    if errors > 0:
        print_error(f"{errors} error(s)", indent=2)
