"""Tests for MCP management functionality."""

import json

import pytest
import yaml

from ai_rules.config import Config
from ai_rules.mcp import (
    AmpMCPManager,
    ClaudeMCPManager,
    CodexMCPManager,
    GeminiMCPManager,
    GooseMCPManager,
    OperationResult,
)


@pytest.fixture(autouse=True)
def setup_test_mcp(test_repo):
    """Add test-mcp to mcps.json for MCP-specific tests."""
    mcps_file = test_repo / "claude" / "mcps.json"
    mcps_data = {"test-mcp": {"type": "stdio", "command": "test", "args": []}}
    mcps_file.write_text(json.dumps(mcps_data, indent=2))
    return test_repo


@pytest.fixture
def manager():
    """Create a ClaudeMCPManager instance."""
    return ClaudeMCPManager()


@pytest.fixture
def config_with_overrides():
    """Create a config with MCP overrides."""
    return Config(
        mcp_overrides={
            "test-mcp": {"env": {"TEST_API_KEY": "test-key"}},
            "override-only": {"type": "stdio", "command": "override-mcp", "args": []},
        }
    )


def test_load_managed_mcps(manager, test_repo):
    """Test loading managed MCPs from repo config file."""
    config = Config()
    mcps = manager.load_managed_mcps(test_repo, config)

    assert "test-mcp" in mcps
    assert mcps["test-mcp"]["type"] == "stdio"
    assert mcps["test-mcp"]["command"] == "test"


def test_merge_mcp_overrides(manager, test_repo, config_with_overrides):
    """Test that user overrides merge correctly with base MCPs."""
    mcps = manager.load_managed_mcps(test_repo, config_with_overrides)

    assert mcps["test-mcp"]["env"]["TEST_API_KEY"] == "test-key"
    assert mcps["test-mcp"]["type"] == "stdio"
    assert mcps["test-mcp"]["command"] == "test"

    assert "override-only" in mcps
    assert mcps["override-only"]["command"] == "override-mcp"


def test_install_mcps_fresh(manager, mock_home, test_repo):
    """Test first install creates tracking and updates ~/.claude.json."""
    config = Config()
    result, message, conflicts = manager.install_mcps(test_repo, config)

    assert result == OperationResult.UPDATED
    assert "MCPs installed" in message
    assert conflicts == []

    assert manager.CLAUDE_JSON.exists()
    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert "mcpServers" in data
        assert "test-mcp" in data["mcpServers"]
        assert data["mcpServers"]["test-mcp"]["_managedBy"] == "ai-agent-rules"


def test_install_mcps_update(manager, mock_home, test_repo):
    """Test subsequent install updates existing MCPs."""
    config = Config()

    manager.install_mcps(test_repo, config, force=True)

    mcps_file = test_repo / "claude" / "mcps.json"
    with open(mcps_file) as f:
        mcps_data = json.load(f)
        mcps_data["test-mcp"]["args"] = ["modified"]
    with open(mcps_file, "w") as f:
        json.dump(mcps_data, f)

    result, message, conflicts = manager.install_mcps(test_repo, config, force=True)
    assert result == OperationResult.UPDATED

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert data["mcpServers"]["test-mcp"]["args"] == ["modified"]


def test_install_mcps_conflict_detection(manager, mock_home, test_repo):
    """Test that conflicts are detected when user modifies managed MCP."""
    config = Config()

    manager.install_mcps(test_repo, config, force=True)

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        data["mcpServers"]["test-mcp"]["args"] = ["user-modified"]
    with open(manager.CLAUDE_JSON, "w") as f:
        json.dump(data, f)

    result, message, conflicts = manager.install_mcps(test_repo, config, force=False)
    assert result == OperationResult.ERROR
    assert "test-mcp" in conflicts


def test_uninstall_mcps(manager, mock_home, test_repo):
    """Test that uninstall removes only tracked MCPs."""
    config = Config()
    manager.install_mcps(test_repo, config, force=True)

    result, message = manager.uninstall_mcps(force=True)
    assert result == OperationResult.REMOVED
    assert "Removed" in message

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert "test-mcp" not in data.get("mcpServers", {})


