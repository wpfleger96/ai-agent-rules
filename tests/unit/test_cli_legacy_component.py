from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

import ai_rules.cli

from ai_rules.cli.components.legacy import LegacyMigrationComponent
from ai_rules.cli.context import CliContext
from ai_rules.config import Config


class FailingSymlink:
    def __str__(self) -> str:
        return "/tmp/legacy-symlink"

    def unlink(self) -> None:
        raise OSError("permission denied")


def make_context(tmp_path: Path) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=(),
        selected_targets=(),
    )


@pytest.mark.unit
def test_legacy_migration_unlink_errors_fail_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        ai_rules.cli,
        "detect_old_config_symlinks",
        lambda: [(FailingSymlink(), Path("/old/config"))],
    )

    result = LegacyMigrationComponent().install(make_context(tmp_path))

    assert result.ok is False
    assert result.counts == {"removed": 0, "errors": 1}
