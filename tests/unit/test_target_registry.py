from pathlib import Path

import pytest

from ai_rules.config import Config
from ai_rules.targets.registry import TARGET_CLASSES, get_targets


@pytest.mark.unit
def test_target_registry_returns_unique_targets_in_lifecycle_order(
    tmp_path: Path,
) -> None:
    config = Config()

    target_ids = [target.target_id for target in get_targets(tmp_path, config)]

    assert target_ids == [
        "amp",
        "claude",
        "codex",
        "gemini",
        "goose",
        "shared",
        "statusline",
    ]
    assert len(target_ids) == len(set(target_ids))
    assert len(TARGET_CLASSES) == len(target_ids)
