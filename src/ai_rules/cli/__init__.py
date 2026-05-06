"""Command-line interface for ai-agent-rules."""

import logging
import os

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

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
    get_git_repo_root as get_git_repo_root,
)
from ai_rules.cli.helpers import (
    get_targets as get_targets,
)
from ai_rules.cli.helpers import (
    get_user_config_path as get_user_config_path,
)
from ai_rules.cli.helpers import (
    select_targets as select_targets,
)

if TYPE_CHECKING:
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


def detect_old_config_symlinks() -> list[tuple[Path, Path]]:
    """Detect symlinks pointing to old config/ location."""
    from packaging.version import Version

    old_patterns = [
        "/config/AGENTS.md",
        "/config/claude/",
        "/config/codex/",
        "/config/goose/",
        "/config/chat_agent_hints.md",
    ]

    broken_symlinks = []

    check_paths = [
        Path.home() / ".claude",
        Path.home() / ".codex",
        Path.home() / ".config" / "amp",
        Path.home() / ".config" / "goose",
        Path.home() / "AGENTS.md",
    ]

    try:
        use_fast_check = Version(__version__) >= Version("0.5.0")
    except Exception:
        use_fast_check = False

    for base_path in check_paths:
        if not base_path.exists():
            continue

        if base_path.is_symlink():
            try:
                target = os.readlink(str(base_path))
                if any(pattern in str(target) for pattern in old_patterns):
                    if not base_path.resolve().exists():
                        broken_symlinks.append((base_path, Path(target)))
            except (OSError, ValueError):
                pass

        if base_path.is_dir() and not use_fast_check:
            for item in base_path.rglob("*"):
                if item.is_symlink():
                    try:
                        target = os.readlink(str(item))
                        if any(pattern in str(target) for pattern in old_patterns):
                            if not item.resolve().exists():
                                broken_symlinks.append((item, Path(target)))
                    except (OSError, ValueError):
                        pass

    return broken_symlinks


def _display_pending_symlink_changes(targets: list["ConfigTarget"]) -> bool:
    """Display what symlink changes will be made.

    Returns:
        True if changes were found and displayed, False otherwise
    """
    from rich.console import Console

    from ai_rules.symlinks import check_symlink, get_content_diff

    console = Console()
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
                    console.print(f"  [green]+[/green] Create: {target} → {source}")
                else:
                    console.print(f"  [yellow]↻[/yellow] Update: {target} → {source}")
                    if content_diff:
                        console.print(content_diff)

    return found_changes


def _display_pending_plugin_changes(config: "Config") -> bool:
    """Display what plugin changes will be made.

    Returns:
        True if changes were found and displayed, False otherwise
    """
    from rich.console import Console

    console = Console()

    result = _get_plugin_status(config)
    if result is None:
        return False

    plugin_manager, plugin_status = result
    found_changes = False

    if plugin_status.marketplaces_missing:
        found_changes = True
        console.print("\n[bold]Marketplaces[/bold]")
        for marketplace in plugin_status.marketplaces_missing:
            console.print(
                f"  [green]+[/green] Add: {marketplace['name']} ({marketplace['source']})"
            )

    if plugin_status.pending:
        found_changes = True
        console.print("\n[bold]Plugins[/bold]")
        for plugin in plugin_status.pending:
            console.print(
                f"  [green]+[/green] Install: {plugin['name']}@{plugin['marketplace']}"
            )

    if plugin_status.extra:
        if not found_changes:
            console.print("\n[bold]Plugins[/bold]")
        for name in sorted(plugin_status.extra):
            console.print(f"  [dim]○[/dim] {name} (Unmanaged)")

    return found_changes


def check_first_run(targets: list["ConfigTarget"], force: bool) -> bool:
    """Check if this is the first run and prompt user if needed.

    Returns:
        True if should continue, False if should abort
    """
    from rich.console import Console
    from rich.prompt import Confirm

    console = Console()

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

    console.print("\n[yellow]Warning:[/yellow] Found existing configuration files:\n")
    for agent_name, path in existing_files:
        console.print(f"  [{agent_name}] {path}")

    console.print(
        "\n[dim]These will be replaced with symlinks (originals will be backed up).[/dim]\n"
    )

    return Confirm.ask("Continue?", default=False)


