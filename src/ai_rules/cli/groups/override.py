from __future__ import annotations

import sys

from typing import Any

import click

import ai_rules.cli as cli_facade


@click.group()
def override() -> None:
    """Manage settings overrides."""
    pass


def _override_set_scalar(
    agent: str,
    path_components: list[str | int],
    parsed_value: Any,
    data: dict[str, Any],
    console: Any,
) -> None:
    """Set an override value at a path with no array indices."""
    current = data["settings_overrides"][agent]
    for i, component in enumerate(path_components[:-1]):
        if component not in current:
            next_component = (
                path_components[i + 1] if i + 1 < len(path_components) else None
            )
            if isinstance(next_component, int):
                current[component] = []
            else:
                current[component] = {}
        current = current[component]
    current[path_components[-1]] = parsed_value


def _override_set_with_array_index(
    agent: str,
    setting: str,
    path_components: list[str | int],
    parsed_value: Any,
    data: dict[str, Any],
    console: Any,
) -> None:
    """Set an override at an array-indexed path using read-modify-write.

    Loads the current effective merged settings, deep-copies the target
    list, applies the modification, and stores the complete list so that
    wholesale list replacement in deep_merge produces the correct result.
    """
    import copy

    from ai_rules.config import (
        AGENT_FORMATS,
        FORMAT_CONFIG_FILES,
        Config,
        load_config_file,
    )

    dict_prefix: list[str] = []
    for c in path_components:
        if isinstance(c, int):
            break
        dict_prefix.append(c)
    array_suffix = path_components[len(dict_prefix) :]

    cfg = Config.load()
    config_dir = cli_facade.get_config_dir()
    agent_format = AGENT_FORMATS.get(agent)
    if not agent_format:
        console.print(f"[red]Error:[/red] Unknown agent format for '{agent}'")
        sys.exit(1)

    config_file = FORMAT_CONFIG_FILES.get(agent_format, "settings.json")
    base_path = config_dir / agent / config_file
    if base_path.exists():
        base_settings = load_config_file(base_path, agent_format)
        merged = cfg.merge_settings(agent, base_settings)
    else:
        merged = {}

    target_list: list[Any] = []
    node: Any = merged
    for key in dict_prefix:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            node = None
            break
    if isinstance(node, list):
        target_list = copy.deepcopy(node)

    current: Any = target_list
    for i, component in enumerate(array_suffix[:-1]):
        if isinstance(component, int):
            while len(current) <= component:
                current.append({})
            current = current[component]
        else:
            if not isinstance(current, dict) or component not in current:
                if isinstance(current, dict):
                    next_c = array_suffix[i + 1] if i + 1 < len(array_suffix) else None
                    current[component] = [] if isinstance(next_c, int) else {}
                current = current[component]
            else:
                current = current[component]

    final = array_suffix[-1]
    if isinstance(final, int):
        while len(current) <= final:
            current.append(None)
        current[final] = parsed_value
    else:
        current[final] = parsed_value

    dest = data["settings_overrides"][agent]
    for key in dict_prefix[:-1]:
        if key not in dest:
            dest[key] = {}
        dest = dest[key]
    dest[dict_prefix[-1]] = target_list


