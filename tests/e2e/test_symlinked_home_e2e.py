"""Real-CLI installs when HOME or a managed file is reached through a symlink."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.helpers import (
    CliResult,
    CliRunner,
    build_config_dir,
    make_cli_runner,
    make_home_env,
)

INSTALL = ["install", "-y", "--skip-completions", "--agents", "claude"]


@pytest.fixture(params=["prefix", "alias_dotdot"])
def symlinked_home(request, tmp_path):
    """Return (runner, home as spelled, physical home, config dir)."""
    physical = tmp_path / "physical" / "home"
    physical.mkdir(parents=True)
    if request.param == "prefix":
        (tmp_path / "var").symlink_to(tmp_path / "physical")
        home = tmp_path / "var" / "home"
    else:
        (tmp_path / "physical" / "deep").mkdir()
        (tmp_path / "alias").symlink_to(tmp_path / "physical" / "deep")
        home = tmp_path / "alias" / ".." / "home"
    config = build_config_dir(tmp_path / "rules")
    return make_cli_runner(home, make_home_env(home)), home, physical, config


def _install(
    run: CliRunner, config: Path, only: str = "settings,agents-md,config"
) -> CliResult:
    result = run([*INSTALL, "--only", only, "--config-dir", str(config)])
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.mark.e2e
class TestExcludedSettingsUnderSymlinkedHome:
    def _exclude(self, physical: Path) -> None:
        (physical / ".ai-agent-rules-config.yaml").write_text(
            "version: 1\nexclude_symlinks:\n  - ~/.claude/settings.json\n",
            encoding="utf-8",
        )

    def test_excluded_settings_link_is_removed(self, symlinked_home):
        run, _home, physical, config = symlinked_home
        _install(run, config)
        link = physical / ".claude" / "settings.json"
        assert link.is_symlink()

        self._exclude(physical)
        _install(run, config)

        assert not link.is_symlink()

    def test_unrelated_user_link_survives(self, symlinked_home, tmp_path):
        run, _home, physical, config = symlinked_home
        _install(run, config)
        own = tmp_path / "dotfiles" / "settings.json"
        own.parent.mkdir()
        own.write_text("{}")
        link = physical / ".claude" / "settings.json"
        link.unlink()
        link.symlink_to(own)

        self._exclude(physical)
        _install(run, config)

        assert link.resolve() == own.resolve()


@pytest.mark.e2e
def test_mcp_write_into_missing_folder_is_a_clean_error(isolated_home, tmp_path):
    home, env = isolated_home
    config = build_config_dir(
        tmp_path / "rules", mcps={"demo": {"command": "demo", "type": "stdio"}}
    )
    (home / ".claude.json").symlink_to(tmp_path / "gone" / "claude.json")

    result = make_cli_runner(home, env)(
        [
            *INSTALL,
            "--only",
            "settings,agents-md,config,mcps",
            "--config-dir",
            str(config),
        ]
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "Traceback" not in output
    assert ".claude.json" in output and "gone" in output
    assert (home / ".claude.json").is_symlink()
