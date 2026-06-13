import os
import subprocess
import sys

from pathlib import Path

import pytest

from tests.e2e.helpers import (
    build_config_dir,
    make_cli_runner,
    make_home_env,
)


@pytest.fixture
def e2e_home(tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    env_overrides = {
        "HOME": str(home_dir),
        "USERPROFILE": str(home_dir),
        "APPDATA": str(home_dir / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home_dir / "AppData" / "Local"),
        "NO_COLOR": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "PATH": os.environ.get("PATH", ""),
        "SHELL": "/bin/bash",
    }
    return home_dir, env_overrides


@pytest.fixture
def e2e_config_dir(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "AGENTS.md").write_text("# Shared Agent Rules\n")

    claude_dir = config_dir / "claude"
    claude_dir.mkdir()
    (claude_dir / "CLAUDE.md").write_text("")
    (claude_dir / "settings.json").write_text('{"test": "e2e"}')
    (claude_dir / "mcps.json").write_text("{}")

    codex_dir = config_dir / "codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text('model = "test-model"\n')
    (codex_dir / "AGENTS.md").write_text("@~/AGENTS.md\n")

    gemini_dir = config_dir / "gemini"
    gemini_dir.mkdir()
    (gemini_dir / "GEMINI.md").write_text("")
    (gemini_dir / "settings.json").write_text('{"name": "test"}')

    amp_dir = config_dir / "amp"
    amp_dir.mkdir()
    (amp_dir / "AGENTS.md").write_text("")
    (amp_dir / "settings.json").write_text('{"test": true}')

    goose_dir = config_dir / "goose"
    goose_dir.mkdir()
    (goose_dir / "config.yaml").write_text("test: e2e\n")
    (goose_dir / ".goosehints").write_text("")

    profiles_dir = config_dir / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "default.yaml").write_text(
        "name: default\nagents:\n  - claude\n  - codex\n"
    )

    return config_dir


@pytest.fixture
def run_cli(e2e_home):
    home_dir, env_overrides = e2e_home
    repo_root = Path(__file__).parents[2]
    src_path = repo_root / "src"

    def _run(args, extra_env=None, timeout=30):
        base_env = {**os.environ, **env_overrides}
        existing_pythonpath = base_env.get("PYTHONPATH", "")
        base_env["PYTHONPATH"] = (
            str(src_path)
            if not existing_pythonpath
            else os.pathsep.join([str(src_path), existing_pythonpath])
        )
        if extra_env:
            base_env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "ai_rules.cli", *args],
            capture_output=True,
            encoding="utf-8",
            check=False,
            cwd=repo_root,
            env=base_env,
            timeout=timeout,
        )

    return _run


@pytest.fixture
def run_cli_with_config(e2e_home, e2e_config_dir):
    home_dir, env_overrides = e2e_home
    repo_root = Path(__file__).parents[2]
    src_path = repo_root / "src"

    def _run(args, extra_env=None, timeout=30):
        base_env = {**os.environ, **env_overrides}
        existing_pythonpath = base_env.get("PYTHONPATH", "")
        base_env["PYTHONPATH"] = (
            str(src_path)
            if not existing_pythonpath
            else os.pathsep.join([str(src_path), existing_pythonpath])
        )
        if extra_env:
            base_env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "ai_rules.cli", *args],
            capture_output=True,
            encoding="utf-8",
            check=False,
            cwd=repo_root,
            env=base_env,
            timeout=timeout,
        )

    return _run, home_dir, e2e_config_dir


# ---------------------------------------------------------------------------
# Isolated-home fixtures for the install-and-inspect suites
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_home(tmp_path):
    """An empty, fully isolated HOME plus its environment overrides."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    return home_dir, make_home_env(home_dir)


@pytest.fixture
def cli_in_home(isolated_home):
    """A real-CLI runner bound to an isolated HOME.

    Returns ``(run, home_dir)``. ``run`` invokes ``python -m ai_rules.cli`` in a
    subprocess. Used by the bundled-config lifecycle tests, where status/diff/
    uninstall resolve the shipped package config via ``get_config_dir()``.
    """
    home_dir, env = isolated_home
    return make_cli_runner(home_dir, env), home_dir


@pytest.fixture
def toy_config(tmp_path):
    """A realistic standalone config dir built by :func:`build_config_dir`."""
    return build_config_dir(tmp_path / "rules")


@pytest.fixture
def cli_with_toy_config(isolated_home, toy_config):
    """Real-CLI runner + isolated HOME + a toy config dir.

    Returns ``(run, home_dir, config_dir)``. Drive ``install`` with
    ``--config-dir config_dir`` and inspect ``home_dir`` directly.
    """
    home_dir, env = isolated_home
    return make_cli_runner(home_dir, env), home_dir, toy_config
