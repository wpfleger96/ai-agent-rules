from __future__ import annotations

import sys

from typing import Any

import click

import ai_rules.cli as cli_facade

from ai_rules.profiles import Profile


@click.group()
def profile() -> None:
    """Manage configuration profiles."""
    pass


@profile.command("list")
def profile_list() -> None:
    """List available profiles."""
    from rich.console import Console
    from rich.table import Table

    from ai_rules.profiles import ProfileLoader

    console = Console()

    loader = ProfileLoader()
    profiles = loader.list_profiles()

    table = Table(title="Available Profiles", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Extends")

    for name in profiles:
        try:
            info = loader.get_profile_info(name)
            desc = info.get("description", "")
            extends = info.get("extends") or "-"
            table.add_row(name, desc, extends)
        except Exception:
            table.add_row(name, "[dim]Error loading[/dim]", "-")

    console.print(table)


@profile.command("show")
@click.argument("name")
@click.option(
    "--resolved", is_flag=True, help="Show resolved profile with inheritance applied"
)
def profile_show(name: str, resolved: bool) -> None:
    """Show profile details."""
    from rich.console import Console

    from ai_rules.profiles import (
        CircularInheritanceError,
        ProfileLoader,
        ProfileNotFoundError,
    )

    console = Console()

    loader = ProfileLoader()

    try:
        if resolved:
            profile = loader.load_profile(name)
            console.print(f"[bold]Profile: {profile.name}[/bold] (resolved)")
            console.print(f"[dim]Description:[/dim] {profile.description}")
            if profile.extends:
                console.print(f"[dim]Extends:[/dim] {profile.extends}")

            if profile.settings_overrides:
                console.print("\n[bold]Settings Overrides:[/bold]")
                for agent, overrides in sorted(profile.settings_overrides.items()):
                    console.print(f"  [cyan]{agent}:[/cyan]")
                    for key, value in sorted(overrides.items()):
                        console.print(f"    {key}: {value}")

            if profile.exclude_symlinks:
                console.print("\n[bold]Exclude Symlinks:[/bold]")
                for pattern in sorted(profile.exclude_symlinks):
                    console.print(f"  - {pattern}")

            if profile.mcp_overrides:
                console.print("\n[bold]MCP Overrides:[/bold]")
                for mcp, overrides in sorted(profile.mcp_overrides.items()):
                    console.print(f"  [cyan]{mcp}:[/cyan]")
                    for key, value in sorted(overrides.items()):
                        console.print(f"    {key}: {value}")

            if profile.managed_tools:
                console.print("\n[bold]Managed Tools:[/bold]")
                import yaml as _yaml

                console.print(
                    _yaml.dump(profile.managed_tools, default_flow_style=False).rstrip()
                )

            if profile.plugins:
                console.print("\n[bold]Plugins:[/bold]")
                for plugin in profile.plugins:
                    console.print(
                        f"  - {plugin.get('name', '?')} (marketplace: {plugin.get('marketplace', '?')})"
                    )

            if profile.marketplaces:
                console.print("\n[bold]Marketplaces:[/bold]")
                for marketplace in profile.marketplaces:
                    console.print(
                        f"  - {marketplace.get('name', '?')} (source: {marketplace.get('source', '?')})"
                    )
        else:
            import yaml

            info = loader.get_profile_info(name)
            console.print(f"[bold]Profile: {info.get('name', name)}[/bold]")
            console.print(yaml.dump(info, default_flow_style=False, sort_keys=False))

    except ProfileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except CircularInheritanceError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@profile.command("current")
def profile_current() -> None:
    """Show currently active profile."""
    from rich.console import Console

    from ai_rules.state import get_active_profile

    console = Console()

    active = get_active_profile()
    if active:
        console.print(f"Active profile: [cyan]{active}[/cyan]")
    else:
        console.print("[dim]No profile set (using default)[/dim]")


def _detect_profile_override_conflicts(
    profile: Profile, user_config: dict[str, Any]
) -> list[tuple[str, str, Any]]:
    """Detect conflicts between profile settings and user overrides.

    Args:
        profile: The profile being installed
        user_config: User config dict from ~/.ai-agent-rules-config.yaml

    Returns:
        List of (agent, key, value) tuples for settings that conflict
    """
    conflicts = []
    user_settings = user_config.get("settings_overrides", {})

    for agent, profile_overrides in profile.settings_overrides.items():
        if agent in user_settings:
            for key in profile_overrides:
                if key in user_settings[agent]:
                    conflicts.append((agent, key, user_settings[agent][key]))

    return conflicts


def _handle_profile_conflicts(
    conflicts: list[tuple[str, str, Any]],
    profile_name: str,
    user_config: dict[str, Any],
) -> None:
    """Show conflicts and prompt user to clear them.

    Args:
        conflicts: List of (agent, key, value) tuples
        profile_name: Name of profile being installed
        user_config: User config dict to potentially modify
    """
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    if not conflicts:
        return

    console.print(
        f"\n[yellow]⚠[/yellow]  User overrides conflict with profile '{profile_name}':"
    )
    for agent, key, value in conflicts:
        console.print(f"  • {agent}.{key}: {value}")

    if click.confirm("\nRemove these from user config?", default=False):
        user_settings = user_config.get("settings_overrides", {})
        for agent, key, _ in conflicts:
            if agent in user_settings and key in user_settings[agent]:
                del user_settings[agent][key]
                if not user_settings[agent]:
                    del user_settings[agent]

        Config.save_user_config(user_config)
        console.print("[green]✓[/green] Cleared conflicting overrides\n")
    else:
        console.print()


@profile.command("switch")
@click.argument("name", shell_complete=cli_facade.complete_profiles)
@click.pass_context
def profile_switch(ctx: click.Context, name: str) -> None:
    """Switch to a different profile."""
    from rich.console import Console

    from ai_rules.cli.commands.install import install
    from ai_rules.config import Config
    from ai_rules.profiles import ProfileLoader, ProfileNotFoundError

    console = Console()

    loader = ProfileLoader()
    try:
        profile_obj = loader.load_profile(name)
    except ProfileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    user_config = Config.load_user_config()
    profile_conflicts = _detect_profile_override_conflicts(profile_obj, user_config)
    if profile_conflicts:
        _handle_profile_conflicts(profile_conflicts, name, user_config)

    console.print(f"Switching to profile: [cyan]{name}[/cyan]")
    ctx.invoke(
        install,
        profile=name,
        rebuild_cache=True,
        yes=True,
        skip_completions=True,
        agents=None,
        dry_run=False,
        config_dir_override=None,
    )
