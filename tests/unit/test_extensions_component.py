"""Tests for ClaudeExtensionsComponent orphan cleanup in plan/apply."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

from ai_rules.cli.components.extensions import ClaudeExtensionsComponent
from ai_rules.cli.context import ClaudeExtensionsPlan, CliContext
from ai_rules.config import Config


def make_context(tmp_path: Path, *, dry_run: bool = False) -> CliContext:
    # config_dir contains "ai-agent-rules" so is_managed_target() recognizes
    # symlinks pointing into it as managed via the string-marker fallback.
    config_dir = (
        tmp_path
        / "uv"
        / "tools"
        / "ai-agent-rules"
        / "lib"
        / "python3.14"
        / "site-packages"
        / "ai_rules"
        / "config"
    )
    config_dir.mkdir(parents=True)
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=config_dir,
        config=Config(),
        profile_name=None,
        all_targets=(),
        selected_targets=(),
        dry_run=dry_run,
    )


@pytest.mark.unit
class TestClaudeExtensionsApplyOrphanCleanup:
    def test_apply_removes_orphaned_extension(self, tmp_path):
        ctx = make_context(tmp_path)
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        dangling_target = ctx.config_dir / "commands" / "old-cmd.md"
        symlink = commands_dir / "old-cmd.md"
        symlink.symlink_to(dangling_target)

        plan = ClaudeExtensionsPlan(
            has_changes=True,
            cleanup_ops=[("commands", "old-cmd", symlink)],
        )

        result = ClaudeExtensionsComponent().apply(ctx, plan)

        assert not symlink.exists()
        assert not symlink.is_symlink()
        assert result.counts.get("cleaned", 0) == 1

    def test_apply_dry_run_does_not_remove_orphan(self, tmp_path):
        ctx = make_context(tmp_path, dry_run=True)
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        dangling_target = ctx.config_dir / "commands" / "old-cmd.md"
        symlink = commands_dir / "old-cmd.md"
        symlink.symlink_to(dangling_target)

        plan = ClaudeExtensionsPlan(
            has_changes=True,
            cleanup_ops=[("commands", "old-cmd", symlink)],
        )

        ClaudeExtensionsComponent().apply(ctx, plan)

        assert symlink.is_symlink()
