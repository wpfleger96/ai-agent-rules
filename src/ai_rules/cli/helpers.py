"""Shared CLI helper functions."""

from __future__ import annotations

import subprocess
import sys

from importlib.resources import files as resource_files
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem

    from ai_rules.config import Config
    from ai_rules.targets.base import ConfigTarget

GIT_SUBPROCESS_TIMEOUT = 5


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


def get_git_repo_root() -> Path:
    """Get the git repository root directory for development-mode operations."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass

    raise RuntimeError(
        "Not in a git repository. For config access, use get_config_dir() instead."
    )


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
    from rich.console import Console

    console = Console()

    if not filter_string:
        return all_targets

    requested_ids = {
        agent.strip() for agent in filter_string.split(",") if agent.strip()
    }
    selected = [target for target in all_targets if target.target_id in requested_ids]

    if not selected:
        invalid_ids = requested_ids - {target.target_id for target in all_targets}
        available_ids = [target.target_id for target in all_targets]
        console.print(
            f"[red]Error:[/red] Invalid agent ID(s): {', '.join(sorted(invalid_ids))}\n"
            f"[dim]Available agents: {', '.join(available_ids)}[/dim]"
        )
        sys.exit(1)

    return selected


def format_summary(
    dry_run: bool,
    created: int,
    updated: int,
    skipped: int,
    excluded: int = 0,
    errors: int = 0,
) -> None:
    """Format and print operation summary."""
    from rich.console import Console

    console = Console()
    console.print()
    if dry_run:
        console.print(
            f"[bold]Summary:[/bold] Would create {created}, "
            f"update {updated}, skip {skipped}"
        )
    else:
        console.print(
            f"[bold]Summary:[/bold] Created {created}, "
            f"updated {updated}, skipped {skipped}"
        )

    if excluded > 0:
        console.print(f"  ({excluded} excluded by config)")

    if errors > 0:
        console.print(f"  [red]{errors} error(s)[/red]")
