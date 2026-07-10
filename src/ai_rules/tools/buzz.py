"""Buzz persona pack symlink tool."""

from __future__ import annotations

import json
import os

from functools import cached_property
from pathlib import Path

from ai_rules.platform import Platform, get_appdata_dir, get_buzz_teams_dir, is_platform
from ai_rules.tools.base import Tool


# Tombstone — removal-only. These paths were used when the app was named Sprout
# (bundles xyz.block.sprout.app / xyz.block.sprout.app.dev). Pre-rename installs
# have pack symlinks here; we actively remove them on install to clean up stale
# state on existing machines. Do NOT re-add these bundles to platform.py.
def _get_legacy_sprout_teams_dir(dev: bool = False) -> Path:
    bundle = "xyz.block.sprout.app.dev" if dev else "xyz.block.sprout.app"
    if is_platform(Platform.WINDOWS):
        return get_appdata_dir() / bundle / "agents" / "teams"
    if is_platform(Platform.MACOS):
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / bundle
            / "agents"
            / "teams"
        )
    data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(data_home) / bundle / "agents" / "teams"


class BuzzTool(Tool):
    """Manages Buzz persona pack symlinks into production and dev data directories."""

    name = "Buzz"
    tool_id = "buzz"
    config_file_name = ""
    config_file_format = ""

    @property
    def needs_cache(self) -> bool:
        return False

    def _read_pack_id(self) -> str | None:
        manifest = self.config_dir / "buzz" / ".plugin" / "plugin.json"
        if not manifest.is_file():
            return None
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            pack_id = data.get("id")
            return pack_id if isinstance(pack_id, str) and pack_id else None
        except (json.JSONDecodeError, OSError):
            return None

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        source = self.config_dir / "buzz"
        if not source.exists():
            return []
        pack_id = self._read_pack_id()
        if not pack_id:
            return []
        return [
            (get_buzz_teams_dir(dev=False) / pack_id, source),
            (get_buzz_teams_dir(dev=True) / pack_id, source),
        ]

    def get_deprecated_symlinks(self) -> list[Path]:
        """Return legacy Sprout pack symlink paths for cleanup.

        Pre-rename installs have the pack symlinked under the legacy
        xyz.block.sprout.app / xyz.block.sprout.app.dev bundles. These paths
        are removed on install to clean up stale state on existing machines.
        """
        pack_id = self._read_pack_id()
        if not pack_id:
            return []
        return [
            _get_legacy_sprout_teams_dir(dev=False) / pack_id,
            _get_legacy_sprout_teams_dir(dev=True) / pack_id,
        ]
