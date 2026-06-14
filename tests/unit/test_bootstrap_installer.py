"""Tests for tool installation utilities."""

import subprocess
import sys

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_rules.bootstrap.installer import (
    UV_NOT_FOUND_ERROR,
    ToolSource,
    ensure_tool_installed,
    ensure_tool_uninstalled,
    get_effective_install_source,
    get_tool_config_dir,
    get_tool_source,
    get_tool_version,
    install_tool,
    uninstall_tool,
)
from ai_rules.bootstrap.updater import ToolSpec


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

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

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

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

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

    def test_install_from_local_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        captured = []

        def mock_run(cmd, **kwargs):
            captured.append(cmd)

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr("subprocess.run", mock_run)
        success, _ = install_tool("some-package", local_path=str(tmp_path))
        assert success is True
        assert str(tmp_path) in captured[0][-1] or str(tmp_path.resolve()) in " ".join(
            captured[0]
        )

    def test_local_path_skips_package_name_validation(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        captured = []

        def mock_run(cmd, **kwargs):
            captured.append(cmd)

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr("subprocess.run", mock_run)
        success, _ = install_tool("this-is-invalid!!!name", local_path=str(tmp_path))
        assert success is True

    def test_local_path_takes_priority_over_github(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        captured = []

        def mock_run(cmd, **kwargs):
            captured.append(cmd)

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr("subprocess.run", mock_run)
        success, _ = install_tool(
            "some-package",
            from_github=True,
            github_url="git+ssh://git@github.com/owner/repo.git",
            local_path=str(tmp_path),
        )
        assert success is True
        cmd_str = " ".join(captured[0])
        assert str(tmp_path.resolve()) in cmd_str
        assert "github.com" not in cmd_str


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

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

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

    def test_returns_expected_path_structure(self, monkeypatch):
        """Test that get_tool_config_dir returns correct path structure."""
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        result = get_tool_config_dir("ai-agent-rules")
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

        path_posix = result.as_posix()
        assert "uv/tools/ai-agent-rules" in path_posix
        assert python_version in path_posix
        assert path_posix.endswith("ai_rules/config")

    def test_respects_xdg_data_home(self, monkeypatch, tmp_path):
        """Test that XDG_DATA_HOME environment variable is respected."""
        custom_data_home = tmp_path / "custom_data"
        monkeypatch.setenv("XDG_DATA_HOME", str(custom_data_home))
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)

        result = get_tool_config_dir("ai-agent-rules")

        assert result.as_posix().startswith(custom_data_home.as_posix())
        assert "uv/tools/ai-agent-rules" in result.as_posix()

    def test_uses_default_data_home_when_xdg_not_set(self, monkeypatch):
        """Test that ~/.local/share is used when XDG_DATA_HOME is not set."""
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)

        result = get_tool_config_dir("ai-agent-rules")

        assert ".local/share" in result.as_posix()

    def test_custom_package_name(self, monkeypatch):
        """Test that custom package names are handled correctly."""
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        result = get_tool_config_dir("my-custom-package")

        assert "my-custom-package" in result.as_posix()
        assert "ai_rules/config" in result.as_posix()

    def test_discovers_actual_python_version_via_glob(self, tmp_path, monkeypatch):
        """Test that get_tool_config_dir finds the actual Python version dir."""
        config_dir = (
            tmp_path
            / "test-pkg"
            / "lib"
            / "python3.99"
            / "site-packages"
            / "ai_rules"
            / "config"
        )
        config_dir.mkdir(parents=True)

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_config_dir("test-pkg")
        assert result == config_dir


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetToolSource:
    """Tests for get_tool_source function."""

    def test_detects_pypi_installation(self, tmp_path, monkeypatch):
        """Test that PyPI installations are detected."""
        tools_dir = tmp_path / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", version = "1.0.0" }]\n'
        )

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("test-package")
        assert result == ToolSource.PYPI

    def test_returns_none_when_not_installed(self, tmp_path, monkeypatch):
        """Test that None is returned for tools that aren't installed."""
        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("nonexistent-package")
        assert result is None

    def test_detects_local_installation(self, tmp_path, monkeypatch):
        """Test that local path installations are detected."""
        tools_dir = tmp_path / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", path = "/home/user/dev/test-package" }]\n'
        )

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("test-package")
        assert result == ToolSource.LOCAL

    def test_detects_local_directory_installation(self, tmp_path, monkeypatch):
        """Test that local directory installations are detected."""
        tools_dir = tmp_path / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", directory = "/home/user/dev/test-package" }]\n'
        )

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("test-package")
        assert result == ToolSource.LOCAL

    def test_detects_editable_installation(self, tmp_path, monkeypatch):
        """Test that editable installations are detected as LOCAL."""
        tools_dir = tmp_path / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", editable = "/home/user/dev/test-package" }]\n'
        )

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("test-package")
        assert result == ToolSource.LOCAL

    def test_detects_github_git_installation(self, tmp_path, monkeypatch):
        """Test that GitHub git installations are detected."""
        tools_dir = tmp_path / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", git = "ssh://git@github.com/owner/repo.git" }]\n'
        )

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("test-package")
        assert result == ToolSource.GITHUB

    def test_non_github_git_falls_through_to_pypi(self, tmp_path, monkeypatch):
        """Test that non-GitHub git installations fall through to PYPI."""
        tools_dir = tmp_path / "test-package"
        tools_dir.mkdir(parents=True)
        receipt = tools_dir / "uv-receipt.toml"
        receipt.write_text(
            '[tool]\nrequirements = [{ name = "test-package", git = "ssh://git@gitlab.com/owner/repo.git" }]\n'
        )

        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_tool_source("test-package")
        assert result == ToolSource.PYPI


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetToolVersion:
    """Tests for get_tool_version function."""

    def test_exact_match_not_prefix(self, monkeypatch):
        """Test that tool name must match exactly, not as a prefix."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )

        result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="ai-agent-rules-extra v0.1.0\n  - ai-agent-rules-extra\nai-agent-rules v0.62.4\n  - ai-agent-rules\n",
            stderr="",
        )
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: result)
        version = get_tool_version("ai-agent-rules")
        assert version == "0.62.4"


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

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

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

    def test_cli_flag_returns_github(self, monkeypatch):
        """CLI --github flag overrides everything."""
        source, local_path = get_effective_install_source(
            "statusline", cli_github_flag=True
        )
        assert source == ToolSource.GITHUB
        assert local_path is None

    def test_config_github_returns_github(self, monkeypatch):
        """Persisted 'github' config returns GITHUB."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = "github"
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        source, local_path = get_effective_install_source(
            "statusline", cli_github_flag=False
        )
        assert source == ToolSource.GITHUB
        assert local_path is None

    def test_config_pypi_returns_pypi(self, monkeypatch):
        """Persisted 'pypi' config returns PYPI."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = "pypi"
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        source, local_path = get_effective_install_source(
            "statusline", cli_github_flag=False
        )
        assert source == ToolSource.PYPI
        assert local_path is None

    def test_config_local_returns_local_with_path(self, monkeypatch):
        """Persisted 'local:~/path' config returns LOCAL with the path."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = (
            "local:~/Development/example-tool"
        )
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        source, local_path = get_effective_install_source("example-tool")
        assert source == ToolSource.LOCAL
        assert local_path == "~/Development/example-tool"

    def test_passed_config_is_used_without_loading_active_profile(self, monkeypatch):
        """An explicit config avoids active-profile source lookups."""
        from ai_rules.config import Config

        def _raise(*args, **kwargs):
            raise RuntimeError("should not load active profile")

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = (
            "local:~/Development/example-tool"
        )
        monkeypatch.setattr(Config, "load", _raise)

        source, local_path = get_effective_install_source(
            "example-tool", config=mock_config
        )

        assert source == ToolSource.LOCAL
        assert local_path == "~/Development/example-tool"

    def test_defaults_to_pypi_when_nothing_configured(self, monkeypatch):
        """Falls back to PYPI when no config and no CLI flag."""
        from ai_rules.config import Config

        mock_config = MagicMock()
        mock_config.get_tool_install_source.return_value = None
        monkeypatch.setattr(Config, "load", lambda *a, **kw: mock_config)
        source, local_path = get_effective_install_source("statusline")
        assert source == ToolSource.PYPI
        assert local_path is None

    def test_config_load_failure_falls_back_to_pypi(self, monkeypatch):
        """Config load failure is silently ignored and defaults to PyPI."""
        from ai_rules.config import Config

        def _raise(*args, **kwargs):
            raise RuntimeError("config broke")

        monkeypatch.setattr(Config, "load", _raise)
        source, local_path = get_effective_install_source("statusline")
        assert source == ToolSource.PYPI
        assert local_path is None


