"""Orphaned settings cache cleanup, driven through the install runner."""

from __future__ import annotations

import os
import stat
import sys

from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from rich.console import Console

from ai_rules.cli.components.orphaned_cache import OrphanedCacheComponent
from ai_rules.cli.context import CliContext
from ai_rules.cli.runner import ComponentRunResult, run_install_parallel
from ai_rules.config import Config


class FakeTarget:
    def __init__(
        self,
        target_id: str,
        *,
        needs_cache: bool = False,
        excluded: bool = False,
        links: tuple[tuple[Path, Path], ...] = (),
        settings_link: Path | None = None,
    ):
        self.target_id = target_id
        self.needs_cache = needs_cache
        self.is_settings_file_excluded = excluded
        self.symlinks = list(links)
        self.settings_symlink_target = settings_link

    def get_filtered_symlinks(self) -> list[tuple[Path, Path]]:
        return self.symlinks


def _make_context(
    tmp_path: Path,
    *,
    all_targets: tuple[Any, ...] = (),
    selected_targets: tuple[Any, ...] | None = None,
    config: Config | None = None,
    component_filter: tuple[str, ...] | None = None,
    dry_run: bool = False,
) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=config or Config(),
        profile_name=None,
        all_targets=all_targets,
        selected_targets=(
            all_targets if selected_targets is None else selected_targets
        ),
        component_filter=component_filter,
        yes=True,
        dry_run=dry_run,
    )


def _install(ctx: CliContext) -> ComponentRunResult:
    return run_install_parallel([], [OrphanedCacheComponent()], ctx)


def _make_cache_dirs(home: Path, *agent_ids: str) -> dict[str, Path]:
    dirs = {}
    for agent_id in agent_ids:
        cache_dir = home / ".ai-agent-rules" / "cache" / agent_id
        cache_dir.mkdir(parents=True)
        (cache_dir / "settings.json").write_text("{}")
        dirs[agent_id] = cache_dir
    return dirs


def _link_into(home: Path, cache_dir: Path) -> Path:
    link = home / ".tool" / "settings.json"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(cache_dir / "settings.json")
    return link


