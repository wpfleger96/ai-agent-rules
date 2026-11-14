"""End-to-end coverage of orphaned settings cache cleanup during install.

A cache dir is orphaned once no target needs it, but a managed link may still
point into it until Config Files re-points that link. These tests pin that
install deletes an orphan only after consent and only when no link it leaves
in place still resolves into it.
"""

from __future__ import annotations

import os
import stat

from pathlib import Path

import pytest

from tests.e2e.helpers import (
    CliResult,
    build_config_dir,
    is_windows,
    make_cli_runner,
    strip_ansi,
)

ONLY = ["--only", "settings,agents-md,config"]


@pytest.fixture
def env(isolated_home, tmp_path):
    """Return ``(home, run, install_args, user_config)`` for a toy config dir."""
    home, home_env = isolated_home
    config = build_config_dir(tmp_path / "rules")
    (config / "statusline").mkdir()
    (config / "statusline" / "config.yaml").write_text("theme: a\n", encoding="utf-8")
    install = ["install", "--skip-completions", "--config-dir", str(config)]
    return (
        home,
        make_cli_runner(home, home_env),
        install,
        home / ".ai-agent-rules-config.yaml",
    )


def _cache(home: Path, name: str) -> Path:
    return home / ".ai-agent-rules" / "cache" / name


def _statusline_link(home: Path) -> Path:
    return next(
        path
        for path in home.rglob("config.yaml")
        # Match the link's own dir: pytest names tmp dirs after the test, so the
        # full path contains "statusline" for every link in the home.
        if path.is_symlink() and path.parent.name == "claude-code-statusline"
    )


def _ok(result: CliResult) -> str:
    out = strip_ansi(result.stdout + result.stderr)
    assert result.returncode == 0, out
    return out


def _summary_line(output: str) -> str:
    return next(line for line in output.splitlines() if line.startswith("Summary:"))


@pytest.mark.e2e
def test_removed_agents_md_cache_is_reported_then_removed(env):
    home, run, install, user_config = env
    user_config.write_text('version: 1\nagents_md: "# Extra"\n', encoding="utf-8")
    _ok(run([*install, *ONLY, "-y"]))
    shared_cache = _cache(home, "shared")
    assert shared_cache.is_dir()
    user_config.write_text("version: 1\n", encoding="utf-8")
    scoped = [*install, *ONLY, "--agents", "shared"]

    dry_out = _ok(run([*scoped, "--dry-run"]))

    assert "Would remove orphaned cache: shared" in dry_out
    assert "remove 1" in _summary_line(dry_out)
    assert shared_cache.is_dir()

    real_out = _ok(run([*scoped, "-y"]))

    assert "Removed orphaned cache: shared" in real_out
    assert "removed 1" in _summary_line(real_out)
    assert not shared_cache.exists()
    assert (home / "AGENTS.md").read_text("utf-8") == "# Shared Agent Rules\n"


@pytest.mark.e2e
def test_removed_statusline_override_repoints_link_then_removes_cache(env):
    home, run, install, user_config = env
    user_config.write_text(
        "version: 1\nsettings_overrides:\n  statusline:\n    theme: b\n",
        encoding="utf-8",
    )
    _ok(run([*install, *ONLY, "-y"]))
    statusline_cache = _cache(home, "statusline")
    assert statusline_cache.is_dir()
    user_config.write_text("version: 1\n", encoding="utf-8")

    _ok(run([*install, *ONLY, "--agents", "statusline", "-y"]))

    assert not statusline_cache.exists()
    assert _statusline_link(home).read_text("utf-8") == "theme: a\n"


@pytest.mark.e2e
@pytest.mark.parametrize(
    "user_config_text,scope,cache_name,link_path",
    [
        pytest.param(
            "version: 1\nsettings_overrides:\n  statusline:\n    theme: b\n",
            [*ONLY, "--agents", "shared"],
            "statusline",
            None,
            id="unselected-statusline",
        ),
        pytest.param(
            'version: 1\nagents_md: "# Extra"\n',
            ["--only", "settings,agents-md", "--agents", "shared"],
            "shared",
            "AGENTS.md",
            id="agents-md-without-config",
        ),
    ],
)
def test_scoped_install_keeps_cache_a_remaining_link_uses(
    env, user_config_text, scope, cache_name, link_path
):
    home, run, install, user_config = env
    user_config.write_text(user_config_text, encoding="utf-8")
    _ok(run([*install, *ONLY, "-y"]))
    user_config.write_text("version: 1\n", encoding="utf-8")
    scoped = [*install, *scope]

    dry_out = _ok(run([*scoped, "--dry-run"]))
    real_out = _ok(run([*scoped, "-y"]))

    link = home / link_path if link_path else _statusline_link(home)
    assert "orphaned cache" not in dry_out
    assert "orphaned cache" not in real_out
    assert _cache(home, cache_name).is_dir()
    assert link.exists()


@pytest.mark.e2e
def test_declining_confirmation_deletes_nothing(env):
    home, run, install, _user_config = env
    _ok(run([*install, *ONLY, "-y"]))
    retired = _cache(home, "retired")
    retired.mkdir(parents=True)

    # The orphan is the only pending change, so it alone must raise the prompt.
    out = _ok(run([*install, *ONLY, "--agents", "shared"], input="n\n"))

    assert "Orphaned Caches" in out
    assert "Cancelled" in out
    assert retired.is_dir()


@pytest.mark.e2e
@pytest.mark.skipif(is_windows(), reason="POSIX permission bits")
def test_undeletable_orphan_warns_and_install_still_links(env):
    home, run, install, _user_config = env
    _ok(run([*install, *ONLY, "-y"]))
    locked = _cache(home, "retired") / "sub"
    locked.mkdir(parents=True)
    (locked / "file").write_text("x", encoding="utf-8")
    os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
    (home / "AGENTS.md").unlink()

    try:
        out = _ok(run([*install, *ONLY, "-y"]))
    finally:
        os.chmod(locked, stat.S_IRWXU)

    assert "Could not remove orphaned cache" in out
    assert "removed" not in _summary_line(out)
    assert locked.is_dir()
    assert (home / "AGENTS.md").is_symlink()