def test_uninstall_preserves_user_mcps(manager, mock_home, test_repo):
    """Test that user MCPs are untouched during uninstall."""
    config = Config()
    manager.install_mcps(test_repo, config, force=True)

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        data["mcpServers"]["user-custom-mcp"] = {
            "type": "stdio",
            "command": "user-mcp",
            "args": [],
        }
    with open(manager.CLAUDE_JSON, "w") as f:
        json.dump(data, f)

    manager.uninstall_mcps(force=True)

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert "user-custom-mcp" in data["mcpServers"]
        assert "test-mcp" not in data["mcpServers"]


def test_status_shows_managed_vs_unmanaged(manager, mock_home, test_repo):
    """Test that status correctly categorizes managed vs unmanaged MCPs."""
    config = Config()
    manager.install_mcps(test_repo, config, force=True)

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        data["mcpServers"]["user-mcp"] = {
            "type": "stdio",
            "command": "user-mcp",
            "args": [],
        }
    with open(manager.CLAUDE_JSON, "w") as f:
        json.dump(data, f)

    status = manager.get_status(test_repo, config)

    assert "test-mcp" in status.managed_mcps
    assert "user-mcp" in status.unmanaged_mcps


def test_claude_json_missing(manager, mock_home, test_repo):
    """Test that install handles missing ~/.claude.json gracefully."""
    config = Config()
    assert not manager.CLAUDE_JSON.exists()

    result, message, conflicts = manager.install_mcps(test_repo, config)
    assert result == OperationResult.UPDATED
    assert manager.CLAUDE_JSON.exists()

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert "mcpServers" in data


def test_atomic_write_backup(manager, mock_home, test_repo):
    """Test that backup is created before modification."""
    config = Config()

    original_content = {"mcpServers": {}, "existingKey": "existingValue"}
    manager.CLAUDE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(manager.CLAUDE_JSON, "w") as f:
        json.dump(original_content, f)

    manager.install_mcps(test_repo, config, force=True)

    backup_files = list(manager.CLAUDE_JSON.parent.glob("*.ai-agent-rules-backup.*"))
    assert len(backup_files) == 1

    with open(backup_files[0]) as f:
        backup_data = json.load(f)
        assert backup_data == original_content


def test_dry_run_mode(manager, mock_home, test_repo):
    """Test that dry run mode doesn't modify files."""
    config = Config()

    result, message, conflicts = manager.install_mcps(test_repo, config, dry_run=True)
    assert result == OperationResult.UPDATED
    assert "Would update" in message

    assert not manager.CLAUDE_JSON.exists()


def test_format_diff(manager):
    """Test diff formatting for conflicts."""
    expected = {"type": "stdio", "command": "uvx", "args": ["mcp_test@latest"]}
    installed = {"type": "stdio", "command": "uvx", "args": ["mcp_test@0.2.0"]}

    diff = manager.format_diff("test-mcp", expected, installed)
    assert "test-mcp" in diff
    assert "mcp_test@latest" in diff
    assert "mcp_test@0.2.0" in diff
    assert "Expected (repo)" in diff
    assert "Installed (local)" in diff


def test_detect_conflicts(manager):
    """Test conflict detection logic."""
    expected = {"mcp1": {"command": "cmd1"}, "mcp2": {"command": "cmd2"}}
    installed = {"mcp1": {"command": "cmd1-modified"}, "mcp2": {"command": "cmd2"}}

    conflicts = manager.detect_conflicts(expected, installed)
    assert conflicts == ["mcp1"]


def test_status_sync_detection(manager, mock_home, test_repo):
    """Test that status correctly detects synced vs outdated MCPs."""
    config = Config()
    manager.install_mcps(test_repo, config, force=True)

    status = manager.get_status(test_repo, config)
    assert status.installed["test-mcp"] is True

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        data["mcpServers"]["test-mcp"]["args"] = ["modified"]
    with open(manager.CLAUDE_JSON, "w") as f:
        json.dump(data, f)

    status = manager.get_status(test_repo, config)
    assert status.installed["test-mcp"] is False


