"""Tests for tool installation utilities."""

import subprocess
import sys

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_rules.bootstrap.installer import (
    UV_NOT_FOUND_ERROR,
    ToolSource,
    _is_basic_memory_configured,
    ensure_basic_memory_installed,
    get_effective_install_source,
    get_tool_config_dir,
    get_tool_source,
    install_tool,
    uninstall_tool,
)


@pytest.mark.unit
@pytest.mark.bootstrap
class TestInstallTool:
    """Tests for install_tool function."""

    def test_install_without_uv_returns_error(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: False
        )
        success, message = install_tool("test-package")
        assert success is False
        assert message == UV_NOT_FOUND_ERROR

    def test_install_pypi_package(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        captured_args = []

        def mock_run(*args, **kwargs):
            captured_args.append((args, kwargs))

            class Result:
                returncode = 0
                stderr = ""
                stdout = ""

            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)
        success, message = install_tool("test-package")
        assert success is True
        assert message == "Installation successful"
        assert len(captured_args) == 1
        call_args = captured_args[0][0][0]
        assert "uv" in call_args
        assert "tool" in call_args
        assert "install" in call_args
        assert "test-package" in call_args

    def test_install_with_force_flag(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        captured_args = []

        def mock_run(*args, **kwargs):
            captured_args.append((args, kwargs))

            class Result:
                returncode = 0
                stderr = ""
                stdout = ""

            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)
        success, message = install_tool("test-package", force=True)
        assert success is True
        assert len(captured_args) == 1
        call_args = captured_args[0][0][0]
        assert "--force" in call_args

    def test_install_dry_run(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        success, message = install_tool("test-package", dry_run=True)
        assert success is True
        assert "Would run:" in message

    @pytest.mark.parametrize(
        "error_type,expected_message",
        [
            ("timeout", "timed out"),
            ("command_failure", "package not found"),
            ("empty_error", "failed"),
            ("unexpected", "unexpected error"),
        ],
    )
    def test_install_handles_errors(self, monkeypatch, error_type, expected_message):
        """Test that install handles various error conditions gracefully."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            if error_type == "timeout":
                raise subprocess.TimeoutExpired("uv", 60)
            elif error_type == "command_failure":

                class CommandFailureResult:
                    returncode = 1
                    stderr = "Installation failed: package not found"
                    stdout = ""

                return CommandFailureResult()
            elif error_type == "empty_error":

                class EmptyErrorResult:
                    returncode = 1
                    stderr = ""
                    stdout = ""

                return EmptyErrorResult()
            elif error_type == "unexpected":
                raise ValueError("Unexpected error")

        monkeypatch.setattr("subprocess.run", mock_run)
        success, message = install_tool("test-package")
        assert success is False
        assert expected_message in message.lower()


@pytest.mark.unit
@pytest.mark.bootstrap
class TestUninstallTool:
    """Tests for uninstall_tool function."""

    def test_uninstall_without_uv_returns_error(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: False
        )
        success, message = uninstall_tool("test-package")
        assert success is False
        assert message == UV_NOT_FOUND_ERROR

    def test_uninstall_package(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        captured_args = []

        def mock_run(*args, **kwargs):
            captured_args.append((args, kwargs))

            class Result:
                returncode = 0
                stderr = ""
                stdout = ""

            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)
        success, message = uninstall_tool("test-package")
        assert success is True
        assert message == "Uninstallation successful"
        assert len(captured_args) == 1
        call_args = captured_args[0][0][0]
        assert "uv" in call_args
        assert "tool" in call_args
        assert "uninstall" in call_args
        assert "test-package" in call_args

    @pytest.mark.parametrize(
        "error_type,expected_message",
        [
            ("timeout", "timed out"),
            ("command_failure", "package not installed"),
            ("empty_error", "failed"),
            ("unexpected", "unexpected error"),
        ],
    )
    def test_uninstall_handles_errors(self, monkeypatch, error_type, expected_message):
        """Test that uninstall handles various error conditions gracefully."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            if error_type == "timeout":
                raise subprocess.TimeoutExpired("uv", 30)
            elif error_type == "command_failure":

                class CommandFailureResult:
                    returncode = 1
                    stderr = "Package not installed"
                    stdout = ""

                return CommandFailureResult()
            elif error_type == "empty_error":

                class EmptyErrorResult:
                    returncode = 1
                    stderr = ""
                    stdout = ""

                return EmptyErrorResult()
            elif error_type == "unexpected":
                raise ValueError("Unexpected error")

        monkeypatch.setattr("subprocess.run", mock_run)
        success, message = uninstall_tool("test-package")
        assert success is False
        assert expected_message in message.lower()


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetToolConfigDir:
    """Tests for get_tool_config_dir function."""

    def test_returns_expected_path_structure(self):
        """Test that get_tool_config_dir returns correct path structure."""
        result = get_tool_config_dir("ai-agent-rules")
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

        path_str = str(result)
        assert "uv/tools/ai-agent-rules" in path_str
        assert python_version in path_str
        assert path_str.endswith("ai_rules/config")

    def test_respects_xdg_data_home(self, monkeypatch, tmp_path):
        """Test that XDG_DATA_HOME environment variable is respected."""
        custom_data_home = tmp_path / "custom_data"
        monkeypatch.setenv("XDG_DATA_HOME", str(custom_data_home))

        result = get_tool_config_dir("ai-agent-rules")

        assert str(result).startswith(str(custom_data_home))
        assert "uv/tools/ai-agent-rules" in str(result)

    def test_uses_default_data_home_when_xdg_not_set(self, monkeypatch):
        """Test that ~/.local/share is used when XDG_DATA_HOME is not set."""
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)

        result = get_tool_config_dir("ai-agent-rules")

        path_str = str(result)
        assert ".local/share" in path_str or ".local\\share" in path_str

    def test_custom_package_name(self):
        """Test that custom package names are handled correctly."""
        result = get_tool_config_dir("my-custom-package")

        assert "my-custom-package" in str(result)
        assert "ai_rules/config" in str(result)


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetToolSource:
    """Tests for get_tool_source function."""

    def test_detects_pypi_installation(self, tmp_path, monkeypatch):
        """Test that PyPI installations are detected."""
        tools_dir = tmp_path / "uv" / "tools" / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", version = "1.0.0" }]\n'
        )

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        result = get_tool_source("test-package")
        assert result == ToolSource.PYPI

    def test_returns_none_when_not_installed(self, tmp_path, monkeypatch):
        """Test that None is returned for tools that aren't installed."""
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        result = get_tool_source("nonexistent-package")
        assert result is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestInstallToolGithub:
    """Tests for install_tool with from_github=True."""

    def test_install_from_github_requires_github_url(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        with pytest.raises(ValueError, match="github_url is required"):
            install_tool("some-package", from_github=True)

    def test_install_from_github_with_url(self, monkeypatch):
        captured = []

        def mock_run(cmd, **kwargs):
            captured.append(cmd)

            class Result:
                returncode = 0
                stderr = ""
                stdout = ""

            return Result()

        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr("subprocess.run", mock_run)
        success, _ = install_tool(
            "some-package",
            from_github=True,
            github_url="git+ssh://git@github.com/owner/repo.git",
        )
        assert success is True
        assert "git+ssh://git@github.com/owner/repo.git" in captured[0]

    def test_install_from_github_dry_run(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        success, message = install_tool(
            "some-package",
            from_github=True,
            github_url="git+ssh://git@github.com/owner/repo.git",
            dry_run=True,
        )
        assert success is True
        assert "git+ssh://git@github.com/owner/repo.git" in message


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetEffectiveInstallSource:
    """Tests for get_effective_install_source resolver."""

    def test_cli_flag_always_wins(self, monkeypatch):
        """CLI --github flag overrides everything — no config lookup needed."""
        # No mocking needed: cli_github_flag=True returns True immediately
        assert get_effective_install_source("statusline", cli_github_flag=True) is True

    def test_config_github_wins_without_cli_flag(self, monkeypatch):
        """Persisted 'github' config wins when CLI flag is False."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = "github"
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        assert get_effective_install_source("statusline", cli_github_flag=False) is True

    def test_config_pypi_beats_default(self, monkeypatch):
        """Persisted 'pypi' config returns False even without CLI flag."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = "pypi"
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        assert (
            get_effective_install_source("statusline", cli_github_flag=False) is False
        )

    def test_defaults_to_pypi_when_nothing_configured(self, monkeypatch):
        """Falls back to False (PyPI) when no config and no CLI flag."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = None
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        assert get_effective_install_source("statusline") is False

    def test_config_load_failure_falls_back_to_pypi(self, monkeypatch):
        """Config load failure is silently ignored and defaults to PyPI."""
        from ai_rules.config import Config

        def _raise(*args, **kwargs):
            raise RuntimeError("config broke")

        monkeypatch.setattr(Config, "load", _raise)
        assert get_effective_install_source("statusline") is False


@pytest.mark.unit
@pytest.mark.bootstrap
class TestIsBasicMemoryConfigured:
    """Tests for _is_basic_memory_configured helper."""

    def test_returns_true_when_in_mcp_overrides(self):
        config = SimpleNamespace(
            mcp_overrides={"basic-memory": {"command": "/bin/bash"}}
        )
        assert _is_basic_memory_configured(config) is True

    def test_returns_false_when_mcp_overrides_empty(self, monkeypatch):
        import importlib.resources

        config = SimpleNamespace(mcp_overrides={})
        monkeypatch.setattr(
            importlib.resources,
            "files",
            lambda pkg: _MockTraversable({}),
        )
        assert _is_basic_memory_configured(config) is False

    def test_returns_false_when_no_mcp_overrides_attr(self, monkeypatch):
        import importlib.resources

        config = SimpleNamespace()
        monkeypatch.setattr(
            importlib.resources,
            "files",
            lambda pkg: _MockTraversable({}),
        )
        assert _is_basic_memory_configured(config) is False


@pytest.mark.unit
@pytest.mark.bootstrap
class TestEnsureBasicMemoryInstalled:
    """Tests for ensure_basic_memory_installed function."""

    def test_skips_when_not_configured(self, monkeypatch):
        config = SimpleNamespace(mcp_overrides={})
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer._is_basic_memory_configured",
            lambda c: False,
        )
        status, msg = ensure_basic_memory_installed(config=config)
        assert status == "skipped"
        assert msg is None

    def test_returns_already_installed_when_available(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer._is_basic_memory_configured",
            lambda c: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available",
            lambda cmd: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer._run_basic_memory_setup",
            lambda **kw: None,
        )

        from ai_rules.bootstrap import updater

        monkeypatch.setattr(
            updater,
            "get_tool_by_id",
            lambda tid: None,
        )
        status, msg = ensure_basic_memory_installed(
            config=SimpleNamespace(mcp_overrides={"basic-memory": {}})
        )
        assert status == "already_installed"

    def test_setup_called_on_fresh_install(self, monkeypatch):
        setup_calls = []
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer._is_basic_memory_configured",
            lambda c: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available",
            lambda cmd: cmd != "basic-memory",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer._run_basic_memory_setup",
            lambda **kw: setup_calls.append(kw),
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.install_tool",
            lambda *a, **kw: (True, "ok"),
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.make_github_install_url",
            lambda repo: f"https://github.com/{repo}",
        )
        status, msg = ensure_basic_memory_installed(
            config=SimpleNamespace(mcp_overrides={"basic-memory": {}})
        )
        assert status == "installed"
        assert len(setup_calls) == 1
        assert setup_calls[0].get("verbose") is True


class _MockTraversable:
    """Mock for importlib.resources traversable that returns empty mcps.json."""

    def __init__(self, data: dict):
        self._data = data

    def __truediv__(self, other):
        return _MockTraversable(self._data)

    def is_file(self):
        return True

    def read_text(self):
        import json

        return json.dumps(self._data)
