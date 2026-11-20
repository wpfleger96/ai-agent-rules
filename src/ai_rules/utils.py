"""Shared utility functions."""

import copy
import os

from pathlib import Path
from typing import Any

# Python package directory; older installs live under .../site-packages/ai_rules.
PACKAGE_DIR = "ai_rules"

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


def links_to_source(link: Path, source: Path) -> bool:
    """Check if ``link`` is the symlink ai-rules creates for ``source``.

    Ownership is decided from the link's raw target. The directory parts of
    both the target (relative to the directory the link actually lives in) and
    ``source`` are resolved physically, so a ``..`` after a symlinked
    component (e.g. a symlinked HOME) climbs the real tree rather than the
    spelled one. Final names stay lexical, so a source entry that is itself a
    symlink is matched by its own name rather than by whatever it points to.
    The target must be ``source`` itself or the same entry inside an older
    package install, i.e. a path ending in the same ``ai_rules/...``
    components (a previous Python version's site-packages). Anything else,
    including a link the user replaced or one into an unrelated folder, is not
    ours.

    Args:
        link: The symlink to classify (may be dangling)
        source: The source entry ai-rules links to at this location
    """
    from ai_rules.symlinks import read_link  # symlinks -> cli -> utils cycle

    link = link.expanduser().absolute()
    try:
        raw = Path(read_link(link))
        link_dir = link.parent.resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    source = source.expanduser().absolute()
    if raw.name != source.name:
        return False
    expected = Path(os.path.realpath(source.parent)) / source.name
    target = Path(os.path.realpath(link_dir / raw.parent)) / raw.name
    if target.parent == expected.parent:
        return True
    package_at = [i for i, part in enumerate(expected.parts) if part == PACKAGE_DIR]
    if not package_at:
        return False
    tail = expected.parts[package_at[-1] :]
    return target.parts[-len(tail) :] == tail
