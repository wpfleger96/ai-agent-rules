"""Static config target registry."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from ai_rules.agents.amp import AmpAgent
from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.codex import CodexAgent
from ai_rules.agents.gemini import GeminiAgent
from ai_rules.agents.goose import GooseAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.config import Config
from ai_rules.targets.base import ConfigTarget
from ai_rules.tools.statusline import StatuslineTool

TargetClass: TypeAlias = type[ConfigTarget]

TARGET_CLASSES: tuple[TargetClass, ...] = (
    AmpAgent,
    ClaudeAgent,
    CodexAgent,
    GeminiAgent,
    GooseAgent,
    SharedAgent,
    StatuslineTool,
)


def get_targets(config_dir: Path, config: Config) -> list[ConfigTarget]:
    """Instantiate all configured targets in lifecycle order."""
    return [target_class(config_dir, config) for target_class in TARGET_CLASSES]


def get_target_ids(config_dir: Path, config: Config) -> list[str]:
    """Return target IDs in registry order."""
    return [target.target_id for target in get_targets(config_dir, config)]
