"""Profile loading and inheritance resolution."""

from dataclasses import dataclass, field
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any

import yaml

from ai_rules.utils import deep_merge


@dataclass
class Profile:
    """A named collection of configuration overrides."""

    name: str
    description: str = ""
    extends: str | None = None
    settings_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    exclude_symlinks: list[str] = field(default_factory=list)
    mcp_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    plugins: list[dict[str, str]] = field(default_factory=list)
    marketplaces: list[dict[str, str]] = field(default_factory=list)
    managed_tools: dict[str, Any] = field(default_factory=dict)


class ProfileError(Exception):
    """Base exception for profile-related errors."""

    pass


class ProfileNotFoundError(ProfileError):
    """Raised when a profile is not found."""

    pass


class CircularInheritanceError(ProfileError):
    """Raised when circular profile inheritance is detected."""

    pass


class ProfileLoader:
    """Loads and resolves profile inheritance."""

    def __init__(self, profiles_dir: Path | None = None):
        """Initialize profile loader.

        Args:
            profiles_dir: Optional override for profiles directory (for testing)
        """
        if profiles_dir:
            self._profiles_dir = profiles_dir
        else:
            config_resource = resource_files("ai_rules") / "config" / "profiles"
            self._profiles_dir = Path(str(config_resource))

    def list_profiles(self) -> list[str]:
        """List all available profile names."""
        if not self._profiles_dir.exists():
            return ["default"]

        profiles = []
        for path in self._profiles_dir.glob("*.yaml"):
            profiles.append(path.stem)

        if "default" not in profiles:
            profiles.append("default")

        return sorted(profiles)

    def load_profile(self, name: str) -> Profile:
        """Load a profile by name, resolving inheritance.

        Args:
            name: Profile name (without .yaml extension)

        Returns:
            Fully resolved Profile with inherited values merged

        Raises:
            ProfileNotFoundError: If profile doesn't exist
            CircularInheritanceError: If circular inheritance detected
        """
        return self._load_with_inheritance(name, visited=set())

    def _load_with_inheritance(self, name: str, visited: set[str]) -> Profile:
        """Recursively load profile with inheritance chain."""
        if name in visited:
            cycle = " -> ".join(visited) + f" -> {name}"
            raise CircularInheritanceError(
                f"Circular profile inheritance detected: {cycle}"
            )

        visited.add(name)

        profile_path = self._profiles_dir / f"{name}.yaml"

        if not profile_path.exists():
            if name == "default":
                return Profile(
                    name="default", description="Default profile (no overrides)"
                )
            available = self.list_profiles()
            raise ProfileNotFoundError(
                f"Profile '{name}' not found. Available profiles: {', '.join(available)}"
            )

        try:
            with open(profile_path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ProfileError(f"Profile '{name}' has invalid YAML: {e}") from e

        self._validate_profile_data(data, name)

        profile = Profile(
            name=data.get("name", name),
            description=data.get("description", ""),
            extends=data.get("extends"),
            settings_overrides=data.get("settings_overrides", {}),
            exclude_symlinks=data.get("exclude_symlinks", []),
            mcp_overrides=data.get("mcp_overrides", {}),
            plugins=data.get("plugins", []),
            marketplaces=data.get("marketplaces", []),
            managed_tools=data.get("managed_tools", {}),
        )

        if profile.extends:
            parent = self._load_with_inheritance(profile.extends, visited.copy())
            profile = self._merge_profiles(parent, profile)

        return profile

    def _validate_profile_data(self, data: dict[str, Any], profile_name: str) -> None:
        """Validate profile data types."""
        if "settings_overrides" in data and not isinstance(
            data["settings_overrides"], dict
        ):
            raise ProfileError(
                f"Profile '{profile_name}': settings_overrides must be a dict"
            )
        if "exclude_symlinks" in data and not isinstance(
            data["exclude_symlinks"], list
        ):
            raise ProfileError(
                f"Profile '{profile_name}': exclude_symlinks must be a list"
            )
        if "mcp_overrides" in data and not isinstance(data["mcp_overrides"], dict):
            raise ProfileError(
                f"Profile '{profile_name}': mcp_overrides must be a dict"
            )
        if "plugins" in data:
            if not isinstance(data["plugins"], list):
                raise ProfileError(f"Profile '{profile_name}': plugins must be a list")
            for i, plugin in enumerate(data["plugins"]):
                if not isinstance(plugin, dict):
                    raise ProfileError(
                        f"Profile '{profile_name}': plugins[{i}] must be a dict"
                    )
                if "name" not in plugin or "marketplace" not in plugin:
                    raise ProfileError(
                        f"Profile '{profile_name}': plugins[{i}] must have 'name' and 'marketplace' keys"
                    )
        if "marketplaces" in data:
            if not isinstance(data["marketplaces"], list):
                raise ProfileError(
                    f"Profile '{profile_name}': marketplaces must be a list"
                )
            for i, marketplace in enumerate(data["marketplaces"]):
                if not isinstance(marketplace, dict):
                    raise ProfileError(
                        f"Profile '{profile_name}': marketplaces[{i}] must be a dict"
                    )
                if "name" not in marketplace or "source" not in marketplace:
                    raise ProfileError(
                        f"Profile '{profile_name}': marketplaces[{i}] must have 'name' and 'source' keys"
                    )
        if "managed_tools" in data and not isinstance(data["managed_tools"], dict):
            raise ProfileError(
                f"Profile '{profile_name}': managed_tools must be a dict"
            )

    def _merge_profiles(self, parent: Profile, child: Profile) -> Profile:
        """Merge parent profile into child, with child taking precedence."""
        merged_settings = deep_merge(
            parent.settings_overrides, child.settings_overrides
        )

        merged_mcp = deep_merge(parent.mcp_overrides, child.mcp_overrides)

        merged_excludes = list(
            set(parent.exclude_symlinks) | set(child.exclude_symlinks)
        )

        plugins_by_name = {p["name"]: p for p in parent.plugins}
        for plugin in child.plugins:
            plugins_by_name[plugin["name"]] = plugin
        merged_plugins = list(plugins_by_name.values())

        marketplaces_by_name = {m["name"]: m for m in parent.marketplaces}
        for marketplace in child.marketplaces:
            marketplaces_by_name[marketplace["name"]] = marketplace
        merged_marketplaces = list(marketplaces_by_name.values())

        merged_managed_tools = deep_merge(parent.managed_tools, child.managed_tools)

        return Profile(
            name=child.name,
            description=child.description,
            extends=child.extends,
            settings_overrides=merged_settings,
            exclude_symlinks=merged_excludes,
            mcp_overrides=merged_mcp,
            plugins=merged_plugins,
            marketplaces=merged_marketplaces,
            managed_tools=merged_managed_tools,
        )

    def get_profile_info(self, name: str) -> dict[str, Any]:
        """Get profile information without resolving inheritance."""
        profile_path = self._profiles_dir / f"{name}.yaml"
        if not profile_path.exists():
            if name == "default":
                return {
                    "name": "default",
                    "description": "Default profile (no overrides)",
                }
            raise ProfileNotFoundError(f"Profile '{name}' not found")

        try:
            with open(profile_path) as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ProfileError(f"Profile '{name}' has invalid YAML: {e}") from e
