"""Buzz persona pack symlink tool."""

from __future__ import annotations

import json

from functools import cached_property
from pathlib import Path

from ai_rules.platform import (
    Platform,
    get_buzz_teams_dir,
    get_legacy_sprout_teams_dir,
    is_platform,
)
from ai_rules.tools.base import Tool


class BuzzTool(Tool):
    """Manages Buzz persona pack symlinks into production and dev data directories."""

    name = "Buzz"
    tool_id = "buzz"
    config_file_name = ""
    config_file_format = ""

    @classmethod
    def is_supported_on_current_platform(cls) -> bool:
        from ai_rules.platform import Platform, is_platform

        return is_platform(Platform.MACOS)

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
        except json.JSONDecodeError, OSError:
            return None

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        if not is_platform(Platform.MACOS):
            return []
        source = self.config_dir / "buzz"
        if not source.exists():
            return []
        pack_id = self._read_pack_id()
        if not pack_id:
            return []
        return [
            (get_buzz_teams_dir(dev=False) / pack_id, source),
            (get_buzz_teams_dir(dev=True) / pack_id, source),
            # Legacy Sprout paths — remove once upstream desktop rename is fully shipped
            (get_legacy_sprout_teams_dir(dev=False) / pack_id, source),
            (get_legacy_sprout_teams_dir(dev=True) / pack_id, source),
        ]