def test_status_override_detection(
    manager, mock_home, test_repo, config_with_overrides
):
    """Test that status detects which MCPs have overrides."""
    manager.install_mcps(test_repo, config_with_overrides, force=True)

    status = manager.get_status(test_repo, config_with_overrides)
    assert status.has_overrides["test-mcp"] is True
    assert status.has_overrides.get("override-only", False) is True


def test_install_removes_mcps_no_longer_in_repo(manager, mock_home, test_repo):
    """Test that MCPs removed from repo config are cleaned up on install."""
    config = Config()

    manager.install_mcps(test_repo, config, force=True)
    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert "test-mcp" in data["mcpServers"]
        assert data["mcpServers"]["test-mcp"]["_managedBy"] == "ai-agent-rules"

    mcps_file = test_repo / "claude" / "mcps.json"
    mcps_file.write_text("{}")

    result, message, _ = manager.install_mcps(test_repo, config, force=True)
    assert result == OperationResult.UPDATED
    assert "removed" in message

    with open(manager.CLAUDE_JSON) as f:
        data = json.load(f)
        assert "test-mcp" not in data.get("mcpServers", {})


# ---------------------------------------------------------------------------
# Shared MCP source: config/mcps.json vs legacy config/claude/mcps.json
# ---------------------------------------------------------------------------


def test_load_prefers_shared_mcps_json(manager, test_repo):
    """Shared config/mcps.json takes precedence over legacy claude/mcps.json."""
    shared_file = test_repo / "mcps.json"
    shared_file.write_text(
        json.dumps({"shared-mcp": {"command": "uvx", "args": ["shared"]}})
    )

    config = Config()
    mcps = manager.load_managed_mcps(test_repo, config)

    assert "shared-mcp" in mcps
    assert "test-mcp" not in mcps


def test_load_falls_back_to_claude_mcps_json(manager, test_repo):
    """Falls back to claude/mcps.json when config/mcps.json is absent."""
    assert not (test_repo / "mcps.json").exists()

    config = Config()
    mcps = manager.load_managed_mcps(test_repo, config)

    assert "test-mcp" in mcps


# ---------------------------------------------------------------------------
# GooseMCPManager
# ---------------------------------------------------------------------------


def test_goose_translate_maps_shared_format(mock_home):
    """_translate converts shared format to Goose extension format."""
    mgr = GooseMCPManager()
    shared = {
        "command": "uvx",
        "args": ["recall-mcp-server"],
        "env": {"RECALL_WIKI_PATH": "~/.recall"},
        "name": "Recall",
        "description": "Persistent LLM knowledge base",
    }

    result = mgr._translate(shared)

    assert result["type"] == "stdio"
    assert result["cmd"] == "uvx"
    assert result["args"] == ["recall-mcp-server"]
    assert result["envs"] == {"RECALL_WIKI_PATH": "~/.recall"}
    assert result["env_keys"] == []
    assert result["enabled"] is True
    assert result["timeout"] == 300
    assert result["bundled"] is False
    assert result["available_tools"] == []
    assert result["name"] == "Recall"
    assert result["description"] == "Persistent LLM knowledge base"


def test_goose_translate_minimal_config(mock_home):
    """_translate handles missing optional fields gracefully."""
    mgr = GooseMCPManager()
    result = mgr._translate({"command": "uvx"})

    assert result["cmd"] == "uvx"
    assert result["args"] == []
    assert result["envs"] == {}


def test_goose_install_and_uninstall(mock_home, test_repo):
    """GooseMCPManager writes to ~/.config/goose/config.yaml and removes on uninstall."""
    shared_file = test_repo / "mcps.json"
    shared_file.write_text(
        json.dumps(
            {"recall": {"command": "uvx", "args": ["recall-mcp-server"], "env": {}}}
        )
    )

    mgr = GooseMCPManager()
    config = Config()

    result, message, conflicts = mgr.install_mcps(test_repo, config)
    assert result == OperationResult.UPDATED
    assert conflicts == []

    config_path = mock_home / ".config" / "goose" / "config.yaml"
    assert config_path.exists()
    with open(config_path) as f:
        data = yaml.safe_load(f)

    assert "recall" in data["extensions"]
    assert data["extensions"]["recall"]["_managed_by"] == "ai-agent-rules"
    assert data["extensions"]["recall"]["cmd"] == "uvx"

    result, message = mgr.uninstall_mcps()
    assert result == OperationResult.REMOVED
    with open(config_path) as f:
        data = yaml.safe_load(f)
    assert "recall" not in data.get("extensions", {})


