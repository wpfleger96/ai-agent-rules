"""Configuration loading and management."""

from __future__ import annotations

import copy
import json
import re
import shutil
import sys

from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

from ai_rules.utils import deep_merge

if TYPE_CHECKING:
    from ai_rules.plugins import MarketplaceConfig, PluginConfig

__all__ = [
    "Config",
    "AGENT_FORMATS",
    "FORMAT_CONFIG_FILES",
    "AGENT_SKILLS_DIRS",
    "CONFIG_PARSE_ERRORS",
    "ManagedFieldsTracker",
    "dump_config_file",
    "get_managed_fields_path",
    "get_user_config_path",
    "load_config_file",
    "navigate_path",
    "parse_setting_path",
    "validate_override_path",
]

AGENT_FORMATS: dict[str, str] = {
    "amp": "json",
    "claude": "json",
    "codex": "toml",
    "gemini": "json",
    "goose": "yaml",
    "statusline": "yaml",
}

FORMAT_CONFIG_FILES: dict[str, str] = {
    "json": "settings.json",
    "toml": "config.toml",
    "yaml": "config.yaml",
}

AGENT_SKILLS_DIRS = {
    "amp": Path("~/.config/agents/skills"),
    "claude": Path("~/.claude/skills"),
    "codex": Path("~/.agents/skills"),
    # Gemini CLI not listed here — it discovers skills from ~/.agents/skills/ via
    # built-in alias. Adding ~/.gemini/skills/ would cause "Skill conflict detected"
    # warnings that break headless invocations (e.g., crossfire code review).
    "goose": Path("~/.config/goose/skills"),
}

_CONFIG_FILE_NAME = ".ai-agent-rules-config.yaml"
_LEGACY_CONFIG_FILE_NAME = ".ai-rules-config.yaml"

_MANAGED_FIELDS_FILE = "ai-agent-rules-managed-fields.json"
_LEGACY_MANAGED_FIELDS_FILE = "ai-rules-managed-fields.json"


def get_user_config_path() -> Path:
    """Get the user config file path, migrating from legacy path if needed."""
    import sys

    home = Path.home()
    new_path = home / _CONFIG_FILE_NAME
    old_path = home / _LEGACY_CONFIG_FILE_NAME

    if new_path.exists():
        if old_path.exists():
            old_size = old_path.stat().st_size
            new_size = new_path.stat().st_size
            if new_size == 0 and old_size > 0:
                shutil.copy2(old_path, new_path)
                old_path.rename(old_path.with_suffix(".yaml.migrated"))
            else:
                print(
                    f"Warning: Found config at both {old_path} and {new_path}. Using {new_path}.",
                    file=sys.stderr,
                )
        return new_path

    if old_path.exists():
        old_path.rename(new_path)
        return new_path

    return new_path


def get_managed_fields_path() -> Path:
    """Get the managed fields tracking file path, migrating from legacy if needed."""
    claude_dir = Path.home() / ".claude"
    new_path = claude_dir / _MANAGED_FIELDS_FILE
    old_path = claude_dir / _LEGACY_MANAGED_FIELDS_FILE

    if not new_path.exists() and old_path.exists():
        old_path.rename(new_path)

    return new_path


CONFIG_PARSE_ERRORS = (
    json.JSONDecodeError,
    yaml.YAMLError,
    tomllib.TOMLDecodeError,
    OSError,
    ValueError,
)


def load_config_file(path: Path, config_format: str) -> dict[str, Any]:
    """Load a config file based on format.

    Args:
        path: Path to the config file
        config_format: One of 'json', 'yaml', 'toml'

    Returns:
        Parsed config dictionary

    Raises:
        ValueError: If config_format is unsupported
        OSError, json.JSONDecodeError, yaml.YAMLError, tomllib.TOMLDecodeError: on parse errors
    """
    if config_format == "toml":
        with open(path, "rb") as f:
            return tomllib.load(f)
    elif config_format == "json":
        with open(path) as f:
            result: dict[str, Any] = json.load(f)
            return result
    elif config_format == "yaml":
        with open(path) as f:
            result = yaml.safe_load(f) or {}
            return result
    raise ValueError(f"Unsupported config format: {config_format}")