@pytest.mark.unit
def test_orphan_only_install_removes_orphaned_cache_and_keeps_needed(
    tmp_path: Path, mock_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dirs = _make_cache_dirs(mock_home, "claude", "shared", "old-agent")
    ctx = _make_context(
        tmp_path,
        config=Config(agents_md="# Rules"),
        all_targets=(FakeTarget("claude", needs_cache=True),),
    )

    result = _install(ctx)

    assert result.ok is True
    assert result.counts == {"removed": 1}
    assert "Removed orphaned cache: old-agent" in capsys.readouterr().out
    assert not dirs["old-agent"].exists()
    assert dirs["claude"].exists()
    assert dirs["shared"].exists()


@pytest.mark.unit
def test_orphan_only_dry_run_reports_same_removals_without_deleting(
    tmp_path: Path, mock_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dirs = _make_cache_dirs(mock_home, "claude", "shared", "old-agent")
    ctx = _make_context(
        tmp_path,
        config=Config(agents_md="# Rules"),
        all_targets=(FakeTarget("claude", needs_cache=True),),
        dry_run=True,
    )

    result = _install(ctx)

    assert result.counts == {"removed": 1}
    output = capsys.readouterr().out
    assert "Would remove orphaned cache: old-agent" in output
    assert "orphaned cache: claude" not in output
    assert "orphaned cache: shared" not in output
    assert all(cache_dir.exists() for cache_dir in dirs.values())


@pytest.mark.unit
def test_install_without_orphans_leaves_needed_caches_untouched(
    tmp_path: Path, mock_home: Path
) -> None:
    dirs = _make_cache_dirs(mock_home, "claude", "shared")
    ctx = _make_context(
        tmp_path,
        config=Config(agents_md="# Rules"),
        all_targets=(FakeTarget("claude", needs_cache=True),),
    )

    result = _install(ctx)

    assert result.ok is True
    assert "removed" not in result.counts
    assert all(cache_dir.exists() for cache_dir in dirs.values())


@pytest.mark.unit
def test_cache_cleanup_uses_all_targets_not_selected_subset(
    tmp_path: Path, mock_home: Path
) -> None:
    dirs = _make_cache_dirs(mock_home, "claude", "codex", "old-agent")
    claude = FakeTarget("claude", needs_cache=True)
    ctx = _make_context(
        tmp_path,
        all_targets=(claude, FakeTarget("codex", needs_cache=True)),
        selected_targets=(claude,),
    )

    result = _install(ctx)

    assert result.counts == {"removed": 1}
    assert dirs["claude"].exists()
    assert dirs["codex"].exists()
    assert not dirs["old-agent"].exists()


@pytest.mark.unit
def test_excluded_settings_file_keeps_its_cache(
    tmp_path: Path, mock_home: Path
) -> None:
    dirs = _make_cache_dirs(mock_home, "claude")
    ctx = _make_context(tmp_path, all_targets=(FakeTarget("claude", excluded=True),))

    result = _install(ctx)

    assert "removed" not in result.counts
    assert dirs["claude"].exists()


@pytest.mark.unit
def test_linked_cache_root_deletes_nothing(tmp_path: Path, mock_home: Path) -> None:
    elsewhere = tmp_path / "dotfiles"
    (elsewhere / "Documents").mkdir(parents=True)
    (elsewhere / "Documents" / "notes.txt").write_text("mine")
    state_dir = mock_home / ".ai-agent-rules"
    state_dir.mkdir()
    (state_dir / "cache").symlink_to(elsewhere, target_is_directory=True)

    result = _install(_make_context(tmp_path))

    assert "removed" not in result.counts
    assert (elsewhere / "Documents" / "notes.txt").read_text() == "mine"


@pytest.mark.unit
@pytest.mark.parametrize("dry_run", [False, True])
def test_link_not_repointed_this_run_keeps_its_cache(
    tmp_path: Path, mock_home: Path, dry_run: bool
) -> None:
    dirs = _make_cache_dirs(mock_home, "statusline")
    link = _link_into(mock_home, dirs["statusline"])
    statusline = FakeTarget("statusline", links=((link, tmp_path / "bundled"),))
    ctx = _make_context(
        tmp_path,
        all_targets=(statusline, FakeTarget("shared")),
        selected_targets=(FakeTarget("shared"),),
        dry_run=dry_run,
    )

    result = _install(ctx)

    assert "removed" not in result.counts
    assert dirs["statusline"].exists()
    assert link.exists()


@pytest.mark.unit
def test_only_filter_without_config_keeps_cache_of_selected_link(
    tmp_path: Path, mock_home: Path
) -> None:
    dirs = _make_cache_dirs(mock_home, "shared")
    link = _link_into(mock_home, dirs["shared"])
    shared = FakeTarget("shared", links=((link, tmp_path / "AGENTS.md"),))
    ctx = _make_context(
        tmp_path, all_targets=(shared,), component_filter=("settings", "agents-md")
    )

    result = _install(ctx)

    assert "removed" not in result.counts
    assert link.exists()


@pytest.mark.unit
def test_link_left_in_cache_after_repoint_keeps_cache_with_warning(
    tmp_path: Path, mock_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A selected link Config Files did not manage to re-point keeps its cache."""
    dirs = _make_cache_dirs(mock_home, "statusline")
    link = _link_into(mock_home, dirs["statusline"])
    statusline = FakeTarget("statusline", links=((link, tmp_path / "bundled"),))
    ctx = _make_context(tmp_path, all_targets=(statusline,))

    result = _install(ctx)

    assert result.counts == {"removed": 0}
    assert "Kept orphaned cache statusline" in capsys.readouterr().out
    assert link.exists()


@pytest.mark.unit
@pytest.mark.parametrize("dry_run", [False, True])
def test_settings_link_keeps_cache_when_bundled_file_is_gone(
    tmp_path: Path, mock_home: Path, dry_run: bool
) -> None:
    """Without a bundled settings file the link leaves symlinks but still counts."""
    dirs = _make_cache_dirs(mock_home, "statusline")
    link = _link_into(mock_home, dirs["statusline"])
    ctx = _make_context(
        tmp_path,
        all_targets=(FakeTarget("statusline", settings_link=link),),
        dry_run=dry_run,
    )

    result = _install(ctx)

    assert "removed" not in result.counts
    assert dirs["statusline"].exists()
    assert link.exists()


@pytest.mark.unit
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
@pytest.mark.skipif(
    sys.platform != "win32" and os.geteuid() == 0, reason="root ignores modes"
)
def test_unlistable_cache_dir_shows_no_pending_removals(
    tmp_path: Path, mock_home: Path
) -> None:
    from ai_rules.cli import _display_pending_changes

    _make_cache_dirs(mock_home, "old-agent")
    cache_root = mock_home / ".ai-agent-rules" / "cache"
    # Traversable but not listable.
    cache_root.chmod(stat.S_IWUSR | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    try:
        shown = _display_pending_changes(_make_context(tmp_path))
    finally:
        cache_root.chmod(stat.S_IRWXU)

    assert shown is False
    assert (cache_root / "old-agent").is_dir()
