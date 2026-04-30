"""MCP server management."""

import copy
import json
import shutil
import tempfile

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

import yaml

from .config import Config
from .utils import deep_merge


class OperationResult(Enum):
    CREATED = "created"
    UPDATED = "updated"
    REMOVED = "removed"
    ALREADY_INSTALLED = "already_installed"
    NOT_FOUND = "not_found"
    ERROR = "error"


class MCPStatus:
    def __init__(self) -> None:
        self.managed_mcps: dict[str, dict[str, Any]] = {}
        self.unmanaged_mcps: dict[str, dict[str, Any]] = {}
        self.pending_mcps: dict[str, dict[str, Any]] = {}
        self.stale_mcps: dict[str, dict[str, Any]] = {}
        self.installed: dict[str, bool] = {}
        self.has_overrides: dict[str, bool] = {}


MANAGED_BY_VALUE = "ai-agent-rules"
_MANAGED_BY_VALUE_LEGACY = "ai-rules"


def is_managed_value(v: str | None) -> bool:
    """Check if a value matches the current or legacy managed-by marker."""
    return v in (MANAGED_BY_VALUE, _MANAGED_BY_VALUE_LEGACY)


class MCPManager(ABC):
    """Abstract base for agent-specific MCP config managers."""

    BACKUP_SUFFIX = "ai-agent-rules-backup"

    # --- abstract interface ---------------------------------------------------

    @property
    @abstractmethod
    def _marker_field(self) -> str:
        """Field name used to mark managed MCP entries."""

    @abstractmethod
    def _read_installed(self) -> dict[str, Any]:
        """Return the currently installed MCP entries as {name: config}."""

    @abstractmethod
    def _write_installed(self, mcps: dict[str, Any]) -> None:
        """Persist the full set of MCP entries, merging with non-MCP config."""

    @abstractmethod
    def _translate(self, shared_config: dict[str, Any]) -> dict[str, Any]:
        """Convert shared MCP format to agent-native format."""

    @property
    def mcp_settings_key(self) -> str | None:
        """Key in the settings dict where MCPs are stored.

        Returns None if this manager stores MCPs in a separate file
        (e.g. Claude stores MCPs in ~/.claude.json, not in settings.json).
        """
        return None

    @property
    def mcp_tracking_key(self) -> str | None:
        """Key for the managed-names tracking section, if any."""
        return None

    def get_native_mcps(self, config_dir: Path, config: Config) -> dict[str, Any]:
        """Load managed MCPs, translate to native format, and stamp marker."""
        managed = self.load_managed_mcps(config_dir, config)
        result: dict[str, Any] = {}
        for name, shared_cfg in managed.items():
            native = self._translate(shared_cfg)
            native[self._marker_field] = MANAGED_BY_VALUE
            result[name] = native
        return result

    # --- shared logic --------------------------------------------------------

    def load_managed_mcps(self, config_dir: Path, config: Config) -> dict[str, Any]:
        """Load managed MCP definitions and apply user overrides.

        Prefers config/mcps.json (shared); falls back to config/claude/mcps.json
        for backward compatibility.
        """
        shared_file = config_dir / "mcps.json"
        legacy_file = config_dir / "claude" / "mcps.json"

        if shared_file.exists():
            with open(shared_file) as f:
                base_mcps: dict[str, Any] = json.load(f)
        elif legacy_file.exists():
            with open(legacy_file) as f:
                base_mcps = json.load(f)
        else:
            return {}

        mcp_overrides = config.mcp_overrides if hasattr(config, "mcp_overrides") else {}

        merged_mcps: dict[str, Any] = {}
        for name in {**base_mcps, **mcp_overrides}:
            if name in base_mcps and name in mcp_overrides:
                merged_mcps[name] = deep_merge(base_mcps[name], mcp_overrides[name])
            elif name in base_mcps:
                merged_mcps[name] = copy.deepcopy(base_mcps[name])
            else:
                merged_mcps[name] = copy.deepcopy(mcp_overrides[name])

        return merged_mcps

    def detect_conflicts(
        self, expected: dict[str, Any], installed: dict[str, Any]
    ) -> list[str]:
        """Detect MCPs that have been modified locally."""
        conflicts = []
        marker = self._marker_field
        for name, expected_config in expected.items():
            if name in installed:
                expected_clean = {
                    k: v for k, v in expected_config.items() if k != marker
                }
                installed_clean = {
                    k: v for k, v in installed[name].items() if k != marker
                }
                if expected_clean != installed_clean:
                    conflicts.append(name)
        return conflicts

    def format_diff(
        self, name: str, expected: dict[str, Any], installed: dict[str, Any]
    ) -> str:
        """Format a unified diff between expected and installed MCP config."""
        import difflib

        expected_json = json.dumps(expected, indent=2)
        installed_json = json.dumps(installed, indent=2)

        diff = difflib.unified_diff(
            expected_json.splitlines(keepends=True),
            installed_json.splitlines(keepends=True),
            fromfile="Expected (repo)",
            tofile="Installed (local)",
            lineterm="",
        )

        return f"MCP '{name}' has been modified locally:\n" + "".join(diff)

    def format_pending(self, name: str, expected: dict[str, Any]) -> str:
        """Format expected MCP config for pending installation."""
        marker = self._marker_field
        display_config = {k: v for k, v in expected.items() if k != marker}
        config_json = json.dumps(display_config, indent=2)

        lines = ["[dim]    Will be installed with:[/dim]"]
        for line in config_json.splitlines():
            lines.append(f"[green]    {line}[/green]")
        return "\n".join(lines)

    def _create_backup(self, target: Path) -> Path | None:
        """Create a timestamped backup of a config file."""
        if not target.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = target.with_suffix(
            f"{target.suffix}.{self.BACKUP_SUFFIX}.{timestamp}"
        )
        shutil.copy2(target, backup_path)
        return backup_path

    def _target_path(self) -> Path:
        """Return the agent config file path (used for backups by subclasses)."""
        raise NotImplementedError

    def install_mcps(
        self,
        config_dir: Path,
        config: Config,
        force: bool = False,
        dry_run: bool = False,
    ) -> tuple[OperationResult, str, list[str]]:
        """Install managed MCPs into the agent's config file."""
        native_mcps = self.get_native_mcps(config_dir, config)

        current_mcps = self._read_installed()
        original_mcps = copy.deepcopy(current_mcps)

        tracked_mcps = {
            name
            for name, cfg in current_mcps.items()
            if is_managed_value(cfg.get(self._marker_field))
        }
        removed_mcps = tracked_mcps - set(native_mcps.keys())

        if not native_mcps and not removed_mcps:
            return (OperationResult.NOT_FOUND, "No MCPs to install or remove", [])

        conflicts = self.detect_conflicts(native_mcps, current_mcps)

        if conflicts and not force:
            return (
                OperationResult.ERROR,
                "Conflicts detected (use -y to override)",
                conflicts,
            )

        if dry_run:
            msg = f"Would update {len(native_mcps)} MCPs, remove {len(removed_mcps)}"
            return (OperationResult.UPDATED, msg, conflicts)

        for name in removed_mcps:
            current_mcps.pop(name, None)

        current_mcps.update(native_mcps)

        if current_mcps == original_mcps:
            return (OperationResult.ALREADY_INSTALLED, "MCPs already up to date", [])

        self._write_installed(current_mcps)

        parts = []
        if native_mcps:
            parts.append(f"installed {len(native_mcps)}")
        if removed_mcps:
            parts.append(f"removed {len(removed_mcps)}")
        msg = f"MCPs {', '.join(parts)}"

        return (OperationResult.UPDATED, msg, [])

    def uninstall_mcps(
        self, force: bool = False, dry_run: bool = False
    ) -> tuple[OperationResult, str]:
        """Uninstall managed MCPs from the agent's config file."""
        current_mcps = self._read_installed()

        tracked_mcps = {
            name
            for name, cfg in current_mcps.items()
            if is_managed_value(cfg.get(self._marker_field))
        }

        if not tracked_mcps:
            return (OperationResult.NOT_FOUND, "No tracked MCPs found")

        if dry_run:
            return (
                OperationResult.REMOVED,
                f"Would remove {len(tracked_mcps)} MCPs (dry run)",
            )

        for name in tracked_mcps:
            current_mcps.pop(name, None)

        self._write_installed(current_mcps)

        return (OperationResult.REMOVED, f"Removed {len(tracked_mcps)} MCPs")

    def get_status(self, config_dir: Path, config: Config) -> MCPStatus:
        """Get status of managed and unmanaged MCPs."""
        status = MCPStatus()
        managed_mcps = self.load_managed_mcps(config_dir, config)

        native_mcps: dict[str, Any] = {}
        for name, shared_cfg in managed_mcps.items():
            translated = self._translate(shared_cfg)
            translated[self._marker_field] = MANAGED_BY_VALUE
            native_mcps[name] = translated

        installed_mcps = self._read_installed()
        mcp_overrides = config.mcp_overrides if hasattr(config, "mcp_overrides") else {}
        marker = self._marker_field

        for name, mcp_config in installed_mcps.items():
            if is_managed_value(mcp_config.get(marker)):
                if name in native_mcps:
                    status.managed_mcps[name] = mcp_config
                    expected_clean = {
                        k: v for k, v in native_mcps[name].items() if k != marker
                    }
                    installed_clean = {
                        k: v for k, v in mcp_config.items() if k != marker
                    }
                    status.installed[name] = expected_clean == installed_clean
                    status.has_overrides[name] = name in mcp_overrides
                else:
                    status.stale_mcps[name] = mcp_config
            else:
                status.unmanaged_mcps[name] = mcp_config

        for name, mcp_config in native_mcps.items():
            if name not in installed_mcps:
                status.pending_mcps[name] = mcp_config
                status.has_overrides[name] = name in mcp_overrides

        return status


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


