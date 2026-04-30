"""Base config target class."""

from __future__ import annotations

import copy
import json

from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Any

from ai_rules.config import Config


class ConfigTarget(ABC):
    """Base class for config pipeline targets."""

    def __init__(self, config_dir: Path, config: Config):
        self.config_dir = config_dir
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the target."""
        pass

    @property
    @abstractmethod
    def target_id(self) -> str:
        """Short identifier for the target (e.g., 'claude', 'goose')."""
        pass

    @property
    @abstractmethod
    def config_file_name(self) -> str:
        """Config file name for the target (e.g., 'settings.json', 'config.yaml')."""
        pass

    @property
    @abstractmethod
    def config_file_format(self) -> str:
        """Config file format ('json', 'yaml', or 'toml')."""
        pass

    @property
    def preserved_fields(self) -> list[str]:
        """Fields in the target's config file managed by the tool itself.

        These are preserved across ai-rules installs and excluded from
        staleness diffs. Override in subclasses for target-specific fields.
        """
        return []

    @property
    def _effective_preserved_fields(self) -> list[str]:
        """All fields that should be preserved across cache rebuilds.

        Includes static preserved_fields plus any dynamically derived fields.
        Override in subclasses (e.g. Agent) to extend with additional keys.
        """
        return self.preserved_fields

    @property
    def needs_cache(self) -> bool:
        """Whether this target needs a cache file (has overrides or preserved fields)."""
        return self.target_id in self.config.settings_overrides or bool(
            self._effective_preserved_fields
        )

    @cached_property
    @abstractmethod
    def symlinks(self) -> list[tuple[Path, Path]]:
        """Cached list of (target_path, source_path) tuples for symlinks.

        Returns:
            List of tuples where:
            - target_path: Where symlink should be created (e.g., ~/.CLAUDE.md)
            - source_path: What symlink should point to (e.g., repo/config/AGENTS.md)
        """
        pass

    def _merge_managed_mcps(self, merged: dict[str, Any]) -> None:  # noqa: B027
        """Hook for subclasses to merge managed MCPs into the settings cache.

        Called during build_merged_settings() after preserved_fields are applied.
        Override in Agent to reconcile managed MCP entries.
        """

    # --- settings cache methods -------------------------------------------

    @property
    def _base_settings_path(self) -> Path:
        """Path to the base settings file in the config directory."""
        return self.config_dir / self.target_id / self.config_file_name

    def build_merged_settings(
        self,
        force_rebuild: bool = False,
    ) -> Path | None:
        """Build merged settings file in cache if overrides exist.

        Only rebuilds cache if:
        - force_rebuild is True, OR
        - Cache doesn't exist or is stale

        Returns:
            Path to merged settings file, or None if no overrides exist
        """
        from ai_rules.config import (
            CONFIG_PARSE_ERRORS,
            ManagedFieldsTracker,
            dump_config_file,
            load_config_file,
        )

        if not self.needs_cache:
            return None

        cache_path = self.config.get_merged_settings_path(
            self.target_id, self.config_file_name, force=True
        )

        if not force_rebuild and cache_path and cache_path.exists():
            if not self.is_cache_stale():
                return cache_path

        base_settings_path = self._base_settings_path
        config_format = self.config_file_format

        if not base_settings_path.exists():
            base_settings: dict[str, Any] = {}
        else:
            try:
                base_settings = load_config_file(base_settings_path, config_format)
            except CONFIG_PARSE_ERRORS:
                return None

        merged = self.config.merge_settings(self.target_id, base_settings)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            preserved = self._effective_preserved_fields

            # JSON targets: use ManagedFieldsTracker for granular cleanup on
            # profile switch (e.g. removing stale hook entries)
            tracker = ManagedFieldsTracker() if config_format == "json" else None

            if cache_path.exists() and preserved:
                try:
                    existing = load_config_file(cache_path, config_format)

                    if tracker:
                        existing = tracker.cleanup_stale_entries(
                            existing, merged, preserved
                        )

                    for field in preserved:
                        if field in existing:
                            merged[field] = existing[field]
                except CONFIG_PARSE_ERRORS:
                    pass

            self._merge_managed_mcps(merged)

            if tracker and preserved:
                for field in preserved:
                    merged_value = merged.get(field)
                    if merged_value:
                        tracker.set_field_contributions(field, merged_value)
                    else:
                        tracker.set_field_contributions(field, None)
                tracker.save()

            try:
                dump_config_file(cache_path, merged, config_format)
            except ValueError as exc:
                import logging

                logging.getLogger(__name__).error("%s: %s", self.name, exc)
                raise

        return cache_path

    def is_cache_stale(self) -> bool:
        """Check if cached merged settings are stale.

        Returns:
            True if cache needs rebuilding, False otherwise
        """
        if not self.needs_cache:
            return False

        cache_path = self.config.get_merged_settings_path(
            self.target_id, self.config_file_name, force=True
        )
        if not cache_path or not cache_path.exists():
            return True

        cache_mtime = cache_path.stat().st_mtime

        base_settings_path = self._base_settings_path
        if base_settings_path.exists():
            if base_settings_path.stat().st_mtime > cache_mtime:
                return True

        from ai_rules.config import get_user_config_path

        user_config_path = get_user_config_path()
        if user_config_path.exists():
            if user_config_path.stat().st_mtime > cache_mtime:
                return True

        if self.config.profile_name and self.config.profile_name != "default":
            from ai_rules.profiles import ProfileLoader

            loader = ProfileLoader()
            profile_path = loader._profiles_dir / f"{self.config.profile_name}.yaml"
            if profile_path.exists() and profile_path.stat().st_mtime > cache_mtime:
                return True

        return self.get_cache_diff() is not None

    def get_cache_diff(self) -> str | None:
        """Get unified diff between current state and expected merged settings.

        Returns:
            Formatted diff string with Rich markup, or None if no diff
        """
        import difflib

        import tomli_w
        import yaml

        from ai_rules.config import CONFIG_PARSE_ERRORS, load_config_file

        if not self.needs_cache:
            return None

        config_format = self.config_file_format
        base_settings_path = self._base_settings_path

        if not base_settings_path.exists():
            base_settings: dict[str, Any] = {}
        else:
            try:
                base_settings = load_config_file(base_settings_path, config_format)
            except CONFIG_PARSE_ERRORS:
                return None

        cache_path = self.config.get_merged_settings_path(
            self.target_id, self.config_file_name, force=True
        )
        cache_exists = cache_path and cache_path.exists()

        if cache_exists:
            assert cache_path is not None
            try:
                current_settings = load_config_file(cache_path, config_format)
            except CONFIG_PARSE_ERRORS:
                return None
            from_label = "Cached (current)"
            to_label = "Expected (merged)"
        else:
            current_settings = base_settings
            from_label = "Base (current)"
            to_label = "Expected (with overrides)"

        expected_settings = self.config.merge_settings(self.target_id, base_settings)

        current_copy = copy.deepcopy(current_settings)
        expected_copy = copy.deepcopy(expected_settings)
        for field in self._effective_preserved_fields:
            current_copy.pop(field, None)
            expected_copy.pop(field, None)

        if current_copy == expected_copy:
            return None

        if config_format == "json":
            current_text = json.dumps(current_copy, indent=2)
            expected_text = json.dumps(expected_copy, indent=2)
        elif config_format == "yaml":
            current_text = yaml.dump(
                current_copy, default_flow_style=False, sort_keys=False
            )
            expected_text = yaml.dump(
                expected_copy, default_flow_style=False, sort_keys=False
            )
        elif config_format == "toml":
            from ai_rules.config import _validate_for_format

            try:
                _validate_for_format(current_copy, "toml")
                _validate_for_format(expected_copy, "toml")
            except ValueError as exc:
                return f"[red]Config contains invalid values:[/red] {exc}"
            current_text = tomli_w.dumps(current_copy)
            expected_text = tomli_w.dumps(expected_copy)
        else:
            return None

        current_lines = current_text.splitlines(keepends=True)
        expected_lines = expected_text.splitlines(keepends=True)

        diff = difflib.unified_diff(
            current_lines,
            expected_lines,
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )

        diff_lines = []
        for line in diff:
            line = line.rstrip("\n")
            if (
                line.startswith("---")
                or line.startswith("+++")
                or line.startswith("@@")
            ):
                diff_lines.append(f"[dim]    {line}[/dim]")
            elif line.startswith("+"):
                diff_lines.append(f"[green]    {line}[/green]")
            elif line.startswith("-"):
                diff_lines.append(f"[red]    {line}[/red]")
            else:
                diff_lines.append(f"[dim]    {line}[/dim]")

        if not diff_lines:
            return None

        return "\n".join(diff_lines)

    def get_filtered_symlinks(self) -> list[tuple[Path, Path]]:
        """Get symlinks filtered by config exclusions."""
        return [
            (target, source)
            for target, source in self.symlinks
            if not self.config.is_excluded(str(target))
        ]

    def get_deprecated_symlinks(self) -> list[Path]:
        """Get list of deprecated symlink paths that should be cleaned up.

        Returns:
            List of paths that were previously used but are now deprecated.
            These will be removed during install if they point to our config files.
        """
        return []
