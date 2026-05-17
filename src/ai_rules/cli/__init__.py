"""Command-line interface for ai-agent-rules."""

import logging

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from ai_rules.cli.helpers import (
    complete_components as complete_components,
)
from ai_rules.cli.helpers import (
    complete_profiles as complete_profiles,
)
from ai_rules.cli.helpers import (
    complete_targets as complete_targets,
)
from ai_rules.cli.helpers import (
    format_summary as format_summary,
)
from ai_rules.cli.helpers import (
    get_config_dir as get_config_dir,
)
from ai_rules.cli.helpers import (
    get_targets as get_targets,
)
from ai_rules.cli.helpers import (
    get_user_config_path as get_user_config_path,
)
from ai_rules.cli.helpers import (
    select_components as select_components,
)
from ai_rules.cli.helpers import (
    select_targets as select_targets,
)

if TYPE_CHECKING:
    from ai_rules.cli.context import CliContext
    from ai_rules.config import Config
    from ai_rules.targets.base import ConfigTarget

logger = logging.getLogger(__name__)

try:
    __version__ = get_version("ai-agent-rules")
except PackageNotFoundError:
    __version__ = "dev"


def _get_plugin_status(config: "Config") -> tuple[Any, Any] | None:
    """Get plugin manager and status if CLI is available and plugins are configured."""
    if not (config.plugins or config.marketplaces):
        return None

    from ai_rules.plugins import PluginManager

    plugin_manager = PluginManager()
    if not plugin_manager.is_cli_available():
        return None

    desired_plugins = config.get_plugin_configs()
    desired_marketplaces = config.get_marketplace_configs()
    plugin_status = plugin_manager.get_status(desired_plugins, desired_marketplaces)

    return (plugin_manager, plugin_status)


def _display_pending_symlink_changes(targets: list["ConfigTarget"]) -> bool:
    """Display what symlink changes will be made.

    Returns:
        True if changes were found and displayed, False otherwise
    """
    from ai_rules.cli.display import console, print_add, print_update
    from ai_rules.symlinks import check_symlink, get_content_diff

    found_changes = False

    for agent in targets:
        agent_changes: list[tuple[str, Path, Path, str | None]] = []
        for target, source in agent.get_filtered_symlinks():
            target_path = target.expanduser()
            status_code, _ = check_symlink(target_path, source)

            if status_code == "correct":
                continue

            found_changes = True
            if status_code == "missing":
                agent_changes.append(("create", target_path, source, None))
            elif status_code == "broken":
                agent_changes.append(("update", target_path, source, None))
            elif status_code in ["wrong_target", "not_symlink"]:
                diff_output = None
                try:
                    if status_code == "wrong_target":
                        actual = target_path.resolve()
                        diff_output = get_content_diff(actual, source)
                    elif status_code == "not_symlink":
                        diff_output = get_content_diff(target_path, source)
                except (OSError, RuntimeError):
                    pass
                agent_changes.append(("update", target_path, source, diff_output))

        if agent_changes:
            console.print(f"\n[bold]{agent.name}[/bold]")
            for action, target, source, content_diff in agent_changes:
                if action == "create":
                    print_add(f"Create: {target} → {source}", indent=2)
                else:
                    print_update(f"Update: {target} → {source}", indent=2)
                    if content_diff:
                        console.print(content_diff)

    return found_changes


def _display_pending_plugin_changes(config: "Config") -> bool:
    """Display what plugin changes will be made.

    Returns:
        True if changes were found and displayed, False otherwise
    """
    from ai_rules.cli.display import console, print_add, print_skipped

    result = _get_plugin_status(config)
    if result is None:
        return False

    plugin_manager, plugin_status = result
    found_changes = False

    if plugin_status.marketplaces_missing:
        found_changes = True
        console.print("\n[bold]Marketplaces[/bold]")
        for marketplace in plugin_status.marketplaces_missing:
            print_add(f"Add: {marketplace['name']} ({marketplace['source']})", indent=2)

    if plugin_status.pending:
        found_changes = True
        console.print("\n[bold]Plugins[/bold]")
        for plugin in plugin_status.pending:
            print_add(f"Install: {plugin['name']}@{plugin['marketplace']}", indent=2)

    if plugin_status.extra:
        if not found_changes:
            console.print("\n[bold]Plugins[/bold]")
        for name in sorted(plugin_status.extra):
            print_skipped(f"{name} (Unmanaged)", indent=2)

    return found_changes


def _display_pending_changes(ctx: "CliContext") -> bool:
    """Display pending changes across all component types. Returns True if any changes found."""
    has_symlink_changes = _display_pending_symlink_changes(list(ctx.selected_targets))
    has_plugin_changes = _display_pending_plugin_changes(ctx.config)
    return has_symlink_changes or has_plugin_changes