def _make_spec(installed: bool = True) -> ToolSpec:
    return ToolSpec(
        tool_id="test-tool",
        package_name="test-pkg",
        display_name="Test Tool",
        get_version=lambda: "0.1.0",
        is_installed=lambda: installed,
        github_repo="owner/test-tool",
        is_enabled=lambda: True,
    )


@pytest.mark.unit
@pytest.mark.bootstrap
class TestEnsureToolInstalled:
    """Tests for ensure_tool_installed function."""

    def test_already_installed_no_update_returns_already_installed(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_tool_updates",
            lambda spec, timeout=10: None,
        )
        result = ensure_tool_installed(_make_spec(installed=True))
        assert result == ("already_installed", None)

    def test_fresh_install_success_returns_installed(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.install_tool",
            lambda *args, **kwargs: (True, "ok"),
        )
        result = ensure_tool_installed(_make_spec(installed=False))
        assert result == ("installed", None)

    def test_fresh_install_failure_returns_failed(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.install_tool",
            lambda *args, **kwargs: (False, "err"),
        )
        result = ensure_tool_installed(_make_spec(installed=False))
        assert result == ("failed", None)

    def test_local_source_reinstall_returns_upgraded(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.install_tool",
            lambda *args, **kwargs: (True, "ok"),
        )
        result = ensure_tool_installed(
            _make_spec(installed=True),
            source=ToolSource.LOCAL,
            local_path="/tmp/test",
        )
        assert result == ("upgraded", "reinstalled from local path")

    def test_local_source_failure_returns_failed(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.install_tool",
            lambda *args, **kwargs: (False, "err"),
        )
        result = ensure_tool_installed(
            _make_spec(installed=True),
            source=ToolSource.LOCAL,
            local_path="/tmp/test",
        )
        assert result == ("failed", None)

    def test_upgrade_available_dry_run(self, monkeypatch):
        update_info = SimpleNamespace(
            has_update=True,
            check_failed=False,
            current_version="0.1.0",
            latest_version="0.2.0",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_tool_updates",
            lambda spec, timeout=10: update_info,
        )
        status, message = ensure_tool_installed(
            _make_spec(installed=True),
            dry_run=True,
        )
        assert status == "upgrade_available"
        assert message is not None
        assert "0.1.0" in message
        assert "0.2.0" in message

    def test_skip_update_check_returns_already_installed(self, monkeypatch):
        called: list[bool] = []

        def _tracking_stub(spec: object, timeout: int = 10) -> None:
            called.append(True)

        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_tool_updates",
            _tracking_stub,
        )
        result = ensure_tool_installed(
            _make_spec(installed=True),
            skip_update_check=True,
        )
        assert result == ("already_installed", None)
        assert called == []