class ClaudeMCPManager(MCPManager):
    """Manages MCPs in ~/.claude.json under the mcpServers key."""

    @property
    def _marker_field(self) -> str:
        return "_managedBy"

    @property
    def _claude_json_path(self) -> Path:
        return Path.home() / ".claude.json"

    def _target_path(self) -> Path:
        return self._claude_json_path

    def _read_installed(self) -> dict[str, Any]:
        if not self._claude_json_path.exists():
            return {}
        with open(self._claude_json_path) as f:
            data: dict[str, Any] = json.load(f)
        return cast(dict[str, Any], data.get("mcpServers", {}))

    def _write_installed(self, mcps: dict[str, Any]) -> None:
        self._claude_json_path.parent.mkdir(parents=True, exist_ok=True)

        if self._claude_json_path.exists():
            with open(self._claude_json_path) as f:
                data: dict[str, Any] = json.load(f)
        else:
            data = {}

        data.setdefault("mcpServers", {})
        data["mcpServers"] = mcps

        self._write_json_atomic(self._claude_json_path, data)

    def _translate(self, shared_config: dict[str, Any]) -> dict[str, Any]:
        return {
            k: v for k, v in shared_config.items() if k not in ("description", "name")
        }

    def _write_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with open(fd, "w") as f:
                json.dump(data, f, indent=2)
            if path.exists():
                shutil.copystat(path, temp_path)
            shutil.move(temp_path, path)
        except Exception:
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

    # Preserve the claude_json cached-property interface used in cli.py
    @property
    def claude_json(self) -> dict[str, Any]:
        if not self._claude_json_path.exists():
            return {}
        with open(self._claude_json_path) as f:
            return cast(dict[str, Any], json.load(f))

    # Backward-compat alias so existing cli.py code still works
    @property
    def CLAUDE_JSON(self) -> Path:
        return self._claude_json_path

    def install_mcps(
        self,
        config_dir: Path,
        config: Config,
        force: bool = False,
        dry_run: bool = False,
    ) -> tuple[OperationResult, str, list[str]]:
        """Install MCPs, creating a timestamped backup of ~/.claude.json first."""
        if not dry_run and self._claude_json_path.exists():
            self._create_backup(self._claude_json_path)
        result, msg, conflicts = super().install_mcps(
            config_dir, config, force, dry_run
        )
        return result, msg, conflicts

    def uninstall_mcps(
        self, force: bool = False, dry_run: bool = False
    ) -> tuple[OperationResult, str]:
        if not dry_run:
            backup = self._create_backup(self._claude_json_path)
            result, msg = super().uninstall_mcps(force, dry_run)
            if backup:
                msg += f" (backup: {backup})"
            return result, msg
        return super().uninstall_mcps(force, dry_run)