def _validate_value_for_format(value: Any, config_format: str, path: str) -> None:
    """Recursively validate a config value for format compatibility."""
    if value is None and config_format == "toml":
        raise ValueError(
            f"Cannot write null value at '{path}' to TOML. "
            "Use 'override unset' to remove the key, or set an explicit value."
        )
    if isinstance(value, dict):
        _validate_for_format(value, config_format, path)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _validate_value_for_format(item, config_format, f"{path}[{i}]")


def _validate_for_format(
    data: dict[str, Any], config_format: str, path: str = ""
) -> None:
    """Validate config values are compatible with the target serialization format."""
    for key, value in data.items():
        if config_format == "toml" and not isinstance(key, str):
            raise ValueError(
                f"TOML requires string keys, but '{path}' contains "
                f"key {key!r} of type {type(key).__name__}. "
                "Check your YAML config for unquoted numeric or boolean keys."
            )
        current = f"{path}.{key}" if path else key
        _validate_value_for_format(value, config_format, current)


def dump_config_file(path: Path, data: dict[str, Any], config_format: str) -> None:
    """Write a config file based on format.

    Args:
        path: Path to write the config file
        data: Configuration dictionary to serialize
        config_format: One of 'json', 'yaml', 'toml'

    Raises:
        ValueError: If config_format is unsupported or data contains incompatible values
        OSError, tomli_w errors: on write errors
    """
    _validate_for_format(data, config_format)
    if config_format == "toml":
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
    elif config_format == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    elif config_format == "yaml":
        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    else:
        raise ValueError(f"Unsupported config format: {config_format}")


def parse_setting_path(path: str) -> list[str | int]:
    """Parse a setting path with array indices into components.

    Examples:
        'model' -> ['model']
        'hooks.SubagentStop[0].command' -> ['hooks', 'SubagentStop', 0, 'command']
        'env.SOME_VAR' -> ['env', 'SOME_VAR']
        'hooks.SubagentStop[0].hooks[0].command' -> ['hooks', 'SubagentStop', 0, 'hooks', 0, 'command']

    Args:
        path: Setting path string with optional array indices

    Returns:
        List of path components (str for keys, int for array indices)

    Raises:
        ValueError: If array indices are invalid or path is malformed
    """
    if not path:
        raise ValueError("Path cannot be empty")

    components = []
    parts = path.split(".")

    for part in parts:
        if "[" in part:
            match = re.match(r"^([^\[]+)(\[\d+\])+$", part)
            if not match:
                raise ValueError(
                    f"Invalid array notation in '{part}'. Use format: key[0] or key[0][1]"
                )

            key = match.group(1)
            components.append(key)

            indices = re.findall(r"\[(\d+)\]", part)
            for idx in indices:
                components.append(int(idx))
        else:
            components.append(part)

    return components


def navigate_path(data: Any, path_components: list[str | int]) -> tuple[Any, bool, str]:
    """Navigate a data structure using path components.

    Args:
        data: Data structure to navigate (dict, list, or primitive)
        path_components: List of path components (str for keys, int for indices)

    Returns:
        Tuple of (value_at_path, success, error_message)
        - If success: (value, True, '')
        - If failure: (None, False, 'error description')
    """
    current = data

    for i, component in enumerate(path_components):
        if isinstance(component, int):
            if not isinstance(current, list):
                path_so_far = _format_path(path_components[:i])
                return (
                    None,
                    False,
                    f"Expected array at '{path_so_far}' but found {type(current).__name__}",
                )

            if component >= len(current):
                path_so_far = _format_path(path_components[:i])
                return (
                    None,
                    False,
                    f"Array index {component} out of range at '{path_so_far}' (length: {len(current)})",
                )

            current = current[component]
        else:
            if not isinstance(current, dict):
                path_so_far = _format_path(path_components[:i])
                return (
                    None,
                    False,
                    f"Expected object at '{path_so_far}' but found {type(current).__name__}",
                )

            if component not in current:
                path_so_far = _format_path(path_components[: i + 1])
                return (
                    None,
                    False,
                    f"Key '{component}' not found at '{path_so_far}'",
                )

            current = current[component]

    return (current, True, "")