def test_goose_preserves_non_extension_keys(mock_home, test_repo):
    """Goose install does not clobber GOOSE_MODEL or other existing config keys."""
    config_path = mock_home / ".config" / "goose"
    config_path.mkdir(parents=True)
    (config_path / "config.yaml").write_text(
        "GOOSE_MODEL: claude-opus-4-5\nGOOSE_PROVIDER: anthropic\n"
    )

    shared_file = test_repo / "mcps.json"
    shared_file.write_text(json.dumps({"mcp-a": {"command": "uvx", "args": []}}))

    mgr = GooseMCPManager()
    mgr.install_mcps(test_repo, Config())

    with open(config_path / "config.yaml") as f:
        data = yaml.safe_load(f)

    assert data["GOOSE_MODEL"] == "claude-opus-4-5"
    assert data["GOOSE_PROVIDER"] == "anthropic"
    assert "mcp-a" in data["extensions"]


# ---------------------------------------------------------------------------
# CodexMCPManager
# ---------------------------------------------------------------------------


def test_codex_translate_maps_shared_format(mock_home):
    """_translate extracts command/args/env for TOML."""
    mgr = CodexMCPManager()
    shared = {
        "command": "uvx",
        "args": ["recall-mcp-server"],
        "env": {"RECALL_WIKI_PATH": "~/.recall"},
        "name": "Recall",
        "description": "ignored",
    }

    result = mgr._translate(shared)

    assert result["command"] == "uvx"
    assert result["args"] == ["recall-mcp-server"]
    assert result["env"] == {"RECALL_WIKI_PATH": "~/.recall"}
    assert "name" not in result
    assert "description" not in result


def test_codex_translate_minimal_config(mock_home):
    """_translate handles configs with only a command."""
    mgr = CodexMCPManager()
    result = mgr._translate({"command": "npx"})
    assert result["command"] == "npx"
    assert "args" not in result
    assert "env" not in result


def test_codex_install_and_uninstall(mock_home, test_repo):
    """CodexMCPManager writes to ~/.codex/config.toml and cleans up on uninstall."""
    import tomlkit

    shared_file = test_repo / "mcps.json"
    shared_file.write_text(
        json.dumps(
            {"recall": {"command": "uvx", "args": ["recall-mcp-server"], "env": {}}}
        )
    )

    mgr = CodexMCPManager()
    result, message, conflicts = mgr.install_mcps(test_repo, Config())
    assert result == OperationResult.UPDATED

    config_path = mock_home / ".codex" / "config.toml"
    assert config_path.exists()
    with open(config_path) as f:
        doc = tomlkit.load(f)

    mcp_servers = dict(doc["mcp_servers"])  # type: ignore[arg-type]
    assert "recall" in mcp_servers
    managed_section = doc["_ai_agent_rules_managed"]
    managed_names = list(managed_section["names"])  # type: ignore[index,arg-type]
    assert "recall" in managed_names

    result, message = mgr.uninstall_mcps()
    assert result == OperationResult.REMOVED
    with open(config_path) as f:
        doc = tomlkit.load(f)
    mcp_servers_after = dict(doc.get("mcp_servers", {}))
    assert "recall" not in mcp_servers_after
    managed_after = doc.get("_ai_agent_rules_managed", {})
    names_after = list(managed_after.get("names", []))
    assert "recall" not in names_after