def check_first_run(targets: list["ConfigTarget"], force: bool) -> bool:
    """Check if this is the first run and prompt user if needed.

    Returns:
        True if should continue, False if should abort
    """
    from ai_rules.cli.display import console, print_warning

    existing_files = []

    for agent in targets:
        for target, _ in agent.get_filtered_symlinks():
            target_path = target.expanduser()
            if target_path.exists() and not target_path.is_symlink():
                existing_files.append((agent.name, target_path))

    if not existing_files:
        return True

    if force:
        return True

    print_warning("Found existing configuration files:\n")
    for agent_name, path in existing_files:
        console.print(f"  [{agent_name}] {path}")

    from ai_rules.cli.display import print_dim

    console.print()
    print_dim("These will be replaced with symlinks (originals will be backed up).")
    console.print()

    return click.confirm("Continue?", default=False)


def version_callback(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Custom version callback that also checks for updates.

    Args:
        ctx: Click context
        param: Click parameter
        value: Whether --version flag was provided
    """
    from ai_rules.cli.display import console, print_hint

    if not value or ctx.resilient_parsing:
        return

    console.print(f"ai-agent-rules, version {__version__}")

    try:
        from ai_rules.bootstrap import is_command_available

        if is_command_available("claude-statusline"):
            from ai_rules.tools.statusline import StatuslineTool

            statusline_version = StatuslineTool.INSTALL_SPEC.get_version()
            if statusline_version:
                console.print(f"statusline, version {statusline_version}")
            else:
                from ai_rules.cli.display import dim

                console.print(
                    f"statusline, version {dim('(installed, version unknown)')}"
                )
    except Exception as e:
        logger.debug(f"Failed to get statusline version: {e}")

    try:
        from ai_rules.bootstrap import get_tool_version, is_command_available

        if is_command_available("recall"):
            bm_version = get_tool_version("recall-mcp-server")
            if bm_version:
                console.print(f"recall, version {bm_version}")
            else:
                from ai_rules.cli.display import dim as _dim

                console.print(f"recall, version {_dim('(installed, version unknown)')}")
    except Exception as e:
        logger.debug(f"Failed to get recall version: {e}")

    try:
        from ai_rules.bootstrap import check_tool_updates, get_tool_by_id

        tool = get_tool_by_id("ai-agent-rules")
        if tool:
            update_info = check_tool_updates(tool, timeout=3)
            if update_info and update_info.has_update:
                console.print(
                    f"\n[cyan]Update available:[/cyan] {update_info.current_version} → {update_info.latest_version}"
                )
                print_hint("Run 'ai-agent-rules upgrade' to install")
    except Exception as e:
        logger.debug(f"Failed to check for updates in version callback: {e}")

    ctx.exit()


@click.group()
@click.option(
    "--version",
    is_flag=True,
    callback=version_callback,
    expose_value=False,
    is_eager=True,
    help="Show version and check for updates",
)
def main() -> None:
    """AI Rules - Manage user-level AI agent configurations."""
    pass


def cli_entrypoint() -> None:
    main(complete_var="_AI_AGENT_RULES_COMPLETE")


def cleanup_deprecated_symlinks(
    selected_targets: list["ConfigTarget"], config_dir: Path, dry_run: bool
) -> int:
    """Remove deprecated symlinks that point to our config files.

    Args:
        selected_targets: List of targets to check for deprecated symlinks
        config_dir: Path to the config directory (repo/config)
        dry_run: Don't actually remove symlinks

    Returns:
        Count of removed symlinks
    """
    from ai_rules.cli.display import print_would
    from ai_rules.symlinks import remove_symlink

    removed_count = 0

    for agent in selected_targets:
        deprecated_paths = agent.get_deprecated_symlinks()

        for deprecated_path in deprecated_paths:
            target = deprecated_path.expanduser()

            if not target.exists() and not target.is_symlink():
                continue

            if not target.is_symlink():
                continue

            if dry_run:
                print_would(f"Would remove deprecated: {deprecated_path}", indent=2)
                removed_count += 1
            else:
                success, message = remove_symlink(target, force=True)
                if success:
                    from ai_rules.cli.display import print_label

                    print_label(
                        "Cleaned up deprecated symlink", str(deprecated_path), indent=2
                    )
                    removed_count += 1

    return removed_count


def _register_commands() -> None:
    from ai_rules.cli.commands.diff import diff
    from ai_rules.cli.commands.install import install
    from ai_rules.cli.commands.list_agents import list_agents_cmd
    from ai_rules.cli.commands.setup import setup
    from ai_rules.cli.commands.status import status
    from ai_rules.cli.commands.uninstall import uninstall
    from ai_rules.cli.commands.upgrade import upgrade
    from ai_rules.cli.commands.validate import validate
    from ai_rules.cli.groups.completions import completions
    from ai_rules.cli.groups.config import config
    from ai_rules.cli.groups.exclude import exclude
    from ai_rules.cli.groups.override import override
    from ai_rules.cli.groups.profile import profile
    from ai_rules.cli.groups.skill import skill
    from ai_rules.cli.groups.tool import tool

    main.add_command(setup)
    main.add_command(install)
    main.add_command(status)
    main.add_command(uninstall)
    main.add_command(list_agents_cmd)
    main.add_command(upgrade)
    main.add_command(validate)
    main.add_command(diff)
    main.add_command(exclude)
    main.add_command(override)
    main.add_command(config)
    main.add_command(profile)
    main.add_command(completions)
    main.add_command(skill)
    main.add_command(tool)


_register_commands()


if __name__ == "__main__":
    main()