def _format_path(components: list[str | int]) -> str:
    """Format path components back into a string representation.

    Args:
        components: List of path components

    Returns:
        Formatted path string
    """
    if not components:
        return ""

    result = []
    i = 0
    while i < len(components):
        component = components[i]
        if isinstance(component, str):
            result.append(component)
            i += 1
        else:
            if result:
                result[-1] += f"[{component}]"
            i += 1

    return ".".join(result)


def validate_override_path(
    agent: str, setting: str, config_dir: Path
) -> tuple[bool, str, str, list[str]]:
    """Validate an override path against base settings.

    Args:
        agent: Agent name (e.g., 'claude', 'goose')
        setting: Setting path (e.g., 'hooks.SubagentStop[0].command')
        config_dir: Config directory path

    Returns:
        Tuple of (is_valid, error_message, warning_message, suggestions)
        - If valid: (True, '', '', [])
        - If invalid (hard error): (False, 'error message', '', ['suggestion1', 'suggestion2'])
        - If valid with warning: (True, '', 'warning message', ['suggestion1', 'suggestion2'])
    """
    valid_agents = list(AGENT_FORMATS.keys())
    if agent not in valid_agents:
        return (
            False,
            f"Unknown agent '{agent}'",
            "",
            valid_agents,
        )

    config_format = AGENT_FORMATS[agent]
    config_file = FORMAT_CONFIG_FILES.get(config_format, "settings.json")
    settings_file = config_dir / agent / config_file
    if not settings_file.exists():
        return (
            False,
            f"No base settings file found for agent '{agent}' at {settings_file}",
            "",
            [],
        )

    try:
        base_settings = load_config_file(settings_file, config_format)
    except CONFIG_PARSE_ERRORS as e:
        return (False, f"Failed to load base settings: {e}", "", [])

    try:
        path_components = parse_setting_path(setting)
    except ValueError as e:
        return (False, str(e), "", [])

    value, success, error_msg = navigate_path(base_settings, path_components)

    if success:
        return (True, "", "", [])

    suggestions = []
    if "not found" in error_msg.lower():
        for i in range(len(path_components) - 1, -1, -1):
            partial_path = path_components[:i]
            partial_value, partial_success, _ = navigate_path(
                base_settings, partial_path
            )
            if partial_success and isinstance(partial_value, dict):
                suggestions = list(partial_value.keys())
                break

    error_msg = f"Path '{setting}' not found in base config."
    if suggestions:
        error_msg += f" Did you mean one of: {', '.join(suggestions[:5])}?"

    return (False, error_msg, "", suggestions)