def test_codex_preserves_non_mcp_keys(mock_home, test_repo):
    """Codex install preserves approval_policy, model, and other config keys."""
    import tomlkit

    config_dir = mock_home / ".codex"
    config_dir.mkdir(parents=True)
    original = 'model = "gpt-5.2-codex"\napproval_policy = "on-request"\n'
    (config_dir / "config.toml").write_text(original)

    shared_file = test_repo / "mcps.json"
    shared_file.write_text(json.dumps({"mcp-a": {"command": "uvx", "args": []}}))

    CodexMCPManager().install_mcps(test_repo, Config())

    with open(config_dir / "config.toml") as f:
        doc = tomlkit.load(f)

    assert doc["model"] == "gpt-5.2-codex"
    assert doc["approval_policy"] == "on-request"
    assert "mcp-a" in dict(doc["mcp_servers"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GeminiMCPManager
# ---------------------------------------------------------------------------


def test_gemini_translate_adds_timeout_and_trust(mock_home):
    """_translate adds timeout and trust fields to Gemini MCP config."""
    mgr = GeminiMCPManager()
    shared = {
        "command": "uvx",
        "args": ["recall-mcp-server"],
        "env": {"RECALL_WIKI_PATH": "~/.recall"},
    }

    result = mgr._translate(shared)

    assert result["command"] == "uvx"
    assert result["args"] == ["recall-mcp-server"]
    assert result["env"] == {"RECALL_WIKI_PATH": "~/.recall"}
    assert result["timeout"] == 30000
    assert result["trust"] is False


def test_gemini_translate_minimal_config(mock_home):
    """_translate handles configs with only command and args."""
    mgr = GeminiMCPManager()
    result = mgr._translate({"command": "node", "args": ["server.js"]})
    assert result["command"] == "node"
    assert result["timeout"] == 30000
    assert result["trust"] is False
    assert "env" not in result


def test_gemini_install_and_uninstall(mock_home, test_repo):
    """GeminiMCPManager writes to ~/.gemini/settings.json and removes on uninstall."""
    shared_file = test_repo / "mcps.json"
    shared_file.write_text(
        json.dumps(
            {"recall": {"command": "uvx", "args": ["recall-mcp-server"], "env": {}}}
        )
    )

    mgr = GeminiMCPManager()
    result, message, conflicts = mgr.install_mcps(test_repo, Config())
    assert result == OperationResult.UPDATED

    config_path = mock_home / ".gemini" / "settings.json"
    assert config_path.exists()
    with open(config_path) as f:
        data = json.load(f)

    assert "recall" in data["mcpServers"]
    assert data["mcpServers"]["recall"]["_managedBy"] == "ai-agent-rules"
    assert data["mcpServers"]["recall"]["timeout"] == 30000
    assert data["mcpServers"]["recall"]["trust"] is False

    result, message = mgr.uninstall_mcps()
    assert result == OperationResult.REMOVED
    with open(config_path) as f:
        data = json.load(f)
    assert "recall" not in data.get("mcpServers", {})


def test_gemini_preserves_non_mcp_keys(mock_home, test_repo):
    """Gemini install preserves context, tools, model, and other keys."""
    gemini_dir = mock_home / ".gemini"
    gemini_dir.mkdir(parents=True)
    existing = {"model": "gemini-3.1-pro-preview", "context": {}, "ui": {}}
    (gemini_dir / "settings.json").write_text(json.dumps(existing))

    shared_file = test_repo / "mcps.json"
    shared_file.write_text(json.dumps({"mcp-a": {"command": "uvx", "args": []}}))

    GeminiMCPManager().install_mcps(test_repo, Config())

    with open(gemini_dir / "settings.json") as f:
        data = json.load(f)

    assert data["model"] == "gemini-3.1-pro-preview"
    assert data["context"] == {}
    assert data["ui"] == {}
    assert "mcp-a" in data["mcpServers"]


# ---------------------------------------------------------------------------
# AmpMCPManager
# ---------------------------------------------------------------------------


def test_amp_translate_maps_shared_format(mock_home):
    """_translate strips name/description and passes command/args/env."""
    mgr = AmpMCPManager()
    shared = {
        "command": "uvx",
        "args": ["recall-mcp-server"],
        "env": {"RECALL_WIKI_PATH": "~/.recall"},
        "name": "Recall",
        "description": "ignored",
    }

    result = mgr._translate(shared)

    assert result["command"] == "uvx"
    assert result["args"] == ["recall-mcp-server"]
    assert result["env"] == {"RECALL_WIKI_PATH": "~/.recall"}
    assert "name" not in result
    assert "description" not in result


def test_amp_translate_minimal_config(mock_home):
    """_translate handles configs with only a command."""
    mgr = AmpMCPManager()
    result = mgr._translate({"command": "npx"})
    assert result["command"] == "npx"
    assert "args" not in result
    assert "env" not in result


def test_amp_install_and_uninstall(mock_home, test_repo):
    """AmpMCPManager writes to ~/.config/amp/settings.json and removes on uninstall."""
    shared_file = test_repo / "mcps.json"
    shared_file.write_text(
        json.dumps(
            {"recall": {"command": "uvx", "args": ["recall-mcp-server"], "env": {}}}
        )
    )

    mgr = AmpMCPManager()
    result, message, conflicts = mgr.install_mcps(test_repo, Config())
    assert result == OperationResult.UPDATED
    assert conflicts == []

    config_path = mock_home / ".config" / "amp" / "settings.json"
    assert config_path.exists()
    with open(config_path) as f:
        data = json.load(f)

    assert "recall" in data["amp.mcpServers"]
    assert data["amp.mcpServers"]["recall"]["_managedBy"] == "ai-agent-rules"
    assert data["amp.mcpServers"]["recall"]["command"] == "uvx"

    result, message = mgr.uninstall_mcps()
    assert result == OperationResult.REMOVED
    with open(config_path) as f:
        data = json.load(f)
    assert "recall" not in data.get("amp.mcpServers", {})


def test_amp_preserves_non_mcp_keys(mock_home, test_repo):
    """Amp install preserves existing amp.* settings and other keys."""
    amp_dir = mock_home / ".config" / "amp"
    amp_dir.mkdir(parents=True)
    existing = {"amp.showCosts": True, "amp.anthropic.thinking.enabled": True}
    (amp_dir / "settings.json").write_text(json.dumps(existing))

    shared_file = test_repo / "mcps.json"
    shared_file.write_text(json.dumps({"mcp-a": {"command": "uvx", "args": []}}))

    AmpMCPManager().install_mcps(test_repo, Config())

    with open(amp_dir / "settings.json") as f:
        data = json.load(f)

    assert data["amp.showCosts"] is True
    assert data["amp.anthropic.thinking.enabled"] is True
    assert "mcp-a" in data["amp.mcpServers"]


def test_install_mcps_noop_returns_already_installed(manager, mock_home, test_repo):
    """install_mcps returns ALREADY_INSTALLED when MCPs haven't changed."""
    config = Config()
    result1, _, _ = manager.install_mcps(test_repo, config, force=True)
    assert result1 == OperationResult.UPDATED

    result2, message2, _ = manager.install_mcps(test_repo, config, force=True)
    assert result2 == OperationResult.ALREADY_INSTALLED
    assert "already up to date" in message2


def test_get_native_mcps(manager, test_repo):
    """get_native_mcps returns translated MCPs with managed-by marker."""
    config = Config()
    native = manager.get_native_mcps(test_repo, config)

    assert "test-mcp" in native
    assert native["test-mcp"]["_managedBy"] == "ai-agent-rules"
    assert native["test-mcp"]["command"] == "test"


def test_mcp_settings_key_claude_is_none():
    """Claude stores MCPs in a separate file, so mcp_settings_key is None."""
    assert ClaudeMCPManager().mcp_settings_key is None


def test_mcp_settings_key_amp():
    """Amp stores MCPs in the settings file under amp.mcpServers."""
    assert AmpMCPManager().mcp_settings_key == "amp.mcpServers"


def test_mcp_settings_key_gemini():
    """Gemini stores MCPs in the settings file under mcpServers."""
    assert GeminiMCPManager().mcp_settings_key == "mcpServers"


def test_mcp_settings_key_codex():
    """Codex stores MCPs in config.toml under mcp_servers."""
    mgr = CodexMCPManager()
    assert mgr.mcp_settings_key == "mcp_servers"
    assert mgr.mcp_tracking_key == "_ai_agent_rules_managed"


def test_mcp_settings_key_goose():
    """Goose stores MCPs in config.yaml under extensions."""
    assert GooseMCPManager().mcp_settings_key == "extensions"
