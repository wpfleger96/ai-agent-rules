"""Command-line interface for ai-agent-rules."""

import logging
import os
import subprocess
import sys

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from importlib.resources import files as resource_files
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem

    from ai_rules.config import Config
    from ai_rules.profiles import Profile
    from ai_rules.targets.base import ConfigTarget

logger = logging.getLogger(__name__)

try:
    __version__ = get_version("ai-agent-rules")
except PackageNotFoundError:
    __version__ = "dev"

GIT_SUBPROCESS_TIMEOUT = 5


def get_user_config_path() -> Path:
    from ai_rules.config import get_user_config_path as _get_user_config_path

    return _get_user_config_path()


def _get_plugin_status(config: "Config") -> tuple[Any, Any] | None:
    """Get plugin manager and status if CLI is available and plugins configured.

    Returns:
        tuple of (PluginManager, PluginStatus) if available, None otherwise
    """
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


def get_config_dir() -> Path:
    """Get the config directory.

    Works in both development mode (git repo) and installed mode (PyPI package).
    Uses importlib.resources which handles both cases automatically.
    """
    try:
        config_resource = resource_files("ai_rules") / "config"
        return Path(str(config_resource))
    except Exception:
        return Path(__file__).parent / "config"


def get_git_repo_root() -> Path:
    """Get the git repository root directory.

    This only works in development mode when the code is in a git repository.
    For installed packages, this will fail - use get_config_dir() instead.
    """
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


def get_targets(config_dir: Path, config: "Config") -> list["ConfigTarget"]:
    """Get all config target instances.

    Args:
        config_dir: Path to the config directory (use get_config_dir())
        config: Configuration object

    Returns:
        List of all available config target instances
    """
    from ai_rules.agents.amp import AmpAgent
    from ai_rules.agents.claude import ClaudeAgent
    from ai_rules.agents.codex import CodexAgent
    from ai_rules.agents.gemini import GeminiAgent
    from ai_rules.agents.goose import GooseAgent
    from ai_rules.agents.shared import SharedAgent
    from ai_rules.tools.statusline import StatuslineTool

    return [
        AmpAgent(config_dir, config),
        ClaudeAgent(config_dir, config),
        CodexAgent(config_dir, config),
        GeminiAgent(config_dir, config),
        GooseAgent(config_dir, config),
        SharedAgent(config_dir, config),
        StatuslineTool(config_dir, config),
    ]


