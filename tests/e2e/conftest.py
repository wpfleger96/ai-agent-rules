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
    return home_dir, make_home_env(home_dir)


@pytest.fixture
def e2e_config_dir(tmp_path, config_tree_writer):
    return config_tree_writer(
        tmp_path / "config",
        {
            "AGENTS.md": "# Shared Agent Rules\n",
            "claude/CLAUDE.md": "",
            "claude/settings.json": '{"test": "e2e"}',
            "claude/mcps.json": "{}",
            "codex/config.toml": 'model = "test-model"\n',
            "codex/AGENTS.md": "@~/AGENTS.md\n",
            "gemini/GEMINI.md": "",
            "gemini/settings.json": '{"name": "test"}',
            "amp/AGENTS.md": "",
            "amp/settings.json": '{"test": true}',
            "goose/config.yaml": "test: e2e\n",
            "goose/.goosehints": "",
            "profiles/default.yaml": "name: default\nagents:\n  - claude\n  - codex\n",
        },
    )


@pytest.fixture
def run_cli(e2e_home):
    home_dir, env = e2e_home
    return make_cli_runner(home_dir, env)


@pytest.fixture
def run_cli_with_config(run_cli, e2e_home, e2e_config_dir):
    home_dir, _env_overrides = e2e_home
    return run_cli, home_dir, e2e_config_dir


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
