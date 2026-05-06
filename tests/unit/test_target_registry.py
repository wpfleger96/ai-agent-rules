from pathlib import Path

import pytest

from ai_rules.config import Config
from ai_rules.targets.registry import TARGET_CLASSES, get_target_ids, get_targets


@pytest.mark.unit
def test_target_registry_returns_targets_in_lifecycle_order(tmp_path: Path) -> None:
    config = Config()

    targets = get_targets(tmp_path, config)

    assert [target.target_id for target in targets] == [
        "amp",
        "claude",
        "codex",
        "gemini",
        "goose",
        "shared",
        "statusline",
    ]


@pytest.mark.unit
def test_get_target_ids_matches_registry_order(tmp_path: Path) -> None:
    config = Config()

    assert get_target_ids(tmp_path, config) == [
        "amp",
        "claude",
        "codex",
        "gemini",
        "goose",
        "shared",
        "statusline",
    ]


@pytest.mark.unit
def test_target_registry_has_unique_target_ids(tmp_path: Path) -> None:
    config = Config()

    target_ids = [target.target_id for target in get_targets(tmp_path, config)]

    assert len(target_ids) == len(set(target_ids))
    assert len(TARGET_CLASSES) == len(target_ids)
