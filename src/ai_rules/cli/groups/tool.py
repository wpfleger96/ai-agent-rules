from __future__ import annotations

import sys

from pathlib import Path

import click

from ai_rules.bootstrap import ToolSource


def _resolve_configured_source(configured: str | None) -> ToolSource | None:
    """Resolve a configured source string to a ToolSource enum value."""
    if configured and configured.startswith("local:"):
        return ToolSource.LOCAL
    if configured == "github":
        return ToolSource.GITHUB
    if configured == "pypi":
        return ToolSource.PYPI
    return None


def _format_source_display(source: ToolSource | None, configured: str | None) -> str:
    """Format combined source+config info for table display."""
    if not source:
        return "[dim]unknown[/dim]"

    source_str = source.name.lower()
    configured_source = _resolve_configured_source(configured)

    if configured_source is not None and configured_source != source:
        return f"{source_str} [yellow](config: {configured} — run 'setup' to switch)[/yellow]"
    if configured is not None:
        if configured and configured.startswith("local:"):
            local_cfg_path = configured[len("local:") :]
            return f"{source_str} [dim]({local_cfg_path})[/dim]"
        return f"{source_str} [dim](config)[/dim]"
    return source_str


def _format_config_display(source: ToolSource | None, configured: str) -> str:
    """Format config preference for detail display (tool show)."""
    configured_source = _resolve_configured_source(configured)
    if configured_source is not None and source and configured_source != source:
        return f"[yellow]{configured} (run 'setup' to switch)[/yellow]"
    return configured


@click.group()
def tool() -> None:
    """Manage tools and install source preferences."""
    pass