def version_callback(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Custom version callback that also checks for updates.

    Args:
        ctx: Click context
        param: Click parameter
        value: Whether --version flag was provided
    """
    from rich.console import Console

    console = Console()

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
                console.print(
                    "statusline, version [dim](installed, version unknown)[/dim]"
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
                console.print("recall, version [dim](installed, version unknown)[/dim]")
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
                console.print("[dim]Run 'ai-agent-rules upgrade' to install[/dim]")
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


def cleanup_orphaned_symlinks(
    selected_targets: list["ConfigTarget"],
    config_dir: Path,
    config: "Config",
    force: bool,
    dry_run: bool,
) -> int:
    """Cleanup all orphaned symlinks across all config types.

    Args:
        selected_targets: List of targets to check
        config_dir: Path to the config directory
        config: Config object
        force: Skip confirmation prompts
        dry_run: Don't actually remove symlinks

    Returns:
        Count of removed symlinks
    """
    import json

    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.claude_extensions import ClaudeExtensionManager
    from ai_rules.skills import SkillManager

    console = Console()
    removed = 0

    ext_manager = ClaudeExtensionManager(config_dir)
    all_orphaned = ext_manager.get_all_orphaned()

    for ext_type, orphaned in all_orphaned.items():
        if orphaned:
            console.print(f"\n[bold yellow]Orphaned {ext_type}:[/bold yellow]")
            for name, path in sorted(orphaned.items()):
                console.print(f"  {name} -> {path}")

            if not dry_run:
                if force or Confirm.ask(f"Remove orphaned {ext_type} symlinks?"):
                    for _name, path in orphaned.items():
                        try:
                            path.unlink()
                            console.print(f"  [green]✓[/green] Removed {path}")
                            removed += 1
                        except OSError as e:
                            console.print(
                                f"  [yellow]⚠[/yellow] Could not remove {path}: {e}"
                            )

    claude_agent = next((a for a in selected_targets if a.target_id == "claude"), None)
    if claude_agent:
        base_settings_path = config_dir / "claude" / "settings.json"
        if base_settings_path.exists():
            try:
                with open(base_settings_path) as f:
                    base_settings = json.load(f)
                merged_settings = config.merge_settings("claude", base_settings)

                orphaned_hooks = ext_manager.get_orphaned_hooks(merged_settings)
                if orphaned_hooks:
                    console.print("\n[bold yellow]Orphaned hooks:[/bold yellow]")
                    for name, path in sorted(orphaned_hooks.items()):
                        console.print(f"  {name} -> {path}")

                    if not dry_run:
                        if force or Confirm.ask("Remove orphaned hook symlinks?"):
                            for _name, path in orphaned_hooks.items():
                                try:
                                    path.unlink()
                                    console.print(f"  [green]✓[/green] Removed {path}")
                                    removed += 1
                                except OSError as e:
                                    console.print(
                                        f"  [yellow]⚠[/yellow] Could not remove {path}: {e}"
                                    )
            except (json.JSONDecodeError, OSError) as e:
                console.print(f"[dim]Could not check for orphaned hooks: {e}[/dim]")

    shared_agent = next((a for a in selected_targets if a.target_id == "shared"), None)
    if shared_agent:
        from ai_rules.config import AGENT_SKILLS_DIRS

        skill_manager = SkillManager(
            config_dir=config_dir,
            agent_id="",
            user_skills_dirs=list(AGENT_SKILLS_DIRS.values()),
        )
        orphaned_skills = skill_manager.get_orphaned_skills()

        if orphaned_skills:
            console.print("\n[bold yellow]Orphaned skills:[/bold yellow]")
            for name, paths in sorted(orphaned_skills.items()):
                for path in paths:
                    console.print(f"  {name} -> {path}")

            if not dry_run:
                if force or Confirm.ask("Remove orphaned skill symlinks?"):
                    for _name, paths in orphaned_skills.items():
                        for path in paths:
                            try:
                                path.unlink()
                                console.print(f"  [green]✓[/green] Removed {path}")
                                removed += 1
                            except OSError as e:
                                console.print(
                                    f"  [yellow]⚠[/yellow] Could not remove {path}: {e}"
                                )

    return removed


def cleanup_deprecated_symlinks(
    selected_targets: list["ConfigTarget"], config_dir: Path, force: bool, dry_run: bool
) -> int:
    """Remove deprecated symlinks that point to our config files.

    Args:
        selected_targets: List of targets to check for deprecated symlinks
        config_dir: Path to the config directory (repo/config)
        force: Skip confirmation prompts
        dry_run: Don't actually remove symlinks

    Returns:
        Count of removed symlinks
    """
    from rich.console import Console

    from ai_rules.symlinks import remove_symlink

    console = Console()
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
                console.print(
                    f"  [yellow]Would remove deprecated:[/yellow] {deprecated_path}"
                )
                removed_count += 1
            else:
                success, message = remove_symlink(target, force=True)
                if success:
                    console.print(
                        f"  [dim]Cleaned up deprecated symlink:[/dim] {deprecated_path}"
                    )
                    removed_count += 1

    return removed_count


def install_user_symlinks(
    selected_targets: list["ConfigTarget"], force: bool, dry_run: bool
) -> dict[str, int]:
    """Install user-level symlinks for all selected targets.

    Returns dict with keys: created, updated, skipped, excluded, errors
    """
    from rich.console import Console

    from ai_rules.symlinks import SymlinkResult, create_symlink

    console = Console()
    console.print("[bold cyan]User-Level Configuration[/bold cyan]")

    if selected_targets:
        config_dir = selected_targets[0].config_dir
        cleanup_deprecated_symlinks(selected_targets, config_dir, force, dry_run)

    created = updated = skipped = excluded = errors = 0

    for agent in selected_targets:
        console.print(f"\n[bold]{agent.name}[/bold]")

        filtered_symlinks = agent.get_filtered_symlinks()
        excluded_count = len(agent.symlinks) - len(filtered_symlinks)

        if excluded_count > 0:
            console.print(
                f"  [dim]({excluded_count} symlink(s) excluded by config)[/dim]"
            )
            excluded += excluded_count

        for target, source in filtered_symlinks:
            effective_force = force or not dry_run
            result, message = create_symlink(target, source, effective_force, dry_run)

            if result == SymlinkResult.CREATED:
                console.print(f"  [green]✓[/green] {target} → {source}")
                created += 1
            elif result == SymlinkResult.ALREADY_CORRECT:
                console.print(f"  [dim]•[/dim] {target} [dim](already correct)[/dim]")
            elif result == SymlinkResult.UPDATED:
                console.print(f"  [yellow]↻[/yellow] {target} → {source}")
                updated += 1
            elif result == SymlinkResult.SKIPPED:
                console.print(f"  [yellow]○[/yellow] {target} [dim](skipped)[/dim]")
                skipped += 1
            elif result == SymlinkResult.ERROR:
                console.print(f"  [red]✗[/red] {target}: {message}")
                errors += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "excluded": excluded,
        "errors": errors,
    }


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