class ManagedFieldsTracker:
    """Track ai-agent-rules contributions to preserved fields.

    Prevents stale entries when ai-agent-rules removes something from source config
    while preserving user-added entries.
    """

    def __init__(self, path: Path | None = None):
        if path is None:
            path = get_managed_fields_path()
        self.path = path
        self._data: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load tracked ai-agent-rules contributions."""
        if not self.path.exists():
            return {"version": 1}

        try:
            with open(self.path) as f:
                self._data = json.load(f)
                return self._data
        except (OSError, json.JSONDecodeError):
            return {"version": 1}

    def save(self, contributions: dict[str, Any] | None = None) -> None:
        """Save ai-agent-rules contributions."""
        if contributions is not None:
            self._data = contributions

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self._data, f, indent=2)
            with open(self.path, "a") as f:
                f.write("\n")
        except Exception:
            pass

    def get_field_contributions(self, field: str) -> Any:
        """Get ai-agent-rules contributions for a specific field."""
        if not self._data:
            self.load()
        return self._data.get(field)

    def set_field_contributions(self, field: str, value: Any) -> None:
        """Update ai-agent-rules contributions for a specific field."""
        if not self._data:
            self.load()
        if value is None:
            self._data.pop(field, None)
        else:
            self._data[field] = value

    def cleanup_stale_entries(
        self,
        existing_settings: dict[str, Any],
        source_settings: dict[str, Any],
        preserved_fields: list[str],
    ) -> dict[str, Any]:
        """Remove stale ai-agent-rules contributions from existing settings.

        For each preserved field:
        1. Get what ai-agent-rules previously contributed (from tracking file)
        2. Get what ai-agent-rules currently contributes (from source settings)
        3. Find entries in existing that match stale ai-agent-rules contributions
        4. Remove those stale entries, keep everything else

        Returns cleaned existing_settings.
        """
        self.load()

        cleaned = copy.deepcopy(existing_settings)

        for field in preserved_fields:
            tracked = self.get_field_contributions(field)
            if not tracked:
                continue

            source = source_settings.get(field)
            existing = cleaned.get(field)

            if field == "hooks":
                cleaned[field] = self._cleanup_hooks(
                    existing or {}, tracked, source or {}
                )
                if not cleaned[field]:
                    cleaned.pop(field, None)

        return cleaned

    def _cleanup_hooks(
        self,
        existing_hooks: dict[str, Any],
        tracked_hooks: dict[str, Any],
        source_hooks: dict[str, Any],
    ) -> dict[str, Any]:
        """Remove stale ai-rules hook contributions.

        For each event type (UserPromptSubmit, PreCompact, etc.):
        1. Get tracked commands ai-agent-rules added
        2. Get current commands in source config
        3. For each tracked command not in source, remove from existing
        4. Keep all user-added hooks
        """
        cleaned = copy.deepcopy(existing_hooks)

        for event_type, tracked_entries in tracked_hooks.items():
            tracked_commands = self._extract_commands(tracked_entries)
            source_commands = self._extract_commands(source_hooks.get(event_type, []))

            stale_commands = tracked_commands - source_commands

            if event_type in cleaned and stale_commands:
                cleaned[event_type] = [
                    entry
                    for entry in cleaned[event_type]
                    if not self._entry_matches_commands(entry, stale_commands)
                ]
                if not cleaned[event_type]:
                    del cleaned[event_type]

        return cleaned

    def _extract_commands(self, entries: list[Any]) -> set[str]:
        """Extract command strings from hook entries."""
        commands = set()
        for entry in entries:
            if isinstance(entry, dict) and "hooks" in entry:
                for hook in entry["hooks"]:
                    if isinstance(hook, dict) and "command" in hook:
                        commands.add(hook["command"])
        return commands

    def _entry_matches_commands(
        self, entry: dict[str, Any], commands: set[str]
    ) -> bool:
        """Check if a hook entry contains any of the given commands."""
        if not isinstance(entry, dict) or "hooks" not in entry:
            return False
        for hook in entry["hooks"]:
            if isinstance(hook, dict) and hook.get("command") in commands:
                return True
        return False


class Config:
    """Configuration for ai-agent-rules tool."""

    def __init__(
        self,
        exclude_symlinks: list[str] | None = None,
        settings_overrides: dict[str, dict[str, Any]] | None = None,
        mcp_overrides: dict[str, dict[str, Any]] | None = None,
        profile_name: str | None = None,
        plugins: list[dict[str, str]] | None = None,
        marketplaces: list[dict[str, str]] | None = None,
    ):
        self.exclude_symlinks = set(exclude_symlinks or [])
        self.settings_overrides = settings_overrides or {}
        self.mcp_overrides = mcp_overrides or {}
        self.profile_name = profile_name
        self.plugins = plugins or []
        self.marketplaces = marketplaces or []

    def get_plugin_configs(self) -> list[PluginConfig]:
        """Convert plugin dicts to PluginConfig objects."""
        from ai_rules.plugins import PluginConfig

        configs = []
        for p in self.plugins:
            if "name" not in p or "marketplace" not in p:
                raise ValueError(
                    f"Plugin config missing required fields (name, marketplace): {p}"
                )
            configs.append(PluginConfig(name=p["name"], marketplace=p["marketplace"]))
        return configs

    def get_marketplace_configs(self) -> list[MarketplaceConfig]:
        """Convert marketplace dicts to MarketplaceConfig objects."""
        from ai_rules.plugins import MarketplaceConfig

        configs = []
        for m in self.marketplaces:
            if "name" not in m or "source" not in m:
                raise ValueError(
                    f"Marketplace config missing required fields (name, source): {m}"
                )
            configs.append(MarketplaceConfig(name=m["name"], source=m["source"]))
        return configs

    @classmethod
    def load(cls, profile: str | None = None) -> Config:
        """Load configuration from profile and ~/.ai-agent-rules-config.yaml.

        Merge order (lowest to highest priority):
        1. Profile overrides (if profile specified, defaults to active profile or "default")
        2. Local overrides from ~/.ai-agent-rules-config.yaml

        Args:
            profile: Optional profile name to load (default: active profile or "default")

        Returns:
            Config instance with merged overrides
        """
        if profile is None:
            from ai_rules.state import get_active_profile

            profile = get_active_profile() or "default"
        return cls._load_cached(profile)

    @classmethod
    @lru_cache(maxsize=8)
    def _load_cached(cls, profile_name: str) -> Config:
        """Internal cached loader keyed by profile name."""
        from ai_rules.profiles import ProfileLoader, ProfileNotFoundError

        loader = ProfileLoader()

        try:
            profile_data = loader.load_profile(profile_name)
        except ProfileNotFoundError:
            raise

        exclude_symlinks = list(profile_data.exclude_symlinks)
        settings_overrides = copy.deepcopy(profile_data.settings_overrides)
        mcp_overrides = copy.deepcopy(profile_data.mcp_overrides)
        plugins = copy.deepcopy(profile_data.plugins)
        marketplaces = copy.deepcopy(profile_data.marketplaces)

        user_config_path = get_user_config_path()
        if user_config_path.exists():
            with open(user_config_path) as f:
                user_data = yaml.safe_load(f) or {}

            user_excludes = user_data.get("exclude_symlinks", [])
            exclude_symlinks = list(set(exclude_symlinks) | set(user_excludes))

            user_settings = user_data.get("settings_overrides", {})
            settings_overrides = deep_merge(settings_overrides, user_settings)

            user_mcp = user_data.get("mcp_overrides", {})
            mcp_overrides = deep_merge(mcp_overrides, user_mcp)

            user_plugins = user_data.get("plugins", [])
            if user_plugins:
                plugins_by_name = {p["name"]: p for p in plugins}
                for plugin in user_plugins:
                    plugins_by_name[plugin["name"]] = plugin
                plugins = list(plugins_by_name.values())

            user_marketplaces = user_data.get("marketplaces", [])
            if user_marketplaces:
                marketplaces_by_name = {m["name"]: m for m in marketplaces}
                for marketplace in user_marketplaces:
                    marketplaces_by_name[marketplace["name"]] = marketplace
                marketplaces = list(marketplaces_by_name.values())

        return cls(
            exclude_symlinks=exclude_symlinks,
            settings_overrides=settings_overrides,
            mcp_overrides=mcp_overrides,
            profile_name=profile_name,
            plugins=plugins,
            marketplaces=marketplaces,
        )

    def is_excluded(self, symlink_target: str) -> bool:
        """Check if a symlink target is globally excluded.

        Supports both exact paths and glob patterns (e.g., ~/.claude/*.json).
        """
        normalized = Path(symlink_target).expanduser().as_posix()
        for excl in self.exclude_symlinks:
            excl_normalized = Path(excl).expanduser().as_posix()
            if normalized == excl_normalized:
                return True
            if fnmatch(normalized, excl_normalized):
                return True
        return False

    @staticmethod
    def get_cache_dir() -> Path:
        """Get the cache directory for merged settings."""
        from ai_rules.state import get_state_dir

        cache_dir = get_state_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def merge_settings(
        self, agent: str, base_settings: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge base settings with overrides for a specific agent.

        Args:
            agent: Agent name (e.g., 'claude', 'goose')
            base_settings: Base settings dictionary from repo

        Returns:
            Merged settings dictionary with overrides applied
        """
        if agent not in self.settings_overrides:
            return base_settings

        return deep_merge(base_settings, self.settings_overrides[agent])

    def get_merged_settings_path(
        self, agent: str, config_file_name: str, *, force: bool = False
    ) -> Path | None:
        """Get the path to cached merged settings for an agent.

        Returns None if agent has no overrides and force is False.

        Args:
            agent: Agent name (e.g., 'claude', 'goose')
            config_file_name: Config file name (e.g., 'settings.json')
            force: Return cache path even without overrides (for preserved_fields)

        Returns:
            Path to cached merged settings file, or None
        """
        if not force and agent not in self.settings_overrides:
            return None

        cache_dir = self.get_cache_dir() / agent
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / config_file_name

    def get_settings_file_for_symlink(
        self, agent: str, base_settings_path: Path, *, force: bool = False
    ) -> Path:
        """Get the appropriate settings file to use for symlinking.

        Returns cached merged settings if overrides or force is set and cache
        exists, otherwise returns the base settings file.

        This method does NOT build the cache - use build_merged_settings for that.

        Args:
            agent: Agent name (e.g., 'claude', 'goose')
            base_settings_path: Path to base settings file
            force: Use cache even without overrides (for preserved_fields)

        Returns:
            Path to settings file to use (either cached or base)
        """
        if not force and agent not in self.settings_overrides:
            return base_settings_path

        cache_path = self.get_merged_settings_path(
            agent, base_settings_path.name, force=force
        )
        if cache_path and cache_path.exists():
            return cache_path

        return base_settings_path

    @staticmethod
    def load_user_config() -> dict[str, Any]:
        """Load user config file with defaults.

        Returns:
            Dictionary with user config data, or empty dict with version if file doesn't exist
        """
        user_config_path = get_user_config_path()

        if user_config_path.exists():
            with open(user_config_path) as f:
                return yaml.safe_load(f) or {"version": 1}
        return {"version": 1}

    @staticmethod
    def save_user_config(data: dict[str, Any]) -> None:
        """Save user config file with consistent formatting.

        Args:
            data: Configuration dictionary to save
        """
        user_config_path = get_user_config_path()
        user_config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(user_config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def cleanup_orphaned_cache(self, agents_needing_cache: set[str]) -> list[str]:
        """Remove cache files for agents that no longer need them.

        Args:
            agents_needing_cache: Set of agent IDs that need caches (overrides
                or preserved_fields). Callers must compute this via Agent.needs_cache.

        Returns:
            List of agent IDs whose caches were removed
        """
        removed: list[str] = []
        cache_dir = self.get_cache_dir()
        if not cache_dir.exists():
            return removed

        for agent_dir in cache_dir.iterdir():
            if agent_dir.is_dir():
                agent_id = agent_dir.name
                if agent_id not in agents_needing_cache:
                    shutil.rmtree(agent_dir)
                    removed.append(agent_id)

        return removed
