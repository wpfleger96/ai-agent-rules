"""End-to-end MCP translation/merge tests.

A single shared ``mcps.json`` is fanned out through five different MCP managers,
each writing a different native format to a different file. These tests install
real MCPs and inspect every generated artifact, exercising the per-agent
``_translate`` implementations and the JSON/TOML/YAML writers end-to-end.

Each agent is installed in its own ``--agents <id>`` invocation. That keeps the
component runner single-threaded for the MCP step, which is deterministic;
installing several MCP-writing agents in one parallel run is racy in the app
today (see the PR description), so we avoid coupling these assertions to it.
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.helpers import build_config_dir, is_windows, make_cli_runner

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
