"""End-to-end MCP translation/merge tests.

A single shared ``mcps.json`` is fanned out through five different MCP managers,
each writing a different native format to a different file. These tests install
real MCPs and inspect every generated artifact, exercising the per-agent
``_translate`` implementations and the JSON/TOML/YAML writers end-to-end.

The per-agent translation tests install each agent in its own ``--agents <id>``
invocation, which keeps the assertions focused on one native format at a time.
``TestParallelMCPInstall`` then covers the full multi-agent parallel install,
guarding the fix that defers the MCP component until after ConfigComponent has
created the settings symlinks (previously these two raced on the per-agent
settings files, intermittently failing the install).
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.helpers import (
    build_config_dir,
    is_windows,
    make_cli_runner,
    make_home_env,
)

SHARED_MCPS = {
    "demo": {
        "command": "demo-server",
        "args": ["--port", "9000"],
        "description": "A demo MCP",
        "type": "stdio",
    }
}


@pytest.fixture
def mcp_env(isolated_home, tmp_path):
    home, env = isolated_home
    config = build_config_dir(tmp_path / "rules", mcps=SHARED_MCPS)
    run = make_cli_runner(home, env)

    def install_agent(agent_id):
        result = run(
            [
                "install",
                "-y",
                "--skip-completions",
                "--only",
                "settings,agents-md,config,mcps",
                "--agents",
                agent_id,
                "--config-dir",
                str(config),
            ]
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    return install_agent, home


@pytest.mark.e2e
class TestMCPTranslation:
    def test_claude_mcp_written_to_claude_json(self, mcp_env):
        install_agent, home = mcp_env
        install_agent("claude")
        data = json.loads((home / ".claude.json").read_text("utf-8"))
        demo = data["mcpServers"]["demo"]
        assert demo["command"] == "demo-server"
        assert demo["args"] == ["--port", "9000"]
        assert demo["_managedBy"] == "ai-agent-rules"
        # Claude strips the shared-only "description" field.
        assert "description" not in demo

    def test_gemini_mcp_written_with_native_extras(self, mcp_env):
        install_agent, home = mcp_env
        install_agent("gemini")
        data = json.loads((home / ".gemini" / "settings.json").read_text("utf-8"))
        demo = data["mcpServers"]["demo"]
        assert demo["command"] == "demo-server"
        # Gemini's translation injects native trust/timeout defaults.
        assert "trust" in demo
        assert "timeout" in demo

    def test_codex_mcp_written_to_toml(self, mcp_env):
        install_agent, home = mcp_env
        install_agent("codex")
        text = (home / ".codex" / "config.toml").read_text("utf-8")
        assert "[mcp_servers.demo]" in text
        assert 'command = "demo-server"' in text

    def test_goose_mcp_written_to_yaml(self, mcp_env):
        import yaml

        install_agent, home = mcp_env
        install_agent("goose")
        data = yaml.safe_load(
            (home / ".config" / "goose" / "config.yaml").read_text("utf-8")
        )
        demo = data["extensions"]["demo"]
        # Goose renames command -> cmd in its extension schema.
        assert demo["cmd"] == "demo-server"
        assert demo["_managed_by"] == "ai-agent-rules"

    @pytest.mark.skipif(is_windows(), reason="Amp is not managed on Windows")
    def test_amp_mcp_written_under_namespaced_key(self, mcp_env):
        install_agent, home = mcp_env
        install_agent("amp")
        data = json.loads(
            (home / ".config" / "amp" / "settings.json").read_text("utf-8")
        )
        demo = data["amp.mcpServers"]["demo"]
        assert demo["command"] == "demo-server"
        assert demo["_managedBy"] == "ai-agent-rules"


@pytest.mark.e2e
class TestParallelMCPInstall:
    """Regression guard for the Config<->MCP symlink-creation race.

    Installs all agents in one parallel run (no ``--agents``) so ConfigComponent
    and MCPComponent run in the same install. Before the fix this failed the
    large majority of the time with ``Created N-1`` + ``1 error(s)``; with the
    MCP component deferred until after symlink creation it is deterministic.
    Looped to make the guard robust against an intermittent race.
    """

    def test_parallel_install_is_race_free(self, isolated_home, tmp_path):
        _home, env = isolated_home
        config = build_config_dir(tmp_path / "rules", mcps=SHARED_MCPS)

        last_home = None
        for i in range(6):
            home = tmp_path / f"home-{i}"
            home.mkdir()
            run = make_cli_runner(home, make_home_env(home))
            result = run(
                [
                    "install",
                    "-y",
                    "--skip-completions",
                    "--only",
                    "settings,agents-md,config,mcps",
                    "--config-dir",
                    str(config),
                ]
            )
            assert result.returncode == 0, (
                f"iteration {i} failed:\n{result.stdout}{result.stderr}"
            )
            last_home = home

        # Spot-check that MCPs landed correctly on the final iteration.
        assert last_home is not None
        claude = json.loads((last_home / ".claude.json").read_text("utf-8"))
        assert claude["mcpServers"]["demo"]["command"] == "demo-server"
        codex = (last_home / ".codex" / "config.toml").read_text("utf-8")
        assert "[mcp_servers.demo]" in codex
