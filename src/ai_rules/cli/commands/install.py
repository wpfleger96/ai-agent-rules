from __future__ import annotations

import sys

from pathlib import Path

import click

import ai_rules.cli as cli_facade

from ai_rules.cli.groups.profile import (
    _detect_profile_override_conflicts,
    _handle_profile_conflicts,
)


@click.command()
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option(
    "--rebuild-cache",
    is_flag=True,
    help="Rebuild merged settings cache (use after changing overrides)",
)
@click.option(
    "--agents",
    help="Comma-separated list of agents to install (default: all)",
    shell_complete=cli_facade.complete_targets,
)
@click.option(
    "--skip-completions",
    is_flag=True,
    help="Skip shell completion installation",
)
@click.option(
    "--profile",
    default=None,
    shell_complete=cli_facade.complete_profiles,
    help="Profile to use (default: 'default' for backward compatibility)",
)
@click.option(
    "--config-dir",
    "config_dir_override",
    hidden=True,
    help="Override config directory (internal use)",
)
def install(
    yes: bool,
    dry_run: bool,
    rebuild_cache: bool,
    agents: str | None,
    skip_completions: bool,
    profile: str | None,
    config_dir_override: str | None = None,
) -> None:
    """Install AI agent configs via symlinks."""
    from rich.console import Console

    from ai_rules.cli.components import INSTALL_COMPONENTS
    from ai_rules.cli.context import CliContext
    from ai_rules.cli.runner import run_components
    from ai_rules.config import Config

    console = Console()

    if config_dir_override:
        config_dir = Path(config_dir_override)
        if not config_dir.exists():
            console.print(f"[red]Error:[/red] Config directory not found: {config_dir}")
            sys.exit(1)
    else:
        config_dir = cli_facade.get_config_dir()

    from ai_rules.profiles import ProfileLoader, ProfileNotFoundError
    from ai_rules.state import get_active_profile, set_active_profile

    if profile is None:
        profile = get_active_profile() or "default"

    if profile and not yes:
        try:
            loader = ProfileLoader()
            profile_obj = loader.load_profile(profile)
            user_config = Config.load_user_config()
            profile_conflicts = _detect_profile_override_conflicts(
                profile_obj, user_config
            )
            if profile_conflicts:
                _handle_profile_conflicts(profile_conflicts, profile, user_config)
        except ProfileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

    try:
        config = Config.load(profile=profile)
    except ProfileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if not dry_run:
        set_active_profile(profile)

    if profile and profile != "default":
        console.print(f"[dim]Using profile: {profile}[/dim]\n")

    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)

    cli_ctx = CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=profile,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
        yes=yes,
        dry_run=dry_run,
        rebuild_cache=rebuild_cache,
        skip_completions=skip_completions,
    )

    if dry_run:
        console.print("[bold]Dry run mode - no changes will be made[/bold]\n")

    install_components_result = run_components(INSTALL_COMPONENTS, "install", cli_ctx)
    if install_components_result.aborted:
        if not install_components_result.ok:
            sys.exit(1)
        return

    cli_facade.format_summary(
        dry_run,
        install_components_result.counts.get("created", 0),
        install_components_result.counts.get("updated", 0),
        install_components_result.counts.get("skipped", 0),
        install_components_result.counts.get("excluded", 0),
        install_components_result.counts.get("errors", 0),
    )

    if not install_components_result.ok:
        sys.exit(1)