@override.command("set")
@click.argument("key")
@click.argument("value")
def override_set(key: str, value: str) -> None:
    """Set a settings override for an agent.

    KEY should be in format 'agent.setting' (e.g., 'claude.model')
    Supports array notation: 'claude.hooks.SubagentStop[0].hooks[0].command'
    VALUE will be parsed as JSON if possible, otherwise treated as string

    Array notation examples:
    - claude.hooks.SubagentStop[0].command
    - claude.hooks.SubagentStop[0].hooks[0].command
    - claude.items[0].nested[1].value

    Path validation:
    - Validates agent name (must be 'claude', 'goose', etc.)
    - Validates full path against base settings structure
    - Provides helpful suggestions when paths are invalid
    """
    from rich.console import Console

    from ai_rules.config import (
        Config,
        parse_setting_path,
        validate_override_path,
    )

    console = Console()

    user_config_path = cli_facade.get_user_config_path()
    config_dir = cli_facade.get_config_dir()

    parts = key.split(".", 1)
    if len(parts) != 2:
        console.print("[red]Error:[/red] Key must be in format 'agent.setting'")
        console.print(
            "[dim]Example: claude.model or claude.hooks.SubagentStop[0].command[/dim]"
        )
        sys.exit(1)

    agent, setting = parts

    is_valid, error_msg, warning_msg, suggestions = validate_override_path(
        agent, setting, config_dir
    )

    if not is_valid:
        console.print(f"[red]Error:[/red] {error_msg}")
        if suggestions:
            console.print(
                f"[dim]Available options: {', '.join(suggestions[:10])}[/dim]"
            )
        sys.exit(1)

    if warning_msg:
        console.print(f"[yellow]Warning:[/yellow] {warning_msg}")

    import json

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    data = Config.load_user_config()

    if "settings_overrides" not in data:
        data["settings_overrides"] = {}

    if agent not in data["settings_overrides"]:
        data["settings_overrides"][agent] = {}

    try:
        path_components = parse_setting_path(setting)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    has_array_index = any(isinstance(c, int) for c in path_components)

    if has_array_index:
        _override_set_with_array_index(
            agent, setting, path_components, parsed_value, data, console
        )
    else:
        _override_set_scalar(agent, path_components, parsed_value, data, console)

    Config.save_user_config(data)

    console.print(f"[green]✓[/green] Set override: {agent}.{setting} = {parsed_value}")
    console.print(f"[dim]Config updated: {user_config_path}[/dim]")
    console.print(
        "\n[yellow]💡 Run 'ai-agent-rules install --rebuild-cache' to apply changes[/yellow]"
    )


@override.command("unset")
@click.argument("key")
def override_unset(key: str) -> None:
    """Remove a settings override.

    KEY should be in format 'agent.setting' (e.g., 'claude.model')
    Supports nested keys like 'agent.nested.key'
    """
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    user_config_path = cli_facade.get_user_config_path()

    if not user_config_path.exists():
        console.print("[red]No user config found[/red]")
        sys.exit(1)

    parts = key.split(".", 1)
    if len(parts) != 2:
        console.print("[red]Error:[/red] Key must be in format 'agent.setting'")
        sys.exit(1)

    agent, setting = parts

    data = Config.load_user_config()

    if "settings_overrides" not in data or agent not in data["settings_overrides"]:
        console.print(f"[yellow]Override not found:[/yellow] {key}")
        sys.exit(1)

    setting_parts = setting.split(".")
    current = data["settings_overrides"][agent]

    for part in setting_parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            console.print(f"[yellow]Override not found:[/yellow] {key}")
            sys.exit(1)
        current = current[part]

    final_key = setting_parts[-1]
    if not isinstance(current, dict) or final_key not in current:
        console.print(f"[yellow]Override not found:[/yellow] {key}")
        sys.exit(1)

    del current[final_key]

    current = data["settings_overrides"][agent]
    path = []

    for part in setting_parts[:-1]:
        path.append((current, part))
        current = current[part]

    for parent, key in reversed(path):
        if isinstance(parent[key], dict) and not parent[key]:
            del parent[key]
        else:
            break

    if not data["settings_overrides"][agent]:
        del data["settings_overrides"][agent]

    Config.save_user_config(data)

    console.print(f"[green]✓[/green] Removed override: {key}")
    console.print(f"[dim]Config updated: {user_config_path}[/dim]")
    console.print(
        "\n[yellow]💡 Run 'ai-agent-rules install --rebuild-cache' to apply changes[/yellow]"
    )


@override.command("list")
def override_list() -> None:
    """List all settings overrides."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    user_data = Config.load_user_config()
    user_overrides = user_data.get("settings_overrides", {})

    if not user_overrides:
        console.print("[dim]No settings overrides configured[/dim]")
        return

    console.print("[bold]Settings Overrides:[/bold]\n")

    for agent, overrides in sorted(user_overrides.items()):
        console.print(f"[bold]{agent}:[/bold]")
        for key, value in sorted(overrides.items()):
            console.print(f"  • {key}: {value}")
        console.print()