@pytest.mark.unit
@pytest.mark.bootstrap
class TestEnsureToolUninstalled:
    """Tests for ensure_tool_uninstalled function."""

    def test_not_installed_returns_not_installed(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: False
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.get_tool_source", lambda pkg: None
        )
        result = ensure_tool_uninstalled("test-tool", "test-pkg")
        assert result == ("not_installed", None)

    def test_dry_run_returns_would_uninstall(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        result = ensure_tool_uninstalled("test-tool", "test-pkg", dry_run=True)
        assert result == ("would_uninstall", "Would uninstall test-pkg")

    def test_uninstall_success_returns_uninstalled(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.uninstall_tool",
            lambda pkg: (True, "ok"),
        )
        result = ensure_tool_uninstalled("test-tool", "test-pkg")
        assert result == ("uninstalled", None)

    def test_uninstall_failure_returns_failed(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.installer.uninstall_tool",
            lambda pkg: (False, "uv error"),
        )
        result = ensure_tool_uninstalled("test-tool", "test-pkg")
        assert result == ("failed", "uv error")


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetToolConfigDirWindows:
    def test_windows_uses_appdata(self, monkeypatch):
        from ai_rules.platform import Platform

        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        result = get_tool_config_dir("ai-agent-rules")
        result_str = str(result)
        assert "Lib" in result_str
        assert "site-packages" in result_str

    def test_uv_tool_dir_override(self, monkeypatch):
        monkeypatch.setenv("UV_TOOL_DIR", "/custom/tools")
        result = get_tool_config_dir("ai-agent-rules")
        assert result.as_posix().startswith("/custom/tools")


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
