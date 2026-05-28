"""Tests for OrphanSweepComponent."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

import ai_rules.cli.components.orphan_sweep as orphan_sweep_mod

from ai_rules.cli.components.orphan_sweep import OrphanSweepComponent
from ai_rules.cli.context import CliContext
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
class TestOrphanSweepInstall:
    def test_removes_dangling_managed_symlink(self, tmp_path, monkeypatch):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        ctx = make_context(tmp_path)
        dangling_target = ctx.config_dir / "hooks" / "old_hook.py"  # does not exist
        symlink = hooks_dir / "old_hook.py"
        symlink.symlink_to(dangling_target)

        monkeypatch.setattr(orphan_sweep_mod, "_FILE_DIRS", [(hooks_dir, "*.py")])

        OrphanSweepComponent().install(ctx)

        assert not symlink.exists()
        assert not symlink.is_symlink()

    def test_leaves_live_managed_symlink_alone(self, tmp_path, monkeypatch):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        ctx = make_context(tmp_path)
        live_target = ctx.config_dir / "hooks" / "active_hook.py"
        live_target.parent.mkdir(parents=True, exist_ok=True)
        live_target.write_text("# hook")

        symlink = hooks_dir / "active_hook.py"
        symlink.symlink_to(live_target)

        monkeypatch.setattr(orphan_sweep_mod, "_FILE_DIRS", [(hooks_dir, "*.py")])

        OrphanSweepComponent().install(ctx)

        assert symlink.is_symlink()

    def test_leaves_unmanaged_dangling_symlink_alone(self, tmp_path, monkeypatch):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        ctx = make_context(tmp_path)
        unmanaged_target = tmp_path / "some-other-tool" / "hook.py"  # does not exist
        symlink = hooks_dir / "hook.py"
        symlink.symlink_to(unmanaged_target)

        monkeypatch.setattr(orphan_sweep_mod, "_FILE_DIRS", [(hooks_dir, "*.py")])

        OrphanSweepComponent().install(ctx)

        assert symlink.is_symlink()

    def test_dry_run_does_not_remove_symlink(self, tmp_path, monkeypatch):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        ctx = make_context(tmp_path, dry_run=True)
        dangling_target = ctx.config_dir / "hooks" / "old_hook.py"
        symlink = hooks_dir / "old_hook.py"
        symlink.symlink_to(dangling_target)

        monkeypatch.setattr(orphan_sweep_mod, "_FILE_DIRS", [(hooks_dir, "*.py")])

        OrphanSweepComponent().install(ctx)

        assert symlink.is_symlink()


@pytest.mark.unit
class TestOrphanSweepStatus:
    def test_reports_orphaned_symlinks(self, tmp_path, monkeypatch):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        ctx = make_context(tmp_path)
        dangling_target = ctx.config_dir / "hooks" / "old_hook.py"
        symlink = hooks_dir / "old_hook.py"
        symlink.symlink_to(dangling_target)

        monkeypatch.setattr(orphan_sweep_mod, "_FILE_DIRS", [(hooks_dir, "*.py")])

        result = OrphanSweepComponent().status(ctx)

        assert result.ok is False

    def test_returns_clean_when_no_orphans(self, tmp_path, monkeypatch):
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        ctx = make_context(tmp_path)

        monkeypatch.setattr(orphan_sweep_mod, "_FILE_DIRS", [(hooks_dir, "*.py")])

        result = OrphanSweepComponent().status(ctx)

        assert result.ok is True