def complete_targets(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list["CompletionItem"]:
    """Dynamically discover and complete target names for --agents option."""
    from click.shell_completion import CompletionItem

    from ai_rules.config import Config

    config_dir = get_config_dir()
    config = Config.load()
    targets = get_targets(config_dir, config)
    target_ids = [target.target_id for target in targets]

    return [CompletionItem(tid) for tid in target_ids if tid.startswith(incomplete)]


def complete_profiles(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list["CompletionItem"]:
    """Dynamically complete profile names for --profile option."""
    from click.shell_completion import CompletionItem

    from ai_rules.profiles import ProfileLoader

    loader = ProfileLoader()
    profiles = loader.list_profiles()

    return [CompletionItem(p) for p in profiles if p.startswith(incomplete)]


def detect_old_config_symlinks() -> list[tuple[Path, Path]]:
    """Detect symlinks pointing to old config/ location.

    Returns list of (symlink_path, old_target) tuples for broken symlinks.
    This is used for migration from v0.4.1 to v0.5.0 when config moved
    from repo root to src/ai_rules/config/.

    Optimization: For versions >= 0.5.0, only check top-level symlinks
    to avoid expensive recursive directory scanning.
    """
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


def select_targets(
    all_targets: list["ConfigTarget"], filter_string: str | None
) -> list["ConfigTarget"]:
    """Select targets based on filter string.

    Args:
        all_targets: List of all available targets
        filter_string: Comma-separated target IDs (e.g., "claude,goose") or None for all

    Returns:
        List of selected targets

    Raises:
        SystemExit: If no targets match the filter
    """
    from rich.console import Console

    console = Console()

    if not filter_string:
        return all_targets

    requested_ids = {a.strip() for a in filter_string.split(",") if a.strip()}
    selected = [target for target in all_targets if target.target_id in requested_ids]

    if not selected:
        invalid_ids = requested_ids - {a.target_id for a in all_targets}
        available_ids = [a.target_id for a in all_targets]
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
    """Format and print operation summary.

    Args:
        dry_run: Whether this was a dry run
        created: Number of symlinks created
        updated: Number of symlinks updated
        skipped: Number of symlinks skipped
        excluded: Number of symlinks excluded by config
        errors: Number of errors encountered
    """
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

        if is_command_available("basic-memory"):
            bm_version = get_tool_version("basic-memory")
            if bm_version:
                console.print(f"basic-memory, version {bm_version}")
            else:
                console.print(
                    "basic-memory, version [dim](installed, version unknown)[/dim]"
                )
    except Exception as e:
        logger.debug(f"Failed to get basic-memory version: {e}")

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

    shared_agent = next((a for a in selected_targets if a.target_id == ""), None)
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


@main.command()
@click.option("--github", is_flag=True, help="Install from GitHub instead of PyPI")
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--skip-symlinks", is_flag=True, help="Skip symlink installation step")
@click.option("--skip-completions", is_flag=True, help="Skip shell completion setup")
@click.option(
    "--profile",
    default=None,
    shell_complete=complete_profiles,
    help="Profile to use (default: 'default')",
)
@click.pass_context
def setup(
    ctx: click.Context,
    github: bool,
    yes: bool,
    dry_run: bool,
    skip_symlinks: bool,
    skip_completions: bool,
    profile: str | None,
) -> None:
    """One-time setup: install symlinks and make ai-agent-rules available system-wide.

    This is the recommended way to install ai-agent-rules for first-time users.

    Example:
        uvx ai-agent-rules setup
    """
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.bootstrap import (
        ensure_statusline_installed,
        get_effective_install_source,
        get_tool_config_dir,
        install_tool,
    )

    console = Console()
    from ai_rules.bootstrap.updater import (
        check_tool_updates,
        get_tool_by_id,
        perform_tool_upgrade,
    )

    console.print("[bold cyan]Step 1/3: Install ai-agent-rules system-wide[/bold cyan]")
    console.print("This allows you to run 'ai-agent-rules' from any directory.\n")

    statusline_from_github = get_effective_install_source(
        "statusline", cli_github_flag=github
    )
    statusline_result, statusline_message = ensure_statusline_installed(
        dry_run=dry_run, from_github=statusline_from_github, allow_source_switch=True
    )
    if statusline_result == "installed":
        if dry_run and statusline_message:
            console.print(f"[dim]{statusline_message}[/dim]")
        else:
            console.print("[green]✓[/green] Installed claude-statusline")
    elif statusline_result == "upgraded":
        console.print(
            f"[green]✓[/green] Upgraded claude-statusline ({statusline_message})"
        )
    elif statusline_result == "upgrade_available":
        console.print(f"[dim]{statusline_message}[/dim]")
    elif statusline_result == "source_switched":
        console.print(
            f"[green]✓[/green] Switched claude-statusline source ({statusline_message})"
        )
    elif statusline_result == "source_switch_needed":
        if dry_run and statusline_message:
            console.print(f"[dim]{statusline_message}[/dim]")
    elif statusline_result == "failed":
        console.print(
            "[yellow]⚠[/yellow] Failed to install claude-statusline (continuing anyway)"
        )

    ai_rules_tool = get_tool_by_id("ai-agent-rules")
    tool_install_success = False

    if ai_rules_tool and ai_rules_tool.is_installed():
        from ai_rules.bootstrap import ToolSource, get_tool_source, uninstall_tool

        ai_rules_from_github = get_effective_install_source(
            "ai-agent-rules", cli_github_flag=github
        )
        current_source = get_tool_source(ai_rules_tool.package_name)
        desired_source = ToolSource.GITHUB if ai_rules_from_github else ToolSource.PYPI
        needs_source_switch = current_source != desired_source

        if needs_source_switch:
            source_name = "GitHub" if ai_rules_from_github else "PyPI"
            if dry_run:
                console.print(
                    f"[dim]Would switch ai-agent-rules from {current_source.name if current_source else 'unknown'} to {source_name}[/dim]"
                )
                tool_install_success = True
            else:
                if not yes and not Confirm.ask(
                    f"Switch ai-agent-rules to {source_name} install?", default=True
                ):
                    console.print("[yellow]Skipped source switch[/yellow]")
                    tool_install_success = True
                else:
                    uninstall_success, _ = uninstall_tool(ai_rules_tool.package_name)
                    if uninstall_success:
                        github_url = (
                            ai_rules_tool.github_install_url
                            if ai_rules_from_github
                            else None
                        )
                        success, message = install_tool(
                            ai_rules_tool.package_name,
                            from_github=ai_rules_from_github,
                            github_url=github_url,
                            force=True,
                        )
                        if success:
                            console.print(
                                f"[green]✓[/green] Switched to {source_name} install"
                            )
                            tool_install_success = True
                        else:
                            console.print(
                                f"[red]Error:[/red] Failed to install: {message}"
                            )
                    else:
                        console.print(
                            "[red]Error:[/red] Failed to uninstall current version"
                        )
        else:
            try:
                update_info = check_tool_updates(ai_rules_tool, timeout=10)
                if update_info and update_info.has_update:
                    if dry_run:
                        console.print(
                            f"[dim]Would upgrade ai-agent-rules {update_info.current_version} → {update_info.latest_version}[/dim]"
                        )
                        tool_install_success = True
                    else:
                        if not yes and not Confirm.ask(
                            f"Upgrade ai-agent-rules {update_info.current_version} → {update_info.latest_version}?",
                            default=True,
                        ):
                            console.print(
                                "[yellow]Skipped ai-agent-rules upgrade[/yellow]"
                            )
                            tool_install_success = True
                        else:
                            success, msg, _ = perform_tool_upgrade(ai_rules_tool)
                            if success:
                                console.print(
                                    f"[green]✓[/green] Upgraded ai-agent-rules ({update_info.current_version} → {update_info.latest_version})"
                                )
                                tool_install_success = True
                            else:
                                console.print(
                                    "[red]Error:[/red] Failed to upgrade ai-agent-rules"
                                )
                else:
                    tool_install_success = True
            except Exception:
                pass

    if not tool_install_success:
        if not yes and not dry_run:
            if not Confirm.ask("Install ai-agent-rules permanently?", default=True):
                console.print(
                    "\n[yellow]Skipped.[/yellow] You can still run via: uvx ai-agent-rules <command>"
                )
                return

        try:
            ai_rules_from_github = get_effective_install_source(
                "ai-agent-rules", cli_github_flag=github
            )
            ai_rules_tool_spec = get_tool_by_id("ai-agent-rules")
            github_url = (
                ai_rules_tool_spec.github_install_url
                if (ai_rules_from_github and ai_rules_tool_spec)
                else None
            )
            success, message = install_tool(
                "ai-agent-rules",
                from_github=ai_rules_from_github,
                github_url=github_url,
                force=yes,
                dry_run=dry_run,
            )

            if dry_run:
                console.print(f"[dim]{message}[/dim]")
                tool_install_success = True
            elif success:
                console.print("[green]✓[/green] Tool installed successfully")
                tool_install_success = True
            else:
                console.print(f"\n[red]Error:[/red] {message}")
                console.print("\n[yellow]Manual installation:[/yellow]")
                console.print("  uv tool install ai-agent-rules")
                return
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            return

    if not skip_symlinks:
        console.print(
            "[bold cyan]Step 2/3: Installing AI agent configuration symlinks[/bold cyan]\n"
        )

        config_dir_override = None
        if tool_install_success and not dry_run:
            try:
                tool_config_dir = get_tool_config_dir("ai-agent-rules")
                if tool_config_dir.exists():
                    config_dir_override = str(tool_config_dir)
                else:
                    console.print(
                        f"[yellow]Warning:[/yellow] Tool config not found at expected location: {tool_config_dir}"
                    )
                    console.print(
                        "[dim]Falling back to current config directory[/dim]\n"
                    )
            except Exception as e:
                console.print(
                    f"[yellow]Warning:[/yellow] Could not determine tool config path: {e}"
                )
                console.print("[dim]Falling back to current config directory[/dim]\n")

        ctx.invoke(
            install,
            yes=yes,
            dry_run=dry_run,
            rebuild_cache=False,
            agents=None,
            skip_completions=True,
            profile=profile,
            config_dir_override=config_dir_override,
        )

    if not skip_completions:
        from ai_rules.completions import (
            detect_shell,
            find_config_file,
            get_supported_shells,
            install_completion,
            is_completion_installed,
            is_legacy_completion_block,
            update_completion,
        )

        console.print("\n[bold cyan]Step 3/3: Shell completion setup[/bold cyan]\n")

        shell = detect_shell()
        if shell:
            config_path = find_config_file(shell)
            if config_path and is_completion_installed(config_path):
                if is_legacy_completion_block(config_path):
                    success, msg = update_completion(shell, dry_run=dry_run)
                    if success:
                        console.print(f"[green]✓[/green] {msg}")
                    else:
                        console.print(f"[yellow]⚠[/yellow] {msg}")
                else:
                    console.print(
                        f"[green]✓[/green] {shell} completion already installed"
                    )
            elif (
                yes
                or dry_run
                or Confirm.ask(f"Install {shell} tab completion?", default=True)
            ):
                success, msg = install_completion(shell, dry_run=dry_run)
                if success:
                    console.print(f"[green]✓[/green] {msg}")
                else:
                    console.print(f"[yellow]⚠[/yellow] {msg}")
        else:
            supported = ", ".join(get_supported_shells())
            console.print(
                f"[dim]Shell completion not available for your shell (only {supported} supported)[/dim]"
            )

    if dry_run:
        console.print("\n[dim]Dry run complete - no changes were made.[/dim]")
    else:
        console.print("\n[green]✓ Setup complete![/green]")
        console.print(
            "You can now run [bold]ai-agent-rules[/bold] (or [bold]ai-rules[/bold]) from anywhere."
        )


@main.command()
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
    shell_complete=complete_targets,
)
@click.option(
    "--skip-completions",
    is_flag=True,
    help="Skip shell completion installation",
)
@click.option(
    "--profile",
    default=None,
    shell_complete=complete_profiles,
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
    from rich.prompt import Confirm

    from ai_rules.bootstrap import (
        ensure_basic_memory_installed,
        ensure_statusline_installed,
        get_effective_install_source,
    )
    from ai_rules.config import Config

    console = Console()

    statusline_result, statusline_message = ensure_statusline_installed(
        dry_run=dry_run,
        from_github=get_effective_install_source("statusline"),
    )
    if statusline_result == "installed":
        if dry_run and statusline_message:
            console.print(f"[dim]{statusline_message}[/dim]\n")
        else:
            console.print("[green]✓[/green] Installed claude-statusline\n")
    elif statusline_result == "failed":
        console.print(
            "[yellow]⚠[/yellow] Failed to install claude-statusline (continuing anyway)\n"
        )

    if config_dir_override:
        config_dir = Path(config_dir_override)
        if not config_dir.exists():
            console.print(f"[red]Error:[/red] Config directory not found: {config_dir}")
            sys.exit(1)
    else:
        config_dir = get_config_dir()

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

    bm_result, bm_message = ensure_basic_memory_installed(
        dry_run=dry_run, config=config
    )
    if bm_result == "installed":
        if dry_run and bm_message:
            console.print(f"[dim]{bm_message}[/dim]\n")
        else:
            console.print("[green]✓[/green] Installed basic-memory\n")
    elif bm_result == "failed":
        console.print(
            "[yellow]⚠[/yellow] Failed to install basic-memory (continuing anyway)\n"
        )

    if not dry_run:
        set_active_profile(profile)

    if profile and profile != "default":
        console.print(f"[dim]Using profile: {profile}[/dim]\n")

    all_targets = get_targets(config_dir, config)
    selected_targets = select_targets(all_targets, agents)

    if not dry_run:
        for agent in all_targets:
            base_path = agent._base_settings_path
            if base_path.exists():
                try:
                    agent.build_merged_settings(force_rebuild=rebuild_cache)
                except ValueError as exc:
                    console.print(
                        f"[red]Error building {agent.name} config:[/red] {exc}"
                    )
                    sys.exit(1)

    if not dry_run:
        old_symlinks = detect_old_config_symlinks()
        if old_symlinks:
            console.print(
                "\n[yellow]Detected config migration from v0.4.1 → v0.5.0[/yellow]"
            )
            console.print(
                f"Found {len(old_symlinks)} symlink(s) pointing to old config location"
            )
            console.print(
                "[dim]Automatically migrating symlinks to new location...[/dim]\n"
            )

            for symlink_path, _old_target in old_symlinks:
                try:
                    symlink_path.unlink()
                    console.print(f"  [dim]✓ Removed old symlink: {symlink_path}[/dim]")
                except Exception as e:
                    console.print(
                        f"  [yellow]⚠ Could not remove {symlink_path}: {e}[/yellow]"
                    )

            console.print("\n[green]✓ Migration complete[/green]")
            console.print("[dim]New symlinks will be created below...[/dim]\n")

    if not dry_run and not yes:
        has_changes = _display_pending_symlink_changes(selected_targets)
        has_plugin_changes = _display_pending_plugin_changes(config)

        if has_changes or has_plugin_changes:
            console.print()
            if not Confirm.ask("Apply these changes?", default=True):
                console.print("[yellow]Installation cancelled[/yellow]")
                sys.exit(0)
        elif not has_changes and not has_plugin_changes:
            if not check_first_run(selected_targets, yes):
                console.print("[yellow]Installation cancelled[/yellow]")
                sys.exit(0)
    elif not dry_run and yes:
        pass

    if dry_run:
        console.print("[bold]Dry run mode - no changes will be made[/bold]\n")

    if not dry_run:
        agents_needing_cache = {a.target_id for a in selected_targets if a.needs_cache}
        orphaned = config.cleanup_orphaned_cache(agents_needing_cache)
        if orphaned:
            console.print(
                f"[dim]✓ Cleaned up orphaned cache for: {', '.join(orphaned)}[/dim]"
            )

    user_results = install_user_symlinks(selected_targets, yes, dry_run)

    from ai_rules.agents.base import Agent
    from ai_rules.mcp import OperationResult

    for target in selected_targets:
        if not isinstance(target, Agent):
            continue
        mgr = target.get_mcp_manager()
        if mgr is None:
            continue

        result, message, conflicts = target.install_mcps(force=yes, dry_run=dry_run)

        if conflicts and not yes:
            console.print(
                f"\n[bold yellow]MCP Conflicts Detected ({target.name}):[/bold yellow]"
            )
            expected_mcps = mgr.load_managed_mcps(config_dir, config)
            installed_mcps = mgr._read_installed()

            for conflict_name in conflicts:
                expected = expected_mcps.get(conflict_name, {})
                installed = installed_mcps.get(conflict_name, {})
                if expected and installed:
                    diff = mgr.format_diff(conflict_name, expected, installed)
                    console.print(f"\n{diff}\n")

            if not dry_run and not Confirm.ask(
                "Overwrite local changes?", default=False
            ):
                console.print("[yellow]Skipped MCP installation[/yellow]")
            else:
                result, message, _ = target.install_mcps(force=True, dry_run=dry_run)
                console.print(f"[green]✓[/green] {message}")
        elif result == OperationResult.UPDATED:
            console.print(f"[green]✓[/green] {message}")
        elif result == OperationResult.ALREADY_INSTALLED:
            console.print(f"[dim]○[/dim] {message}")
        elif result != OperationResult.NOT_FOUND:
            console.print(f"[yellow]⚠[/yellow] {message}")

    claude_agent = next((a for a in selected_targets if a.target_id == "claude"), None)
    if claude_agent is not None:
        if config.plugins or config.marketplaces:
            from ai_rules.plugins import (
                OperationResult as PluginOperationResult,
            )
            from ai_rules.plugins import (
                PluginManager,
            )

            plugin_manager = PluginManager()

            if plugin_manager.is_cli_available():
                desired_plugins = config.get_plugin_configs()
                desired_marketplaces = config.get_marketplace_configs()

                plugin_result, message, warnings = plugin_manager.sync_plugins(
                    desired_plugins, desired_marketplaces, dry_run=dry_run
                )

                if plugin_result == PluginOperationResult.SUCCESS:
                    console.print(f"[green]✓[/green] {message}")
                elif plugin_result == PluginOperationResult.ALREADY_INSTALLED:
                    console.print(f"[dim]○[/dim] {message}")
                elif plugin_result == PluginOperationResult.DRY_RUN:
                    console.print(f"[dim]{message}[/dim]")
                elif plugin_result == PluginOperationResult.ERROR:
                    console.print(f"[yellow]⚠[/yellow] {message}")

                for warning in warnings:
                    console.print(f"[yellow]⚠[/yellow] {warning}")
            elif not dry_run:
                console.print(
                    "[dim]○[/dim] Skipped plugin sync (claude CLI not available)"
                )

    if selected_targets:
        cleanup_orphaned_symlinks(selected_targets, config_dir, config, yes, dry_run)

    total_created = user_results["created"]
    total_updated = user_results["updated"]
    total_skipped = user_results["skipped"]
    total_excluded = user_results["excluded"]
    total_errors = user_results["errors"]

    if not skip_completions:
        from ai_rules.completions import detect_shell, install_completion

        shell = detect_shell()
        if shell:
            success, msg = install_completion(shell, dry_run=dry_run)
            if success and not dry_run and "already installed" not in msg:
                console.print(f"\n[dim]✓ {msg}[/dim]")

    format_summary(
        dry_run,
        total_created,
        total_updated,
        total_skipped,
        total_excluded,
        total_errors,
    )

    if total_errors > 0:
        sys.exit(1)


def _display_symlink_status(
    status_code: str,
    target: Path,
    source: Path,
    message: str,
    agent_label: str | None = None,
) -> bool:
    """Display symlink status with consistent formatting.

    Args:
        status_code: Status code from check_symlink()
        target: Target path to display
        source: Source path (to check if it's a directory)
        message: Status message
        agent_label: Optional agent label for project-level display

    Returns:
        True if status is correct, False otherwise
    """
    from rich.console import Console

    from ai_rules.symlinks import get_content_diff

    console = Console()

    target_str = str(target)
    if source.is_dir():
        target_str = target_str.rstrip("/") + "/"
    target_display = f"{agent_label} {target.name}" if agent_label else target_str

    if status_code == "correct":
        console.print(f"  [green]✓[/green] {target_display}")
        return True
    elif status_code == "missing":
        console.print(f"  [red]✗[/red] {target_display} [dim](not installed)[/dim]")
        return False
    elif status_code == "broken":
        console.print(f"  [red]✗[/red] {target_display} [dim](broken symlink)[/dim]")
        return False
    elif status_code == "wrong_target":
        console.print(f"  [yellow]⚠[/yellow] {target_display} [dim]({message})[/dim]")

        try:
            actual = target.expanduser().resolve()
            diff_output = get_content_diff(actual, source)
            if diff_output:
                console.print(diff_output)
        except (OSError, RuntimeError):
            pass

        return False
    elif status_code == "not_symlink":
        console.print(
            f"  [yellow]⚠[/yellow] {target_display} [dim](not a symlink)[/dim]"
        )

        try:
            diff_output = get_content_diff(target.expanduser(), source)
            if diff_output:
                console.print(diff_output)
        except (OSError, RuntimeError):
            pass

        return False
    return True


@main.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to check (default: all)",
    shell_complete=complete_targets,
)
def status(agents: str | None) -> None:
    """Check status of AI agent symlinks."""
    from rich.console import Console

    from ai_rules.config import Config
    from ai_rules.state import get_active_profile
    from ai_rules.symlinks import check_symlink

    console = Console()

    config_dir = get_config_dir()
    config = Config.load()
    all_targets = get_targets(config_dir, config)
    selected_targets = select_targets(all_targets, agents)

    console.print("[bold]AI Rules Status[/bold]\n")

    active_profile = get_active_profile()
    if active_profile:
        console.print(f"[dim]Profile: {active_profile}[/dim]\n")

    all_correct = True

    from ai_rules.agents.base import Agent

    console.print("[bold cyan]User-Level Configuration[/bold cyan]\n")
    cache_stale = False
    for target in selected_targets:
        console.print(f"[bold]{target.name}:[/bold]")

        all_symlinks = target.symlinks
        filtered_symlinks = target.get_filtered_symlinks()
        excluded_symlinks = [
            (t, s) for t, s in all_symlinks if (t, s) not in filtered_symlinks
        ]

        for tgt, source in filtered_symlinks:
            target_str = str(tgt)
            if any(
                ext in target_str
                for ext in ["/agents/", "/commands/", "/skills/", "/hooks/"]
            ):
                continue

            status_code, message = check_symlink(tgt, source)
            is_correct = _display_symlink_status(status_code, tgt, source, message)
            if not is_correct:
                all_correct = False

        for tgt, _ in excluded_symlinks:
            console.print(f"  [dim]○[/dim] {tgt} [dim](excluded by config)[/dim]")
        if target.needs_cache:
            if target.is_cache_stale():
                console.print("  [yellow]⚠[/yellow] Cached settings are stale")
                diff_output = target.get_cache_diff()
                if diff_output:
                    console.print(diff_output)
                all_correct = False
                cache_stale = True

        mcp_status = target.get_mcp_status() if isinstance(target, Agent) else None
        if (
            mcp_status is not None
            and isinstance(target, Agent)
            and (
                mcp_status.managed_mcps
                or mcp_status.unmanaged_mcps
                or mcp_status.pending_mcps
                or mcp_status.stale_mcps
            )
        ):
            mgr = target.get_mcp_manager()
            console.print("  [bold]MCPs:[/bold]")
            for name in sorted(mcp_status.managed_mcps.keys()):
                is_installed = mcp_status.installed.get(name, False)
                has_override = mcp_status.has_overrides.get(name, False)
                status_text = (
                    "[green]Installed[/green]"
                    if is_installed
                    else "[yellow]Outdated[/yellow]"
                )
                override_text = ", override" if has_override else ""
                console.print(
                    f"    {name:<20} {status_text} [dim](managed{override_text})[/dim]"
                )
                if not is_installed and mgr is not None:
                    expected = mgr.load_managed_mcps(config_dir, config).get(name, {})
                    installed_config = mcp_status.managed_mcps.get(name, {})
                    diff = mgr.format_diff(name, expected, installed_config)
                    if diff:
                        for line in diff.split("\n"):
                            if line.startswith("MCP"):
                                continue
                            if line.strip():
                                console.print(f"      [dim]{line}[/dim]")
                    all_correct = False
            for name in sorted(mcp_status.pending_mcps.keys()):
                has_override = mcp_status.has_overrides.get(name, False)
                override_text = ", override" if has_override else ""
                console.print(
                    f"    {name:<20} [yellow]Not installed[/yellow] [dim](managed{override_text})[/dim]"
                )
                if mgr is not None:
                    expected = mcp_status.pending_mcps.get(name, {})
                    pending_output = mgr.format_pending(name, expected)
                    if pending_output:
                        console.print(pending_output)
                all_correct = False
            for name in sorted(mcp_status.stale_mcps.keys()):
                console.print(
                    f"    {name:<20} [red]Should be removed[/red] [dim](no longer in config)[/dim]"
                )
                all_correct = False
            for name in sorted(mcp_status.unmanaged_mcps.keys()):
                console.print(f"    {name:<20} [dim]Unmanaged[/dim]")

        if target.target_id == "claude":
            plugin_result = _get_plugin_status(config)
            if plugin_result is not None:
                plugin_manager, plugin_status = plugin_result
                desired_plugins = config.get_plugin_configs()

                if (
                    plugin_status.installed
                    or plugin_status.pending
                    or plugin_status.extra
                ):
                    console.print("  [bold]Plugins:[/bold]")

                    for plugin_config in desired_plugins:
                        plugin_key = plugin_config.key
                        if plugin_key in plugin_status.installed:
                            console.print(
                                f"    {plugin_config.name:<20} [green]Installed[/green] [dim](managed)[/dim]"
                            )
                        else:
                            console.print(
                                f"    {plugin_config.name:<20} [yellow]Not installed[/yellow] [dim](managed)[/dim]"
                            )
                            all_correct = False

                    for key in sorted(plugin_status.extra):
                        console.print(f"    {key:<20} [dim]Unmanaged[/dim]")

            extension_status = target.get_extension_status()  # type: ignore[attr-defined]

            merged_settings_for_hooks = {}
            base_settings_path = target._base_settings_path
            if base_settings_path.exists():
                from ai_rules.config import CONFIG_PARSE_ERRORS, load_config_file

                try:
                    base_settings = load_config_file(
                        base_settings_path, target.config_file_format
                    )
                    merged_settings_for_hooks = config.merge_settings(
                        target.target_id, base_settings
                    )
                except CONFIG_PARSE_ERRORS:
                    pass

            from ai_rules.claude_extensions import ClaudeExtensionManager

            ext_manager = ClaudeExtensionManager(config_dir)
            all_orphaned = ext_manager.get_all_orphaned()

            for ext_type, type_name in [
                ("agents", "Agents"),
                ("commands", "Commands"),
                ("hooks", "Hooks"),
            ]:
                type_status = getattr(extension_status, ext_type)

                orphaned_hooks = {}
                if ext_type == "hooks" and merged_settings_for_hooks:
                    from ai_rules.claude_extensions import ClaudeExtensionManager

                    ext_manager = ClaudeExtensionManager(config_dir)
                    orphaned_hooks = ext_manager.get_orphaned_hooks(
                        merged_settings_for_hooks
                    )

                if any(
                    [
                        type_status.managed_installed,
                        type_status.managed_pending,
                        type_status.managed_wrong_target,
                        type_status.unmanaged,
                        orphaned_hooks,
                    ]
                ):
                    console.print(f"  [bold]{type_name}:[/bold]")

                    for name in sorted(type_status.managed_installed.keys()):
                        console.print(
                            f"    {name:<20} [green]Installed[/green] [dim](managed)[/dim]"
                        )

                    for name, item in sorted(type_status.managed_wrong_target.items()):
                        if item.is_broken:
                            console.print(
                                f"    {name:<20} [red]Broken symlink[/red] [dim](managed)[/dim]"
                            )
                        else:
                            console.print(
                                f"    {name:<20} [yellow]Wrong target[/yellow] [dim](managed)[/dim]"
                            )
                            if item.actual_source and item.expected_source:
                                from ai_rules.symlinks import get_content_diff

                                diff_output = get_content_diff(
                                    item.actual_source, item.expected_source
                                )
                                if diff_output:
                                    console.print(diff_output)
                        all_correct = False

                    for name in sorted(type_status.managed_pending.keys()):
                        console.print(
                            f"    {name:<20} [yellow]Not installed[/yellow] [dim](managed)[/dim]"
                        )
                        all_correct = False

                    for name in sorted(type_status.unmanaged.keys()):
                        if ext_type in all_orphaned and name in all_orphaned[ext_type]:
                            console.print(f"    {name:<20} [yellow]Orphaned[/yellow]")
                        else:
                            console.print(f"    {name:<20} [dim]Unmanaged[/dim]")

                    for name in sorted(orphaned_hooks.keys()):
                        console.print(
                            f"    {name:<20} [yellow]No configuration[/yellow] [dim](orphaned)[/dim]"
                        )
                        all_correct = False

        skill_status = target.get_skill_status() if isinstance(target, Agent) else None
        orphaned_skills = {}
        if skill_status:
            from ai_rules.config import AGENT_SKILLS_DIRS
            from ai_rules.skills import SkillManager

            skill_manager = SkillManager(
                config_dir=config_dir,
                agent_id=target.target_id,
                user_skills_dirs=(
                    list(AGENT_SKILLS_DIRS.values()) if target.target_id == "" else None
                ),
            )
            orphaned_skills_list = skill_manager.get_orphaned_skills()
            for name, paths in orphaned_skills_list.items():
                if paths:
                    orphaned_skills[name] = paths[0]

        if skill_status and any(
            [
                skill_status.managed_installed,
                skill_status.managed_pending,
                skill_status.managed_wrong_target,
                skill_status.unmanaged,
            ]
        ):
            console.print("  [bold]Skills:[/bold]")

            for name in sorted(skill_status.managed_installed.keys()):
                console.print(
                    f"    {name:<20} [green]Installed[/green] [dim](managed)[/dim]"
                )

            for name, item in sorted(skill_status.managed_wrong_target.items()):
                if item.is_broken:
                    console.print(
                        f"    {name:<20} [red]Broken symlink[/red] [dim](managed)[/dim]"
                    )
                else:
                    console.print(
                        f"    {name:<20} [yellow]Wrong target[/yellow] [dim](managed)[/dim]"
                    )
                    if item.actual_source and item.expected_source:
                        from ai_rules.symlinks import get_content_diff

                        diff_output = get_content_diff(
                            item.actual_source, item.expected_source
                        )
                        if diff_output:
                            console.print(diff_output)
                all_correct = False

            for name in sorted(skill_status.managed_pending.keys()):
                console.print(
                    f"    {name:<20} [yellow]Not installed[/yellow] [dim](managed)[/dim]"
                )
                all_correct = False

            for name in sorted(skill_status.unmanaged.keys()):
                if name in orphaned_skills:
                    console.print(f"    {name:<20} [yellow]Orphaned[/yellow]")
                else:
                    console.print(f"    {name:<20} [dim]Unmanaged[/dim]")

        console.print()

    console.print("[bold cyan]Optional Tools[/bold cyan]\n")
    from ai_rules.bootstrap import is_command_available

    optional_tools_missing = False
    if is_command_available("claude-statusline"):
        console.print("  [green]✓[/green] claude-statusline installed")
    else:
        console.print("  [yellow]○[/yellow] claude-statusline not installed")
        optional_tools_missing = True

    from ai_rules.bootstrap.installer import _is_basic_memory_configured

    if _is_basic_memory_configured(config):
        if is_command_available("basic-memory"):
            console.print("  [green]✓[/green] basic-memory installed")
        else:
            console.print("  [yellow]○[/yellow] basic-memory not installed")
            optional_tools_missing = True

    console.print()

    console.print("[bold cyan]Shell Completions[/bold cyan]\n")
    from ai_rules.completions import (
        detect_shell,
        find_config_file,
        get_supported_shells,
        is_completion_installed,
    )

    shell = detect_shell()
    if shell:
        config_path = find_config_file(shell)
        if config_path and is_completion_installed(config_path):
            console.print(
                f"  [green]✓[/green] {shell} completion installed ({config_path})"
            )
        else:
            console.print(
                f"  [yellow]○[/yellow] {shell} completion not installed "
                "(run: ai-agent-rules completions install)"
            )
    else:
        supported = ", ".join(get_supported_shells())
        console.print(
            f"  [dim]Shell completion not available for your shell (only {supported} supported)[/dim]"
        )

    console.print()

    if not all_correct:
        if cache_stale:
            console.print(
                "[yellow]💡 Run 'ai-agent-rules install --rebuild-cache' to fix issues[/yellow]"
            )
        else:
            console.print(
                "[yellow]💡 Run 'ai-agent-rules install' to fix issues[/yellow]"
            )
        sys.exit(1)
    elif optional_tools_missing:
        console.print("[green]All symlinks are correct![/green]")
        console.print(
            "[yellow]💡 Run 'ai-agent-rules install' to install optional tools[/yellow]"
        )
    else:
        console.print("[green]All symlinks are correct![/green]")


@main.command()
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@click.option(
    "--agents",
    help="Comma-separated list of agents to uninstall (default: all)",
    shell_complete=complete_targets,
)
def uninstall(yes: bool, agents: str | None) -> None:
    """Remove AI agent symlinks."""
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.config import Config
    from ai_rules.symlinks import remove_symlink

    console = Console()

    config_dir = get_config_dir()
    config = Config.load()
    all_targets = get_targets(config_dir, config)
    selected_targets = select_targets(all_targets, agents)

    from ai_rules.agents.base import Agent

    if not yes:
        console.print("[yellow]Warning:[/yellow] This will remove symlinks for:\n")
        console.print("[bold]Agents:[/bold]")
        for target in selected_targets:
            console.print(f"  • {target.name}")
        console.print()
        if not Confirm.ask("Continue?", default=False):
            console.print("[yellow]Uninstall cancelled[/yellow]")
            sys.exit(0)

    total_removed = 0
    total_skipped = 0

    console.print("\n[bold cyan]User-Level Configuration[/bold cyan]")
    for target in selected_targets:
        console.print(f"\n[bold]{target.name}[/bold]")

        for tgt, _ in target.get_filtered_symlinks():
            success, message = remove_symlink(tgt, yes)

            if success:
                console.print(f"  [green]✓[/green] {tgt} removed")
                total_removed += 1
            elif "Does not exist" in message:
                console.print(f"  [dim]•[/dim] {tgt} [dim](not installed)[/dim]")
            else:
                console.print(f"  [yellow]○[/yellow] {tgt} [dim]({message})[/dim]")
                total_skipped += 1

        if isinstance(target, Agent) and target.get_mcp_manager() is not None:
            from ai_rules.mcp import OperationResult

            result, message = target.uninstall_mcps(force=yes, dry_run=False)
            if result == OperationResult.REMOVED:
                console.print(f"  [green]✓[/green] {message}")
            elif result == OperationResult.NOT_FOUND:
                console.print(f"  [dim]•[/dim] {message}")

    console.print(
        f"\n[bold]Summary:[/bold] Removed {total_removed}, skipped {total_skipped}"
    )


@main.command("list-agents")
def list_agents_cmd() -> None:
    """List available AI agents."""
    from rich.console import Console
    from rich.table import Table

    from ai_rules.config import Config
    from ai_rules.symlinks import check_symlink

    console = Console()

    config_dir = get_config_dir()
    config = Config.load()
    targets = get_targets(config_dir, config)

    table = Table(title="Available AI Agents", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Symlinks", justify="right")
    table.add_column("Status")

    for target in targets:
        all_symlinks = target.symlinks
        filtered_symlinks = target.get_filtered_symlinks()
        excluded_count = len(all_symlinks) - len(filtered_symlinks)

        installed = 0
        for tgt, source in filtered_symlinks:
            status_code, _ = check_symlink(tgt, source)
            if status_code == "correct":
                installed += 1

        total = len(filtered_symlinks)
        status = f"{installed}/{total} installed"
        if excluded_count > 0:
            status += f" ({excluded_count} excluded)"

        table.add_row(target.target_id, target.name, str(total), status)

    console.print(table)


@main.command()
@click.option("--check", is_flag=True, help="Check for updates without installing")
@click.option("--force", is_flag=True, help="Force reinstall even if up to date")
@click.option(
    "-y", "--yes", is_flag=True, help="Auto-confirm installation without prompting"
)
@click.option(
    "--skip-install",
    is_flag=True,
    help="Skip running 'install --rebuild-cache' after upgrade",
)
@click.option(
    "--only",
    type=click.Choice(["ai-agent-rules", "ai-rules", "statusline", "basic-memory"]),
    help="Only upgrade specific tool",
)
def upgrade(
    check: bool, force: bool, yes: bool, skip_install: bool, only: str | None
) -> None:
    """Upgrade ai-agent-rules and related tools to the latest versions.

    Each tool upgrades from its configured install source (PyPI or GitHub).

    Examples:
        ai-agent-rules upgrade                    # Check and install all updates
        ai-agent-rules upgrade --check            # Only check for updates
        ai-agent-rules upgrade -y                 # Auto-confirm installation
        ai-agent-rules upgrade --only=statusline  # Only upgrade statusline tool
    """
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.bootstrap import (
        check_tool_updates,
        get_effective_install_source,
        get_updatable_tools,
        perform_tool_upgrade,
    )
    from ai_rules.bootstrap.installer import install_tool
    from ai_rules.bootstrap.updater import _TOOL_ID_ALIASES

    console = Console()

    resolved_only = _TOOL_ID_ALIASES.get(only, only) if only else None
    all_tools = [
        t
        for t in get_updatable_tools()
        if resolved_only is None or t.tool_id == resolved_only
    ]
    tools = [t for t in all_tools if t.is_installed()]
    if resolved_only is None:
        tools = [t for t in tools if t.is_enabled is None or t.is_enabled()]
    missing_tools = [t for t in all_tools if not t.is_installed()]

    for tool in missing_tools:
        console.print(f"[yellow]⚠[/yellow] {tool.display_name} is not installed")

    if missing_tools and not check:
        if yes or Confirm.ask("\nReinstall missing tools?", default=True):
            for tool in missing_tools:
                from_github = get_effective_install_source(tool.tool_id)
                github_url = tool.github_install_url if from_github else None
                with console.status(f"Installing {tool.display_name}..."):
                    success, msg = install_tool(
                        tool.package_name,
                        from_github=from_github,
                        github_url=github_url,
                    )
                if success:
                    console.print(f"[green]✓[/green] {tool.display_name} reinstalled")
                    tools.append(tool)
                else:
                    console.print(
                        f"[red]Error:[/red] Failed to install {tool.display_name}: {msg}"
                    )

    if not tools:
        if only:
            console.print(f"[yellow]⚠[/yellow] Tool '{only}' is not installed")
        else:
            console.print("[yellow]⚠[/yellow] No tools are installed")
        sys.exit(1)

    tool_updates = []
    for tool in tools:
        try:
            current = tool.get_version()
            if current:
                console.print(
                    f"[dim]{tool.display_name} current version: {current}[/dim]"
                )
        except Exception as e:
            console.print(
                f"[red]Error:[/red] Could not get {tool.display_name} version: {e}"
            )
            continue

        with console.status(f"Checking {tool.display_name} for updates..."):
            try:
                update_info = check_tool_updates(tool)
            except Exception as e:
                console.print(
                    f"[red]Error:[/red] Failed to check {tool.display_name} updates: {e}"
                )
                continue

        if update_info and (update_info.has_update or force):
            tool_updates.append((tool, update_info))
        elif update_info and not update_info.has_update:
            console.print(
                f"[green]✓[/green] {tool.display_name} is already up to date!"
            )

    console.print()

    if not tool_updates and not force:
        console.print("[green]✓[/green] All tools are up to date!")
        return

    for tool, update_info in tool_updates:
        if update_info.has_update:
            console.print(
                f"[cyan]Update available for {tool.display_name}:[/cyan] "
                f"{update_info.current_version} → {update_info.latest_version}"
            )

            if update_info.changelog_entries:
                console.print()
                for version, notes in update_info.changelog_entries:
                    console.print(f"  [bold]v{version}[/bold]")
                    for line in notes.strip().split("\n"):
                        if line.strip():
                            console.print(f"    {line.strip()}")
                console.print()

    if check:
        if tool_updates:
            console.print("\nRun [bold]ai-agent-rules upgrade[/bold] to install")
        return

    if not force and not yes:
        if len(tool_updates) == 1:
            prompt = f"\nInstall {tool_updates[0][0].display_name} update?"
        else:
            prompt = f"\nInstall {len(tool_updates)} updates?"
        if not Confirm.ask(prompt, default=True):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    ai_rules_upgraded = False
    for tool, update_info in tool_updates:
        with console.status(f"Upgrading {tool.display_name}..."):
            try:
                success, msg, was_upgraded = perform_tool_upgrade(tool)
            except Exception as e:
                console.print(
                    f"\n[red]Error:[/red] {tool.display_name} upgrade failed: {e}"
                )
                continue

        if success:
            new_version = tool.get_version()
            if new_version == update_info.latest_version:
                console.print(
                    f"[green]✓[/green] {tool.display_name} upgraded to {new_version}"
                )
                if tool.tool_id == "ai-agent-rules":
                    ai_rules_upgraded = True
            elif new_version == update_info.current_version:
                console.print(
                    f"[yellow]⚠[/yellow] {tool.display_name} upgrade reported success but version unchanged ({new_version})"
                )
            else:
                console.print(
                    f"[green]✓[/green] {tool.display_name} upgraded to {new_version}"
                )
                if tool.tool_id == "ai-agent-rules":
                    ai_rules_upgraded = True
        else:
            console.print(
                f"[red]Error:[/red] {tool.display_name} upgrade failed: {msg}"
            )

    if ai_rules_upgraded and not skip_install:
        try:
            import subprocess

            console.print(
                "\n[dim]Running 'ai-agent-rules install --rebuild-cache'...[/dim]"
            )

            from ai_rules.state import get_active_profile

            current_profile = get_active_profile() or "default"

            result = subprocess.run(
                [
                    "ai-agent-rules",
                    "install",
                    "--rebuild-cache",
                    "-y",
                    "--profile",
                    current_profile,
                ],
                capture_output=False,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                console.print("[dim]✓ Install completed successfully[/dim]")
            else:
                console.print(
                    f"[yellow]⚠[/yellow] Install failed with exit code {result.returncode}"
                )
                console.print(
                    "[dim]Run 'ai-agent-rules install --rebuild-cache' manually to retry[/dim]"
                )
        except subprocess.TimeoutExpired:
            console.print("[yellow]⚠[/yellow] Install timed out after 30 seconds")
            console.print(
                "[dim]Run 'ai-agent-rules install --rebuild-cache' manually to retry[/dim]"
            )
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not run install: {e}")
            console.print(
                "[dim]Run 'ai-agent-rules install --rebuild-cache' manually[/dim]"
            )


@main.command()
def info() -> None:
    """Show installation method and version info for ai-agent-rules tools.

    Displays how each tool was installed (PyPI or GitHub)
    along with current versions and update availability.
    """
    from rich.console import Console
    from rich.table import Table

    from ai_rules.bootstrap import (
        ToolSource,
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

    table = Table(title="AI Rules Installation Info", show_header=True)
    table.add_column("Tool", style="cyan")
    table.add_column("Source", style="bold")
    table.add_column("Version")
    table.add_column("Update")

    has_updates = False

    for tool in get_updatable_tools():
        tool_name = tool.display_name

        if not tool.is_installed():
            table.add_row(tool_name, "-", "-", "[dim](not installed)[/dim]")
            continue

        source = get_tool_source(tool.package_name)
        configured = config.get_tool_install_source(tool.tool_id) if config else None

        if source:
            source_str = source.name.lower()
            configured_source = (
                ToolSource.GITHUB
                if configured == "github"
                else (ToolSource.PYPI if configured == "pypi" else None)
            )
            if configured_source is not None and configured_source != source:
                # Drift: config says one thing, receipt says another
                source_display = f"{source_str} [yellow](config: {configured} — run 'setup' to switch)[/yellow]"
            elif configured is not None:
                source_display = f"{source_str} [dim](config)[/dim]"
            else:
                source_display = source_str
        else:
            source_display = "[dim]unknown[/dim]"

        version = tool.get_version()
        version_display = version if version else "[dim]unknown[/dim]"

        update_display = "-"
        try:
            update_info = check_tool_updates(tool, timeout=5)
            if update_info and update_info.has_update:
                update_display = f"[cyan]{update_info.latest_version} available[/cyan]"
                has_updates = True
        except Exception:
            update_display = "[dim](check failed)[/dim]"

        table.add_row(tool_name, source_display, version_display, update_display)

    console.print(table)

    if has_updates:
        console.print("\n[dim]Run 'ai-agent-rules upgrade' to install updates.[/dim]")


@main.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to validate (default: all)",
    shell_complete=complete_targets,
)
def validate(agents: str | None) -> None:
    """Validate configuration and source files."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    config_dir = get_config_dir()
    config = Config.load()
    all_targets = get_targets(config_dir, config)
    selected_targets = select_targets(all_targets, agents)

    console.print("[bold]Validating AI Rules Configuration[/bold]\n")

    all_valid = True
    total_checked = 0
    total_issues = 0

    for target in selected_targets:
        console.print(f"[bold]{target.name}:[/bold]")
        target_issues = []

        for _tgt, source in target.symlinks:
            total_checked += 1

            if not source.exists():
                target_issues.append((source, "Source file does not exist"))
                all_valid = False
            elif not source.is_file() and not source.is_dir():
                target_issues.append((source, "Source is not a file or directory"))
                all_valid = False
            else:
                console.print(f"  [green]✓[/green] {source.name}")

        excluded_symlinks = [
            (t, s)
            for t, s in target.symlinks
            if (t, s) not in target.get_filtered_symlinks()
        ]
        if excluded_symlinks:
            console.print(
                f"  [dim]({len(excluded_symlinks)} symlink(s) excluded by config)[/dim]"
            )

        for path, issue in target_issues:
            console.print(f"  [red]✗[/red] {path}")
            console.print(f"    [dim]{issue}[/dim]")
            total_issues += 1

        console.print()

    console.print(f"[bold]Summary:[/bold] Checked {total_checked} source file(s)")

    if all_valid:
        console.print("[green]All source files are valid![/green]")
    else:
        console.print(f"[red]Found {total_issues} issue(s)[/red]")
        sys.exit(1)


@main.command()
@click.option(
    "--agents",
    help="Comma-separated list of agents to check (default: all)",
    shell_complete=complete_targets,
)
def diff(agents: str | None) -> None:
    """Show differences between repo configs and installed symlinks."""
    from rich.console import Console

    from ai_rules.config import Config
    from ai_rules.symlinks import check_symlink, get_content_diff

    console = Console()

    config_dir = get_config_dir()
    config = Config.load()
    all_targets = get_targets(config_dir, config)
    selected_targets = select_targets(all_targets, agents)

    console.print("[bold]Configuration Differences[/bold]\n")

    found_differences = False

    for target in selected_targets:
        target_has_diff = False
        target_diffs: list[tuple[Path, Path, str, str, str | None]] = []

        for tgt, source in target.get_filtered_symlinks():
            target_path = tgt.expanduser()
            status_code, message = check_symlink(target_path, source)

            if status_code == "missing":
                target_diffs.append(
                    (target_path, source, "missing", "Not installed", None)
                )
                target_has_diff = True
            elif status_code == "broken":
                target_diffs.append(
                    (target_path, source, "broken", "Broken symlink", None)
                )
                target_has_diff = True
            elif status_code == "wrong_target":
                try:
                    actual = target_path.resolve()
                    diff_output = get_content_diff(actual, source)
                    target_diffs.append(
                        (
                            target_path,
                            source,
                            "wrong",
                            f"Points to {actual}",
                            diff_output,
                        )
                    )
                    target_has_diff = True
                except (OSError, RuntimeError):
                    target_diffs.append(
                        (target_path, source, "broken", "Broken symlink", None)
                    )
                    target_has_diff = True
            elif status_code == "not_symlink":
                try:
                    diff_output = get_content_diff(target_path, source)
                except (OSError, RuntimeError):
                    diff_output = None
                target_diffs.append(
                    (
                        target_path,
                        source,
                        "file",
                        "Regular file (not symlink)",
                        diff_output,
                    )
                )
                target_has_diff = True

        cache_is_stale = False
        if target.needs_cache:
            cache_is_stale = target.is_cache_stale()
            if cache_is_stale:
                target_has_diff = True

        if target_has_diff:
            console.print(f"[bold]{target.name}:[/bold]")
            for path, expected_source, diff_type, desc, content_diff in target_diffs:
                if diff_type == "missing":
                    console.print(f"  [red]✗[/red] {path}")
                    console.print(f"    [dim]{desc}[/dim]")
                    console.print(f"    [dim]Expected: → {expected_source}[/dim]")
                elif diff_type == "broken":
                    console.print(f"  [red]✗[/red] {path}")
                    console.print(f"    [dim]{desc}[/dim]")
                elif diff_type == "wrong":
                    console.print(f"  [yellow]⚠[/yellow] {path}")
                    console.print(f"    [dim]{desc}[/dim]")
                    console.print(f"    [dim]Expected: → {expected_source}[/dim]")
                    if content_diff:
                        console.print(content_diff)
                elif diff_type == "file":
                    console.print(f"  [yellow]⚠[/yellow] {path}")
                    console.print(f"    [dim]{desc}[/dim]")
                    console.print(f"    [dim]Expected: → {expected_source}[/dim]")
                    if content_diff:
                        console.print(content_diff)

            if cache_is_stale:
                console.print("  [yellow]⚠[/yellow] Cached settings are stale")
                diff_output = target.get_cache_diff()
                if diff_output:
                    console.print(diff_output)

            console.print()
            found_differences = True

    if not found_differences:
        console.print("[green]No differences found - all symlinks are correct![/green]")
    else:
        console.print(
            "[yellow]💡 Run 'ai-agent-rules install' to fix these differences[/yellow]"
        )


@main.group()
def exclude() -> None:
    """Manage exclusion patterns."""
    pass


@exclude.command("add")
@click.argument("pattern")
def exclude_add(pattern: str) -> None:
    """Add an exclusion pattern to user config.

    PATTERN can be an exact path or glob pattern (e.g., ~/.claude/*.json)
    """
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    data = Config.load_user_config()

    if "exclude_symlinks" not in data:
        data["exclude_symlinks"] = []

    if pattern in data["exclude_symlinks"]:
        console.print(f"[yellow]Pattern already excluded:[/yellow] {pattern}")
        return

    data["exclude_symlinks"].append(pattern)
    Config.save_user_config(data)

    user_config_path = get_user_config_path()
    console.print(f"[green]✓[/green] Added exclusion pattern: {pattern}")
    console.print(f"[dim]Config updated: {user_config_path}[/dim]")


@exclude.command("remove")
@click.argument("pattern")
def exclude_remove(pattern: str) -> None:
    """Remove an exclusion pattern from user config."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    user_config_path = get_user_config_path()

    if not user_config_path.exists():
        console.print("[red]No user config found[/red]")
        sys.exit(1)

    data = Config.load_user_config()

    if "exclude_symlinks" not in data or pattern not in data["exclude_symlinks"]:
        console.print(f"[yellow]Pattern not found:[/yellow] {pattern}")
        sys.exit(1)

    data["exclude_symlinks"].remove(pattern)
    Config.save_user_config(data)

    console.print(f"[green]✓[/green] Removed exclusion pattern: {pattern}")
    console.print(f"[dim]Config updated: {user_config_path}[/dim]")


@exclude.command("list")
def exclude_list() -> None:
    """List all exclusion patterns."""
    from rich.console import Console

    from ai_rules.config import Config

    console = Console()

    config = Config.load()

    if not config.exclude_symlinks:
        console.print("[dim]No exclusion patterns configured[/dim]")
        return

    console.print("[bold]Exclusion Patterns:[/bold]\n")

    for pattern in sorted(config.exclude_symlinks):
        console.print(f"  • {pattern} [dim](user)[/dim]")


@main.group()
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
    config_dir = get_config_dir()
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

    user_config_path = get_user_config_path()
    config_dir = get_config_dir()

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

    user_config_path = get_user_config_path()

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


@main.group()
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

    config_dir = get_config_dir()
    cfg = Config.load()
    user_config_path = get_user_config_path()

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

    user_config_path = get_user_config_path()
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

    user_config_path = get_user_config_path()

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


@main.group()
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
    profile: "Profile", user_config: dict[str, Any]
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
@click.argument("name", shell_complete=complete_profiles)
@click.pass_context
def profile_switch(ctx: click.Context, name: str) -> None:
    """Switch to a different profile."""
    from rich.console import Console

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


@main.group()
def completions() -> None:
    """Manage shell tab completion."""
    pass


from ai_rules.completions import get_supported_shells

_SUPPORTED_SHELLS = list(get_supported_shells())


@completions.command(name="bash")
def completions_bash() -> None:
    """Output bash completion script for manual installation."""
    from rich.console import Console

    from ai_rules.completions import generate_completion_script

    console = Console()

    try:
        script = generate_completion_script("bash")
        console.print(script)
        console.print(
            "\n[dim]To install: Add the above to your ~/.bashrc or run:[/dim]"
        )
        console.print("[dim]  ai-agent-rules completions install[/dim]")
    except Exception as e:
        console.print(f"[red]Error generating completion script:[/red] {e}")
        sys.exit(1)


@completions.command(name="zsh")
def completions_zsh() -> None:
    """Output zsh completion script for manual installation."""
    from rich.console import Console

    from ai_rules.completions import generate_completion_script

    console = Console()

    try:
        script = generate_completion_script("zsh")
        console.print(script)
        console.print("\n[dim]To install: Add the above to your ~/.zshrc or run:[/dim]")
        console.print("[dim]  ai-agent-rules completions install[/dim]")
    except Exception as e:
        console.print(f"[red]Error generating completion script:[/red] {e}")
        sys.exit(1)


@completions.command(name="install")
@click.option(
    "--shell",
    type=click.Choice(_SUPPORTED_SHELLS, case_sensitive=False),
    help="Shell type (auto-detected if not specified)",
)
def completions_install(shell: str | None) -> None:
    """Install shell completion to config file."""
    from rich.console import Console

    from ai_rules.completions import detect_shell, install_completion

    console = Console()

    if shell is None:
        shell = detect_shell()
        if shell is None:
            console.print(
                "[red]Error:[/red] Could not detect shell. Please specify with --shell"
            )
            sys.exit(1)
        console.print(f"[dim]Detected shell:[/dim] {shell}")

    success, message = install_completion(shell, dry_run=False)

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]Error:[/red] {message}")
        sys.exit(1)


@completions.command(name="uninstall")
@click.option(
    "--shell",
    type=click.Choice(_SUPPORTED_SHELLS, case_sensitive=False),
    help="Shell type (auto-detected if not specified)",
)
def completions_uninstall(shell: str | None) -> None:
    """Remove shell completion from config file."""
    from rich.console import Console

    from ai_rules.completions import (
        detect_shell,
        find_config_file,
        uninstall_completion,
    )

    console = Console()

    if shell is None:
        shell = detect_shell()
        if shell is None:
            console.print(
                "[red]Error:[/red] Could not detect shell. Please specify with --shell"
            )
            sys.exit(1)

    config_path = find_config_file(shell)
    if config_path is None:
        console.print(f"[red]Error:[/red] No {shell} config file found")
        sys.exit(1)

    success, message = uninstall_completion(config_path)

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]Error:[/red] {message}")
        sys.exit(1)


@completions.command(name="update")
@click.option(
    "--shell",
    type=click.Choice(_SUPPORTED_SHELLS, case_sensitive=False),
    help="Shell type (auto-detected if not specified)",
)
def completions_update(shell: str | None) -> None:
    """Re-generate completion block (fixes PATH shadowing issues)."""
    from rich.console import Console

    from ai_rules.completions import detect_shell, update_completion

    console = Console()

    if shell is None:
        shell = detect_shell()
        if shell is None:
            console.print(
                "[red]Error:[/red] Could not detect shell. Use --shell to specify."
            )
            sys.exit(1)
        console.print(f"[dim]Detected shell:[/dim] {shell}")

    success, message = update_completion(shell, dry_run=False)

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]Error:[/red] {message}")
        sys.exit(1)


@completions.command(name="status")
def completions_status() -> None:
    """Show shell completion installation status."""
    from rich.console import Console
    from rich.table import Table

    from ai_rules.completions import (
        detect_shell,
        find_config_file,
        get_supported_shells,
        is_completion_installed,
    )

    console = Console()

    detected_shell = detect_shell()
    console.print("[bold cyan]Shell Completions Status[/bold cyan]\n")

    if detected_shell:
        console.print(f"Detected shell: [cyan]{detected_shell}[/cyan]\n")
    else:
        console.print("[yellow]No supported shell detected[/yellow]\n")

    table = Table(show_header=True)
    table.add_column("Shell")
    table.add_column("Status")
    table.add_column("Config File")

    for shell in get_supported_shells():
        config_path = find_config_file(shell)

        if config_path is None:
            status = "[dim]-[/dim]"
            config_str = "[dim]No config file found[/dim]"
        elif is_completion_installed(config_path):
            status = "[green]✓[/green]"
            config_str = str(config_path)
        else:
            status = "[yellow]○[/yellow]"
            config_str = f"{config_path} [dim](not installed)[/dim]"

        shell_name = f"[bold]{shell}[/bold]" if shell == detected_shell else shell
        table.add_row(shell_name, status, config_str)

    console.print(table)
    console.print("\n[dim]To install: ai-agent-rules completions install[/dim]")


@main.group()
def tool() -> None:
    """Manage tool install source preferences."""
    pass


@tool.command("source")
@click.argument("tool_id", required=False)
@click.argument(
    "source_value",
    required=False,
    type=click.Choice(["pypi", "github", "reset"]),
)
def tool_source(tool_id: str | None, source_value: str | None) -> None:
    """Get or set the persistent install source for a managed tool.

    Without arguments, lists all configured source preferences.

    TOOL_ID can be one of: ai-agent-rules, ai-rules, statusline

    SOURCE_VALUE can be: pypi, github, or reset (to clear the preference)

    Examples:
        ai-agent-rules tool source
        ai-agent-rules tool source statusline github
        ai-agent-rules tool source statusline reset
    """
    from rich.console import Console
    from rich.table import Table

    from ai_rules.bootstrap.updater import _TOOL_ID_ALIASES, get_updatable_tools
    from ai_rules.config import Config

    console = Console()

    if tool_id is None:
        # List all configured preferences
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
        return

    # Normalize alias (ai-rules → ai-agent-rules)
    canonical_id = _TOOL_ID_ALIASES.get(tool_id, tool_id)
    tools = get_updatable_tools()
    valid_ids = {t.tool_id for t in tools}
    if canonical_id not in valid_ids:
        console.print(
            f"[red]Error:[/red] Unknown tool '{tool_id}'. Valid tools: {', '.join(sorted(valid_ids))}"
        )
        sys.exit(1)

    if source_value is None:
        # Show current preference for this tool
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
            console.print(
                f"[cyan]{canonical_id}[/cyan] user config: [dim](not set)[/dim]"
            )
        if effective_pref:
            console.print(
                f"[cyan]{canonical_id}[/cyan] effective (profile/config): [bold]{effective_pref}[/bold]"
            )
        else:
            console.print(
                f"[cyan]{canonical_id}[/cyan] effective: [dim](default: pypi)[/dim]"
            )
        return

    if source_value == "reset":
        Config.set_tool_install_source(canonical_id, None)
        console.print(
            f"[green]✓[/green] Cleared install source preference for [cyan]{canonical_id}[/cyan]"
        )
    else:
        Config.set_tool_install_source(canonical_id, source_value)
        console.print(
            f"[green]✓[/green] Set [cyan]{canonical_id}[/cyan] install source to [bold]{source_value}[/bold]"
        )
        console.print(
            "[dim]Run 'ai-agent-rules setup' to switch the installed source if needed.[/dim]"
        )


if __name__ == "__main__":
    main()
