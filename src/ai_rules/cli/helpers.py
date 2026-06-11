"""Shared CLI helper functions."""

from __future__ import annotations

import sys

from importlib.resources import files as resource_files
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from collections.abc import Callable

    from click.decorators import FC
    from click.shell_completion import CompletionItem

    from ai_rules.cli.context import CliContext, Component
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
    from ai_rules.cli.display import print_error

    if not filter_string:
        return all_targets

    requested_ids = {
        agent.strip() for agent in filter_string.split(",") if agent.strip()
    }
    selected = [target for target in all_targets if target.target_id in requested_ids]

    shared_target = next((t for t in all_targets if t.target_id == "shared"), None)
    if shared_target and shared_target not in selected:
        selected.insert(0, shared_target)

    if not selected:
        invalid_ids = requested_ids - {target.target_id for target in all_targets}
        available_ids = [target.target_id for target in all_targets]
        print_error(f"Invalid agent ID(s): {', '.join(sorted(invalid_ids))}")
        from ai_rules.cli.display import print_dim

        print_dim(f"Available agents: {', '.join(available_ids)}")
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
        from ai_rules.cli.display import print_error

        print_error(f"Invalid component ID(s): {', '.join(sorted(invalid_ids))}")
        from ai_rules.cli.display import print_dim

        print_dim(f"Available components: {', '.join(sorted(known_ids))}")
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


def make_component_completer(
    components_attr: str, *, filterable_only: bool = False
) -> Callable[[click.Context, click.Parameter, str], list[CompletionItem]]:
    """Build a --only completion callback for a component list.

    Takes the attribute name on ``ai_rules.cli.components`` (rather than the
    tuple itself) so commands keep their lazy component imports.
    """

    def _complete(
        ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        import ai_rules.cli.components as components_module

        components = getattr(components_module, components_attr)
        ids = tuple(
            c.component_id for c in components if c.filterable or not filterable_only
        )
        return complete_components(ctx, param, incomplete, component_ids=ids)

    return _complete


def agents_option(verb: str) -> Callable[[FC], FC]:
    """Shared ``--agents`` option with target-name completion."""
    return click.option(
        "--agents",
        help=f"Comma-separated list of agents to {verb} (default: all)",
        shell_complete=complete_targets,
    )


def only_option(
    components_attr: str, *, filterable_only: bool = False
) -> Callable[[FC], FC]:
    """Shared ``--only`` option completing against a component list."""
    return click.option(
        "--only",
        "component_filter",
        help="Comma-separated list of components to target (default: all)",
        shell_complete=make_component_completer(
            components_attr, filterable_only=filterable_only
        ),
    )


def build_cli_context(
    components: tuple[Component, ...],
    agents: str | None,
    component_filter: str | None,
    *,
    config_dir: Path | None = None,
    config: Config | None = None,
    profile_name: str | None = None,
    yes: bool = False,
    dry_run: bool = False,
    rebuild_cache: bool = False,
    skip_completions: bool = False,
    force: bool = False,
) -> CliContext:
    """Load config, resolve target/component filters, and build a CliContext."""
    # Route through the facade so monkeypatching ai_rules.cli still applies.
    import ai_rules.cli as cli_facade

    from ai_rules.cli.context import CliContext
    from ai_rules.cli.display import console
    from ai_rules.config import Config as ConfigClass

    if config_dir is None:
        config_dir = cli_facade.get_config_dir()
    if config is None:
        config = ConfigClass.load()
    all_targets = cli_facade.get_targets(config_dir, config)
    selected_targets = cli_facade.select_targets(all_targets, agents)
    parsed_filter = cli_facade.select_components(components, component_filter)

    return CliContext(
        console=console,
        config_dir=config_dir,
        config=config,
        profile_name=profile_name if profile_name is not None else config.profile_name,
        all_targets=tuple(all_targets),
        selected_targets=tuple(selected_targets),
        target_filter=agents,
        component_filter=parsed_filter,
        yes=yes,
        dry_run=dry_run,
        rebuild_cache=rebuild_cache,
        skip_completions=skip_completions,
        force=force,
    )


def save_user_config_and_report(
    data: dict[str, Any], success_msg: str, hint: str | None = None
) -> None:
    """Save user config and print the standard confirmation lines."""
    from ai_rules.cli.display import print_dim, print_hint, print_success
    from ai_rules.config import Config

    Config.save_user_config(data)
    print_success(success_msg)
    print_dim(f"Config updated: {get_user_config_path()}")
    if hint:
        print_hint(hint)


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
