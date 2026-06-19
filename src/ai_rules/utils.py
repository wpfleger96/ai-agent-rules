"""Shared utility functions."""

import copy

from pathlib import Path
from typing import Any

# Substrings that identify a symlink target as belonging to this package,
# regardless of which Python version's site-packages path it resolves under.
PACKAGE_MARKERS: tuple[str, ...] = (
    "ai_rules/config",
    "ai-agent-rules",
    "ai-rules",
)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override values taking precedence.

    Nested dicts are merged recursively. Lists are replaced wholesale by the
    override value (not merged element-by-element).

    Uses deep copy to prevent mutation of either input dictionary.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key not in result:
            result[key] = copy.deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def is_managed_target(target_path: Path, config_dir: Path) -> bool:
    """Check if a symlink target points to ai-rules managed location.

    Args:
        target_path: Path that symlink points to (resolved or raw readlink result)
        config_dir: ai-rules config directory

    Returns:
        True if target is under the config directory or contains package-identifying markers
    """
    try:
        target_resolved = target_path.resolve()
        config_resolved = config_dir.resolve()
        if target_resolved.is_relative_to(config_resolved):
            return True
    except (ValueError, OSError, RuntimeError):
        pass

    # Fallback: check raw path string for package markers. Catches symlinks
    # pointing to a previous Python version's site-packages path.
    target_str = str(target_path)
    return any(marker in target_str for marker in PACKAGE_MARKERS)