# ---------------------------------------------------------------------------
# Goose
# ---------------------------------------------------------------------------


class GooseMCPManager(MCPManager):
    """Manages MCPs in ~/.config/goose/config.yaml under the extensions key."""

    @property
    def _marker_field(self) -> str:
        return "_managed_by"

    @property
    def mcp_settings_key(self) -> str | None:
        return "extensions"

    @property
    def _config_path(self) -> Path:
        return Path.home() / ".config" / "goose" / "config.yaml"

    def _target_path(self) -> Path:
        return self._config_path

    def _load_full_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with open(self._config_path) as f:
            result = yaml.safe_load(f)
        return cast(dict[str, Any], result) if result else {}

    def _read_installed(self) -> dict[str, Any]:
        full = self._load_full_config()
        extensions = full.get("extensions", {})
        if not isinstance(extensions, dict):
            return {}
        return cast(dict[str, Any], extensions)

    def _write_installed(self, mcps: dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        full = self._load_full_config()
        full["extensions"] = mcps
        with open(self._config_path, "w") as f:
            yaml.safe_dump(full, f, default_flow_style=False, sort_keys=False)

    def _translate(self, shared_config: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "stdio",
            "cmd": shared_config.get("command", ""),
            "args": shared_config.get("args", []),
            "envs": shared_config.get("env", {}),
            "env_keys": [],
            "enabled": True,
            "name": shared_config.get("name", ""),
            "description": shared_config.get("description", ""),
            "timeout": 300,
            "bundled": False,
            "available_tools": [],
        }


# ---------------------------------------------------------------------------
# Codex
# ---------------------------------------------------------------------------


class CodexMCPManager(MCPManager):
    """Manages MCPs in ~/.codex/config.toml under the mcp_servers section.

    Uses tomlkit for round-trip editing so non-MCP keys (approval_policy,
    trust_level, model) and comments are preserved.

    The managed-names list is stored in a dedicated TOML section
    because TOML inline per-table markers are awkward.
    """

    _MANAGED_SECTION = "_ai_agent_rules_managed"
    _LEGACY_MANAGED_SECTION = "_ai_rules_managed"

    @property
    def _marker_field(self) -> str:
        return "_ai_agent_rules_managed_entry"

    @property
    def mcp_settings_key(self) -> str | None:
        return "mcp_servers"

    @property
    def mcp_tracking_key(self) -> str | None:
        return self._MANAGED_SECTION

    @property
    def _config_path(self) -> Path:
        return Path.home() / ".codex" / "config.toml"

    def _target_path(self) -> Path:
        return self._config_path

    def _load_doc(self) -> Any:
        import tomlkit

        if not self._config_path.exists():
            return tomlkit.document()
        with open(self._config_path) as f:
            return tomlkit.load(f)

    def _get_managed_names(self, doc: Any) -> set[str]:
        section = doc.get(self._MANAGED_SECTION) or doc.get(
            self._LEGACY_MANAGED_SECTION, {}
        )
        names = section.get("names", [])
        return set(names) if isinstance(names, list) else set()

    def _read_installed(self) -> dict[str, Any]:
        import tomlkit

        doc = self._load_doc()
        managed_names = self._get_managed_names(doc)
        mcp_servers = doc.get("mcp_servers", tomlkit.table())
        if not isinstance(mcp_servers, dict):
            return {}

        result: dict[str, Any] = {}
        for name, cfg in mcp_servers.items():
            entry = dict(cfg) if hasattr(cfg, "items") else {}
            if name in managed_names:
                entry[self._marker_field] = MANAGED_BY_VALUE
            result[name] = entry
        return result

    def _write_installed(self, mcps: dict[str, Any]) -> None:
        import tomlkit

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        doc = self._load_doc()

        managed_names: list[str] = []
        mcp_table = tomlkit.table()

        for name, cfg in mcps.items():
            is_managed = is_managed_value(cfg.get(self._marker_field))
            entry = tomlkit.table()
            for k, v in cfg.items():
                if k == self._marker_field:
                    continue
                if isinstance(v, dict):
                    sub = tomlkit.table()
                    for sk, sv in v.items():
                        sub[sk] = sv
                    entry[k] = sub
                else:
                    entry[k] = v
            mcp_table[name] = entry
            if is_managed:
                managed_names.append(name)

        doc["mcp_servers"] = mcp_table

        mgmt_section = tomlkit.table()
        mgmt_section["names"] = managed_names
        doc[self._MANAGED_SECTION] = mgmt_section

        if self._LEGACY_MANAGED_SECTION in doc:
            del doc[self._LEGACY_MANAGED_SECTION]

        with open(self._config_path, "w") as f:
            f.write(tomlkit.dumps(doc))

    def _translate(self, shared_config: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "command" in shared_config:
            result["command"] = shared_config["command"]
        if "args" in shared_config:
            result["args"] = shared_config["args"]
        if "env" in shared_config:
            result["env"] = shared_config["env"]
        return result

    def detect_conflicts(
        self, expected: dict[str, Any], installed: dict[str, Any]
    ) -> list[str]:
        """Conflict detection strips the per-entry marker added during read."""
        marker = self._marker_field
        conflicts = []
        for name, expected_config in expected.items():
            if name in installed:
                expected_clean = {
                    k: v for k, v in expected_config.items() if k != marker
                }
                installed_clean = {
                    k: v for k, v in installed[name].items() if k != marker
                }
                if expected_clean != installed_clean:
                    conflicts.append(name)
        return conflicts


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


class GeminiMCPManager(MCPManager):
    """Manages MCPs in ~/.gemini/settings.json under the mcpServers key."""

    @property
    def _marker_field(self) -> str:
        return "_managedBy"

    @property
    def mcp_settings_key(self) -> str | None:
        return "mcpServers"

    @property
    def _config_path(self) -> Path:
        return Path.home() / ".gemini" / "settings.json"

    def _target_path(self) -> Path:
        return self._config_path

    def _load_full_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with open(self._config_path) as f:
            data: dict[str, Any] = json.load(f)
        return data

    def _read_installed(self) -> dict[str, Any]:
        full = self._load_full_config()
        return cast(dict[str, Any], full.get("mcpServers", {}))

    def _write_installed(self, mcps: dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        full = self._load_full_config()
        full["mcpServers"] = mcps

        fd, temp_path = tempfile.mkstemp(
            dir=self._config_path.parent, prefix=f".{self._config_path.name}."
        )
        try:
            with open(fd, "w") as f:
                json.dump(full, f, indent=2)
            if self._config_path.exists():
                shutil.copystat(self._config_path, temp_path)
            shutil.move(temp_path, self._config_path)
        except Exception:
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

    def _translate(self, shared_config: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "command" in shared_config:
            result["command"] = shared_config["command"]
        if "args" in shared_config:
            result["args"] = shared_config["args"]
        if "env" in shared_config:
            result["env"] = shared_config["env"]
        result["timeout"] = 30000
        result["trust"] = False
        return result


# ---------------------------------------------------------------------------
# Amp
# ---------------------------------------------------------------------------


class AmpMCPManager(MCPManager):
    """Manages MCPs in ~/.config/amp/settings.json under the amp.mcpServers key."""

    @property
    def _marker_field(self) -> str:
        return "_managedBy"

    @property
    def mcp_settings_key(self) -> str | None:
        return "amp.mcpServers"

    @property
    def _config_path(self) -> Path:
        return Path.home() / ".config" / "amp" / "settings.json"

    def _target_path(self) -> Path:
        return self._config_path

    def _load_full_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with open(self._config_path) as f:
            data: dict[str, Any] = json.load(f)
        return data

    def _read_installed(self) -> dict[str, Any]:
        full = self._load_full_config()
        return cast(dict[str, Any], full.get("amp.mcpServers", {}))

    def _write_installed(self, mcps: dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        full = self._load_full_config()
        full["amp.mcpServers"] = mcps

        fd, temp_path = tempfile.mkstemp(
            dir=self._config_path.parent, prefix=f".{self._config_path.name}."
        )
        try:
            with open(fd, "w") as f:
                json.dump(full, f, indent=2)
            if self._config_path.exists():
                shutil.copystat(self._config_path, temp_path)
            shutil.move(temp_path, self._config_path)
        except Exception:
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

    def _translate(self, shared_config: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "command" in shared_config:
            result["command"] = shared_config["command"]
        if "args" in shared_config:
            result["args"] = shared_config["args"]
        if "env" in shared_config:
            result["env"] = shared_config["env"]
        return result
