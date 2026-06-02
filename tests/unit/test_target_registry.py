from pathlib import Path

import pytest

from ai_rules.agents.amp import AmpAgent
from ai_rules.config import Config
from ai_rules.targets.registry import TARGET_CLASSES, get_targets


@pytest.mark.unit
def test_target_registry_returns_unique_targets_in_lifecycle_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
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


@pytest.mark.unit
def test_get_targets_excludes_amp_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
    config = Config()

    targets = get_targets(tmp_path, config)
    target_classes = [type(t) for t in targets]

    assert AmpAgent not in target_classes
