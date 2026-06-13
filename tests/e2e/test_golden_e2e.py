"""Golden-snapshot E2E gates.

These convert two guarantees that are normally checked by hand into
CI-enforced regressions:

* the **dry-run plan** ``install --dry-run`` emits, and
* the **symlink manifest** a real install materializes on disk.

A refactor that changes either (e.g. a divergence between the dry-run path and
the real install path, or a dropped/renamed symlink) fails here instead of
shipping silently.

Goldens are pinned on Linux so absolute-path and platform-symlink differences
(Amp on Windows, Gemini copy-mode, the Goose config dir) don't destabilize the
snapshot; the install-and-inspect and lifecycle suites carry the cross-platform
coverage. Regenerate with ``UPDATE_GOLDENS=1 just test-e2e``.
"""

from __future__ import annotations

import os
import sys

from pathlib import Path

import pytest

from tests.e2e.helpers import (
    CORE_COMPONENTS,
    build_config_dir,
    collect_symlink_manifest,
    make_cli_runner,
    make_home_env,
    normalize_output,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE = os.environ.get("UPDATE_GOLDENS") == "1"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="goldens are pinned on Linux"
)


def _canonical_install(tmp_path: Path, *, dry_run: bool) -> tuple[str, Path, Path]:
    """Install the canonical golden config into a fresh HOME; return (out, home, config)."""
    home = tmp_path / "home"
    home.mkdir()
    config = build_config_dir(tmp_path / "rules")
    # A generous fixed width keeps Rich from wrapping the long absolute-path
    # lines (which vary with the pytest tmp_path length) so the golden is stable.
    env = make_home_env(home, columns=400)
    run = make_cli_runner(home, env)
    args = ["install", "-y", "--skip-completions", "--only", CORE_COMPONENTS]
    if dry_run:
        args.append("--dry-run")
    args += ["--config-dir", str(config)]
    result = run(args)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr, home, config


def _check_golden(name: str, actual: str) -> None:
    path = GOLDEN_DIR / name
    if UPDATE:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        pytest.skip(f"updated golden {name}")
    assert path.exists(), (
        f"missing golden {path}; run UPDATE_GOLDENS=1 just test-e2e to create it"
    )
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"golden {name} mismatch; if intended, run UPDATE_GOLDENS=1 just test-e2e"
    )


@pytest.mark.e2e
class TestGoldenSnapshots:
    def test_dry_run_plan_matches_golden(self, tmp_path):
        raw, home, config = _canonical_install(tmp_path, dry_run=True)
        actual = normalize_output(raw, {str(home): "<HOME>", str(config): "<CONFIG>"})
        _check_golden("install_dry_run.txt", actual)

    def test_symlink_manifest_matches_golden(self, tmp_path):
        _raw, home, _config = _canonical_install(tmp_path, dry_run=False)
        actual = "\n".join(collect_symlink_manifest(home)) + "\n"
        _check_golden("symlink_manifest.txt", actual)
