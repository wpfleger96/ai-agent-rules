"""End-to-end lifecycle round-trip against the *bundled* shipped config.

``status``, ``diff`` and ``uninstall`` resolve their config via
``get_config_dir()`` (the installed package config), not a ``--config-dir``
override. The only way to exercise the full install -> status -> diff ->
reinstall -> uninstall arc end-to-end is therefore against the bundled config,
which is also the truest simulation of real ``ai-agent-rules install`` usage.

Runs are scoped to the core symlink/merge components so the arc stays hermetic
(no `claude`/`uv` network calls) and deterministic across the OS matrix; we
assert high-level invariants rather than exact paths so the suite is portable.
"""

from __future__ import annotations

import pytest

from tests.e2e.helpers import CORE_COMPONENTS, CliResult, strip_ansi


def _out(result: CliResult) -> str:
    return strip_ansi(result.stdout + result.stderr)


@pytest.mark.e2e
class TestBundledLifecycle:
    def test_full_lifecycle_round_trip(self, cli_in_home):
        run, home = cli_in_home
        only = ["--only", CORE_COMPONENTS]

        # 1. Install the real shipped config into a clean HOME.
        install = run(["install", "-y", "--skip-completions", *only])
        install_out = _out(install)
        assert install.returncode == 0, install_out
        assert "Created" in install_out
        # A few well-known stable targets must now exist as symlinks.
        assert (home / "AGENTS.md").is_symlink()
        assert (home / ".claude" / "CLAUDE.md").is_symlink()

        # 2. status reports a clean install.
        status = run(["status", *only])
        status_out = _out(status)
        assert status.returncode == 0, status_out
        assert "All symlinks are correct!" in status_out

        # 3. diff finds no differences.
        diff = run(["diff", *only])
        diff_out = _out(diff)
        assert diff.returncode == 0, diff_out
        assert "No differences found" in diff_out

        # 4. Re-install is idempotent.
        reinstall = run(["install", "-y", "--skip-completions", *only])
        reinstall_out = _out(reinstall)
        assert reinstall.returncode == 0, reinstall_out
        assert "up to date" in reinstall_out.lower() or (
            "unchanged" in reinstall_out.lower()
        )

        # 5. Uninstall removes the managed symlinks.
        uninstall = run(["uninstall", "-y", *only])
        uninstall_out = _out(uninstall)
        assert uninstall.returncode == 0, uninstall_out
        assert "Removed" in uninstall_out
        assert not (home / "AGENTS.md").exists()
        assert not (home / ".claude" / "CLAUDE.md").exists()

        # 6. status now reports an incomplete install (non-zero exit).
        status_after = run(["status", *only])
        assert status_after.returncode == 1, _out(status_after)
