"""Shared utility functions."""

import copy

from pathlib import Path
from typing import Any


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override values taking precedence.

    Nested dicts are merged recursively. Lists are replaced wholesale by the
    override value (not merged element-by-element).

    Uses deep copy to prevent mutation of the base dictionary.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def is_managed_target(target_path: Path, config_dir: Path) -> bool:
    """Check if a symlink target points to ai-rules managed location.

    Args:
        target_path: Path that symlink points to
        config_dir: ai-rules config directory

    Returns:
        True if target is under the config directory
    """
    try:
        target_resolved = target_path.resolve()
        config_resolved = config_dir.resolve()
        return target_resolved.is_relative_to(config_resolved)
    except (ValueError, OSError, RuntimeError):
        return False