@tool.command("list")
def tool_list() -> None:
    """List managed tools with version and update info."""
    from rich.console import Console
    from rich.table import Table

    from ai_rules.bootstrap import (
        check_tool_updates,
        get_tool_source,
        get_updatable_tools,
    )
    from ai_rules.config import Config

    console = Console()

    try:
        config = Config.load()
    except Exception:
        config = None

    table = Table(title="Managed Tools", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Source", style="bold")
    table.add_column("Version")
    table.add_column("Update")

    has_updates = False

    for spec in get_updatable_tools():
        if not spec.is_installed():
            table.add_row(spec.display_name, "-", "-", "[dim](not installed)[/dim]")
            continue

        source = get_tool_source(spec.package_name)
        configured = config.get_tool_install_source(spec.tool_id) if config else None
        source_display = _format_source_display(source, configured)

        version = spec.get_version()
        version_display = version if version else "[dim]unknown[/dim]"

        update_display = "-"
        try:
            update_info = check_tool_updates(spec, timeout=5)
            if update_info and update_info.has_update:
                update_display = f"[cyan]{update_info.latest_version} available[/cyan]"
                has_updates = True
        except Exception:
            update_display = "[dim](check failed)[/dim]"

        table.add_row(
            spec.display_name, source_display, version_display, update_display
        )

    console.print(table)

    if has_updates:
        console.print("\n[dim]Run 'ai-agent-rules upgrade' to install updates.[/dim]")


@tool.command("show")
@click.argument("tool_id")
def tool_show(tool_id: str) -> None:
    """Show detailed info for a managed tool.

    TOOL_ID can be one of: ai-agent-rules, ai-rules, statusline

    Examples:
        ai-agent-rules tool show statusline
        ai-agent-rules tool show ai-agent-rules
    """
    from rich.console import Console

    from ai_rules.bootstrap import (
        check_tool_updates,
        get_tool_source,
    )
    from ai_rules.bootstrap.updater import _TOOL_ID_ALIASES, get_tool_by_id
    from ai_rules.config import Config

    console = Console()

    canonical_id = _TOOL_ID_ALIASES.get(tool_id, tool_id)
    spec = get_tool_by_id(canonical_id)
    if spec is None:
        from ai_rules.bootstrap import get_updatable_tools

        valid_ids = ", ".join(sorted(t.tool_id for t in get_updatable_tools()))
        console.print(
            f"[red]Error:[/red] Unknown tool '{tool_id}'. Valid tools: {valid_ids}"
        )
        sys.exit(1)

    console.print(f"[bold]{spec.display_name}[/bold]\n")

    if not spec.is_installed():
        console.print("  Status: [dim]not installed[/dim]")
        return

    version = spec.get_version()
    console.print(f"  Version:  {version or '[dim]unknown[/dim]'}")

    source = get_tool_source(spec.package_name)
    console.print(
        f"  Source:   {source.name.lower() if source else '[dim]unknown[/dim]'}"
    )

    try:
        config = Config.load()
        configured = config.get_tool_install_source(spec.tool_id)
    except Exception:
        configured = None
    if configured:
        config_display = _format_config_display(source, configured)
        console.print(f"  Config:   {config_display}")
    else:
        console.print("  Config:   [dim](not set — default: pypi)[/dim]")

    if spec.github_repo:
        console.print(f"  Repo:     https://github.com/{spec.github_repo}")

    try:
        update_info = check_tool_updates(spec, timeout=5)
        if update_info and update_info.has_update:
            console.print(
                f"  Update:   [cyan]{update_info.latest_version} available[/cyan]"
            )
        elif update_info:
            console.print("  Update:   [green]up to date[/green]")
    except Exception:
        console.print("  Update:   [dim](check failed)[/dim]")


@tool.group()
def source() -> None:
    """Manage install source preferences."""
    pass


@source.command("list")
def source_list() -> None:
    """List install source preferences for all tools.

    Examples:
        ai-agent-rules tool source list
    """
    from rich.console import Console
    from rich.table import Table

    from ai_rules.bootstrap.updater import get_updatable_tools
    from ai_rules.config import Config

    console = Console()

    tools = get_updatable_tools()
    table = Table(title="Tool Install Source Preferences", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("User Config")
    table.add_column("Effective (from profile/config)")

    for spec in tools:
        user_pref = Config.get_tool_install_source_from_user_config(spec.tool_id)
        try:
            effective_pref = Config.load().get_tool_install_source(spec.tool_id)
        except Exception:
            effective_pref = None
        table.add_row(
            spec.tool_id,
            user_pref or "[dim](not set)[/dim]",
            effective_pref or "[dim](default: pypi)[/dim]",
        )
    console.print(table)
    console.print(
        "\n[dim]Run 'ai-agent-rules setup' after changing to switch the installed source.[/dim]"
    )


def _resolve_tool_id(tool_id: str) -> str:
    """Resolve a tool ID alias to canonical form, or exit with an error."""
    from ai_rules.bootstrap.updater import _TOOL_ID_ALIASES, get_updatable_tools

    canonical_id = _TOOL_ID_ALIASES.get(tool_id, tool_id)
    valid_ids = {t.tool_id for t in get_updatable_tools()}
    if canonical_id not in valid_ids:
        from rich.console import Console

        Console().print(
            f"[red]Error:[/red] Unknown tool '{tool_id}'. Valid tools: {', '.join(sorted(valid_ids))}"
        )
        sys.exit(1)
    return canonical_id


@source.command("get")
@click.argument("tool_id")
def source_get(tool_id: str) -> None:
    """Show the install source preference for a tool.

    TOOL_ID can be one of: ai-agent-rules, ai-rules, statusline

    Examples:
        ai-agent-rules tool source get statusline
    """
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()
    canonical_id = _resolve_tool_id(tool_id)

    user_pref = Config.get_tool_install_source_from_user_config(canonical_id)
    try:
        effective_pref = Config.load().get_tool_install_source(canonical_id)
    except Exception:
        effective_pref = None

    if user_pref:
        console.print(
            f"[cyan]{canonical_id}[/cyan] user config: [bold]{user_pref}[/bold]"
        )
    else:
        console.print(f"[cyan]{canonical_id}[/cyan] user config: [dim](not set)[/dim]")
    if effective_pref:
        console.print(
            f"[cyan]{canonical_id}[/cyan] effective (profile/config): [bold]{effective_pref}[/bold]"
        )
    else:
        console.print(
            f"[cyan]{canonical_id}[/cyan] effective: [dim](default: pypi)[/dim]"
        )


@source.command("set")
@click.argument("tool_id")
@click.argument("source_value")
def source_set(tool_id: str, source_value: str) -> None:
    """Set the install source preference for a tool.

    TOOL_ID can be one of: ai-agent-rules, ai-rules, statusline

    SOURCE_VALUE can be: pypi, github, local:<path>, or reset

    Examples:
        ai-agent-rules tool source set statusline github
        ai-agent-rules tool source set ai-agent-rules "local:~/Development/Personal/ai-rules"
        ai-agent-rules tool source set statusline reset
    """
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()
    canonical_id = _resolve_tool_id(tool_id)

    if source_value == "reset":
        Config.set_tool_install_source(canonical_id, None)
        console.print(
            f"[green]✓[/green] Cleared install source preference for [cyan]{canonical_id}[/cyan]"
        )
    elif source_value in ("pypi", "github"):
        Config.set_tool_install_source(canonical_id, source_value)
        console.print(
            f"[green]✓[/green] Set [cyan]{canonical_id}[/cyan] install source to [bold]{source_value}[/bold]"
        )
        console.print(
            "[dim]Run 'ai-agent-rules setup' to switch the installed source if needed.[/dim]"
        )
    elif source_value.startswith("local:"):
        local_path = source_value[len("local:") :]
        resolved = Path(local_path).expanduser().resolve()
        if not resolved.exists():
            console.print(f"[red]Error:[/red] Path does not exist: {resolved}")
            sys.exit(1)
        Config.set_tool_install_source(canonical_id, f"local:{resolved}")
        console.print(
            f"[green]✓[/green] Set [cyan]{canonical_id}[/cyan] install source to [bold]local: {resolved}[/bold]"
        )
        console.print(
            "[dim]Run 'ai-agent-rules install' to install from local path.[/dim]"
        )
    else:
        console.print(
            f"[red]Error:[/red] Invalid source value '{source_value}'. Use: pypi, github, local:<path>, or reset"
        )
        sys.exit(1)
