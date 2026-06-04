"""Sprout persona pack symlink tool."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from ai_rules.platform import (
    SPROUT_PACK_ID,
    Platform,
    get_sprout_packs_dir,
    is_platform,
)
from ai_rules.tools.base import Tool


class SproutTool(Tool):
    """Manages Sprout persona pack symlinks into production and dev data directories."""

    name = "Sprout"
    tool_id = "sprout"
    config_file_name = ""
    config_file_format = ""

    @property
    def needs_cache(self) -> bool:
        return False

    @cached_property
    def symlinks(self) -> list[tuple[Path, Path]]:
        if not is_platform(Platform.MACOS):
            return []
        source = self.config_dir / "sprout"
        if not source.exists():
            return []
        return [
            (get_sprout_packs_dir(dev=False) / SPROUT_PACK_ID, source),
            (get_sprout_packs_dir(dev=True) / SPROUT_PACK_ID, source),
        ]
