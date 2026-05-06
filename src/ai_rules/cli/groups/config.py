from __future__ import annotations

import sys

from typing import Any

import click

import ai_rules.cli as cli_facade


@click.group()
def config() -> None:
    """Manage ai-agent-rules configuration."""
    pass


@config.command("show")
@click.option(
    "--merged", is_flag=True, help="Show merged settings with overrides applied"
)
@click.option("--agent", help="Show config for specific agent only")
def config_show(merged: bool, agent: str | None) -> None:
    """Show current configuration."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    config_dir = cli_facade.get_config_dir()
    cfg = Config.load()
    user_config_path = cli_facade.get_user_config_path()

    if merged:
        console.print("[bold]Merged Settings:[/bold]\n")

        from ai_rules.config import AGENT_FORMATS, FORMAT_CONFIG_FILES

        agents_to_show = [agent] if agent else list(AGENT_FORMATS.keys())

        for agent_name in agents_to_show:
            has_overrides = agent_name in cfg.settings_overrides
            cache_path = cfg.get_merged_settings_path(
                agent_name, "settings.json", force=True
            )
            has_cache = cache_path and cache_path.exists()

            if not has_overrides and not has_cache:
                console.print(
                    f"[dim]{agent_name}: No overrides (using base settings)[/dim]\n"
                )
                continue

            console.print(f"[bold]{agent_name}:[/bold]")

            agent_format = AGENT_FORMATS.get(agent_name)
            if not agent_format:
                console.print(f"  [red]✗[/red] Unknown agent: {agent_name}")
                console.print()
                continue

            config_file = FORMAT_CONFIG_FILES.get(agent_format, "settings.json")
            base_path = config_dir / agent_name / config_file
            if base_path.exists():
                from ai_rules.config import CONFIG_PARSE_ERRORS, load_config_file

                try:
                    base_settings = load_config_file(base_path, agent_format)
                except CONFIG_PARSE_ERRORS as e:
                    console.print(
                        f"  [red]✗[/red] Failed to load base settings from {base_path}: {e}"
                    )
                    console.print()
                    continue

                merged_settings = cfg.merge_settings(agent_name, base_settings)

                overridden_keys = []
                agent_overrides = cfg.settings_overrides.get(agent_name, {})
                for key in agent_overrides:
                    if key in base_settings:
                        old_val = base_settings[key]
                        new_val = merged_settings[key]
                        console.print(
                            f"  [yellow]↻[/yellow] {key}: {old_val} → {new_val}"
                        )
                        overridden_keys.append(key)
                    else:
                        console.print(
                            f"  [green]+[/green] {key}: {merged_settings[key]}"
                        )
                        overridden_keys.append(key)

                for key, value in merged_settings.items():
                    if key not in overridden_keys:
                        console.print(f"  [dim]•[/dim] {key}: {value}")
            else:
                console.print(
                    f"  [yellow]⚠[/yellow] No base settings found at {base_path}"
                )
                if has_overrides:
                    console.print(
                        f"  [dim]Overrides: {cfg.settings_overrides[agent_name]}[/dim]"
                    )

            console.print()
    else:
        console.print("[bold]Configuration:[/bold]\n")

        if user_config_path.exists():
            with open(user_config_path) as f:
                content = f.read()
            console.print(f"[bold]User Config:[/bold] {user_config_path}")
            console.print(content)
        else:
            console.print(f"[dim]No user config at {user_config_path}[/dim]\n")


@config.command("edit")
def config_edit() -> None:
    """Edit user configuration file in $EDITOR."""
    from rich.console import Console

    console = Console()

    import os
    import subprocess

    user_config_path = cli_facade.get_user_config_path()
    editor = os.environ.get("EDITOR", "vi")

    if not user_config_path.exists():
        user_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(user_config_path, "w") as f:
            f.write("version: 1\n")

    try:
        subprocess.run([editor, str(user_config_path)], check=True)
        console.print(f"[green]✓[/green] Config edited: {user_config_path}")
    except subprocess.CalledProcessError:
        console.print("[red]Error opening editor[/red]")
        sys.exit(1)


def _get_common_exclusions() -> list[tuple[str, str, bool]]:
    """Get list of common exclusion patterns.

    Returns:
        List of (pattern, description, default) tuples
    """
    return [
        ("~/.claude/settings.json", "Claude Code settings", False),
        ("~/.codex/config.toml", "Codex CLI config", False),
        ("~/.gemini/settings.json", "Gemini CLI settings", False),
        ("~/.gemini/GEMINI.md", "Gemini rules", True),
        ("~/.config/goose/config.yaml", "Goose config", False),
        ("~/.config/goose/.goosehints", "Goose hints", True),
        ("~/AGENTS.md", "Shared agents file", False),
    ]


def _collect_exclusion_patterns() -> list[str]:
    """Collect exclusion patterns from user (Step 1).

    Returns:
        List of exclusion patterns
    """
    from rich.console import Console

    console = Console()

    console.print("\n[bold]Step 1: Exclusion Patterns[/bold]")
    console.print("Do you want to exclude any files from being managed?\n")

    console.print("Common files to exclude:")
    selected_exclusions = []

    for pattern, description, default in _get_common_exclusions():
        default_str = "Y/n" if default else "y/N"
        response = console.input(f"  Exclude {description}? [{default_str}]: ").lower()
        should_exclude = (default and response != "n") or (
            not default and response == "y"
        )
        if should_exclude:
            selected_exclusions.append(pattern)
            console.print(f"    [green]✓[/green] Will exclude: {pattern}")

    console.print(
        "\n[dim]Enter custom exclusion patterns (glob patterns supported)[/dim]"
    )
    console.print("[dim]One per line, empty line to finish:[/dim]")
    while True:
        pattern = console.input("> ").strip()
        if not pattern:
            break
        selected_exclusions.append(pattern)
        console.print(f"  [green]✓[/green] Added: {pattern}")

    if selected_exclusions:
        console.print(
            f"\n[green]✓[/green] Configured {len(selected_exclusions)} exclusion pattern(s)"
        )

    return selected_exclusions


def _collect_settings_overrides() -> dict[str, dict[str, Any]]:
    """Collect settings overrides from user (Step 2).

    Returns:
        Dictionary of agent settings overrides
    """
    from rich.console import Console

    console = Console()

    import json

    console.print("\n[bold]Step 2: Settings Overrides[/bold]")
    response = console.input(
        "Do you want to override any settings for this machine? [y/N]: "
    )

    if response.lower() != "y":
        return {}

    settings_overrides = {}

    while True:
        console.print("\nWhich agent's settings do you want to override?")
        from ai_rules.config import AGENT_FORMATS

        agent_keys = list(AGENT_FORMATS.keys())
        for i, key in enumerate(agent_keys, 1):
            console.print(f"  {i}) {key}")
        console.print(f"  {len(agent_keys) + 1}) done")
        agent_choice = console.input("> ").strip()

        if agent_choice == str(len(agent_keys) + 1) or not agent_choice:
            break

        agent_map = {str(i): key for i, key in enumerate(agent_keys, 1)}
        agent = agent_map.get(agent_choice)

        if not agent:
            console.print("[yellow]Invalid choice[/yellow]")
            continue

        console.print(f"\n[bold]{agent.title()} settings overrides:[/bold]")
        console.print("[dim]Enter key=value pairs (empty to finish):[/dim]")
        console.print("[dim]Example: model=claude-sonnet-4-5-20250929[/dim]\n")

        agent_overrides = {}
        while True:
            override = console.input("> ").strip()
            if not override:
                break

            if "=" not in override:
                console.print("[yellow]Invalid format. Use key=value[/yellow]")
                continue

            key, value = override.split("=", 1)
            key = key.strip()
            value = value.strip()

            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value

            agent_overrides[key] = parsed_value
            console.print(f"  [green]✓[/green] Added: {key} = {parsed_value}")

        if agent_overrides:
            settings_overrides[agent] = agent_overrides

    if settings_overrides:
        total_overrides = sum(len(v) for v in settings_overrides.values())
        console.print(
            f"\n[green]✓[/green] Configured {total_overrides} override(s) for {len(settings_overrides)} agent(s)"
        )

    return settings_overrides


def _display_configuration_summary(config_data: dict[str, Any]) -> None:
    """Display configuration summary before saving.

    Args:
        config_data: Configuration dictionary to display
    """
    from rich.console import Console

    console = Console()

    console.print("\n[bold cyan]Configuration Summary:[/bold cyan]")
    console.print("=" * 50)

    if "exclude_symlinks" in config_data:
        console.print(
            f"\n[bold]Global Exclusions ({len(config_data['exclude_symlinks'])}):[/bold]"
        )
        for pattern in config_data["exclude_symlinks"]:
            console.print(f"  • {pattern}")

    if "settings_overrides" in config_data:
        console.print("\n[bold]Settings Overrides:[/bold]")
        for agent, overrides in config_data["settings_overrides"].items():
            console.print(f"  [bold]{agent}:[/bold]")
            for key, value in overrides.items():
                console.print(f"    • {key}: {value}")

    console.print("\n" + "=" * 50)


@config.command("init")
def config_init() -> None:
    """Interactive configuration wizard."""
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.config import Config

    console = Console()

    user_config_path = cli_facade.get_user_config_path()

    console.print(
        "[bold cyan]Welcome to ai-agent-rules configuration wizard![/bold cyan]\n"
    )
    console.print("This will help you set up your .ai-agent-rules-config.yaml file.")
    console.print(f"Config will be created at: [dim]{user_config_path}[/dim]\n")

    if user_config_path.exists():
        console.print("[yellow]⚠[/yellow] Config file already exists!")
        if not Confirm.ask("Overwrite existing config?", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    config_data: dict[str, Any] = {"version": 1}

    selected_exclusions = _collect_exclusion_patterns()
    if selected_exclusions:
        config_data["exclude_symlinks"] = selected_exclusions

    settings_overrides = _collect_settings_overrides()
    if settings_overrides:
        config_data["settings_overrides"] = settings_overrides

    _display_configuration_summary(config_data)

    if Confirm.ask("\nSave configuration?", default=True):
        Config.save_user_config(config_data)

        console.print(f"\n[green]✓[/green] Configuration saved to {user_config_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(
            "  • Run [cyan]ai-agent-rules install[/cyan] to apply these settings"
        )
        console.print(
            "  • Run [cyan]ai-agent-rules config show[/cyan] to view your config"
        )
        console.print(
            "  • Run [cyan]ai-agent-rules config show --merged[/cyan] to see merged settings"
        )
    else:
        console.print("[dim]Configuration not saved[/dim]")
