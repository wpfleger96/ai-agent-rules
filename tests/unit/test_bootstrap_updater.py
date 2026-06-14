"""Tests for update checking and application utilities."""

from __future__ import annotations

import json
import subprocess
import urllib.error

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from ai_rules.bootstrap.installer import UV_NOT_FOUND_ERROR, ToolSource
from ai_rules.bootstrap.updater import (
    ToolSpec,
    UpdateInfo,
    _compute_required_python,
    _fetch_requires_python,
    _get_tool_venv_python,
    check_github_updates,
    check_index_updates,
    check_tool_updates,
    fetch_changelog_entries,
    get_configured_index_url,
    perform_tool_upgrade,
)


def _track(tracker: list[int], result: Any) -> Any:
    """Append to tracker and return result — typed alternative to (list.append(), val)[-1]."""
    tracker.append(1)
    return result


def _mock_urlopen(body: bytes) -> Callable[..., Any]:
    """Create a mock urlopen that returns a context manager with the given body."""

    def _urlopen(*args: Any, **kwargs: Any) -> MagicMock:
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        return resp

    return _urlopen


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetConfiguredIndexUrl:
    """Tests for get_configured_index_url helper."""

    def test_prefers_uv_default_index(self, monkeypatch):
        """UV_DEFAULT_INDEX takes priority over deprecated options."""
        monkeypatch.setenv("UV_DEFAULT_INDEX", "https://default.example.com")
        monkeypatch.setenv("UV_INDEX_URL", "https://legacy.example.com")
        monkeypatch.setenv("PIP_INDEX_URL", "https://pip.example.com")
        assert get_configured_index_url() == "https://default.example.com"

    def test_falls_back_to_uv_index_url(self, monkeypatch):
        """Falls back to UV_INDEX_URL when UV_DEFAULT_INDEX not set."""
        monkeypatch.delenv("UV_DEFAULT_INDEX", raising=False)
        monkeypatch.setenv("UV_INDEX_URL", "https://legacy.example.com")
        monkeypatch.setenv("PIP_INDEX_URL", "https://pip.example.com")
        assert get_configured_index_url() == "https://legacy.example.com"

    def test_falls_back_to_pip_index_url(self, monkeypatch):
        """Falls back to PIP_INDEX_URL when UV vars not set."""
        monkeypatch.delenv("UV_DEFAULT_INDEX", raising=False)
        monkeypatch.delenv("UV_INDEX_URL", raising=False)
        monkeypatch.setenv("PIP_INDEX_URL", "https://pip.example.com")
        assert get_configured_index_url() == "https://pip.example.com"

    def test_returns_none_when_not_configured(self, monkeypatch):
        """Returns None when no index env vars set."""
        monkeypatch.delenv("UV_DEFAULT_INDEX", raising=False)
        monkeypatch.delenv("UV_INDEX_URL", raising=False)
        monkeypatch.delenv("PIP_INDEX_URL", raising=False)
        assert get_configured_index_url() is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestCheckIndexUpdates:
    """Tests for check_index_updates function."""

    def test_check_index_no_update(self, monkeypatch):
        """Test when current version is up to date."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="test-package (1.0.0)\nAvailable versions: 1.0.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)

        update_info = check_index_updates("test-package", "1.0.0")
        assert update_info.has_update is False
        assert update_info.current_version == "1.0.0"
        assert update_info.latest_version == "1.0.0"

    def test_check_index_has_update(self, monkeypatch):
        """Test when newer version is available."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="test-package (1.1.0)\nAvailable versions: 1.1.0, 1.0.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)

        update_info = check_index_updates("test-package", "1.0.0")
        assert update_info.has_update is True
        assert update_info.current_version == "1.0.0"
        assert update_info.latest_version == "1.1.0"
        assert update_info.source == "index"

    def test_check_index_command_error(self, monkeypatch):
        """Test handling of command errors."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Network error"
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)

        update_info = check_index_updates("test-package", "1.0.0")
        assert update_info.has_update is False

    def test_check_index_invalid_package_name(self):
        """Test that invalid package names are rejected."""
        update_info = check_index_updates("../../../etc/passwd", "1.0.0")
        assert update_info.has_update is False

    def test_check_index_package_name_validation(self):
        """Test package name validation with various invalid names."""
        invalid_names = [
            "package with spaces",
            "package/with/slashes",
            "../relative/path",
            "package;with;semicolons",
            "",
        ]
        for name in invalid_names:
            update_info = check_index_updates(name, "1.0.0")
            assert update_info.has_update is False, f"Should reject: {name}"

    def test_check_index_without_uvx(self, monkeypatch):
        """Test that missing uvx returns no update."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: False
        )
        update_info = check_index_updates("test-package", "1.0.0")
        assert update_info.has_update is False

    def test_check_index_unparseable_output(self, monkeypatch):
        """Test handling of unparseable output."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Unexpected output format", stderr=""
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)

        update_info = check_index_updates("test-package", "1.0.0")
        assert update_info.has_update is False

    def test_check_index_timeout(self, monkeypatch):
        """Test handling of timeout."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired("uvx", 30)

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)

        update_info = check_index_updates("test-package", "1.0.0")
        assert update_info.has_update is False


@pytest.fixture
def test_tool():
    """Create a minimal ToolSpec for testing."""
    return ToolSpec(
        tool_id="test",
        package_name="test-package",
        display_name="test",
        get_version=lambda: "1.0.0",
        is_installed=lambda: True,
    )


@pytest.mark.unit
@pytest.mark.bootstrap
class TestPerformToolUpgrade:
    """Tests for perform_tool_upgrade function."""

    def test_perform_tool_upgrade_without_uv(self, test_tool, monkeypatch):
        """Test that missing uv returns error."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: False
        )
        success, message, was_upgraded = perform_tool_upgrade(test_tool)
        assert success is False
        assert message == UV_NOT_FOUND_ERROR
        assert was_upgraded is False

    def test_perform_tool_upgrade_success(self, test_tool, monkeypatch):
        """Test successful upgrade."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Upgraded test-package from 1.0.0 to 1.1.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)
        assert success is True
        assert "successful" in message.lower()
        assert was_upgraded is True

    def test_perform_tool_upgrade_failure(self, test_tool, monkeypatch):
        """Test upgrade failure."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Package not found"
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)
        assert success is False
        assert "Package not found" in message
        assert was_upgraded is False

    def test_perform_tool_upgrade_timeout(self, test_tool, monkeypatch):
        """Test handling of timeout."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired("uv", 60)

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)
        assert success is False
        assert "timed out" in message.lower()
        assert was_upgraded is False

    def test_perform_tool_upgrade_unexpected_exception(self, test_tool, monkeypatch):
        """Test handling of unexpected errors."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            raise ValueError("Unexpected error")

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)
        assert success is False
        assert "Unexpected error" in message
        assert was_upgraded is False

    def test_perform_tool_upgrade_empty_stderr(self, test_tool, monkeypatch):
        """Test handling of failures with no stderr."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)
        assert success is False
        assert "failed" in message.lower()
        assert was_upgraded is False

    def test_pypi_installation_upgrades_successfully(self, test_tool, monkeypatch):
        """Test that PyPI installations still upgrade correctly."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source", lambda pkg: ToolSource.PYPI
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Upgraded test-package from 1.0.0 to 1.1.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)

        assert success is True
        assert was_upgraded is True


@pytest.mark.unit
@pytest.mark.bootstrap
class TestCheckToolUpdatesLocalSource:
    """Tests that LOCAL-sourced tools are skipped by check_tool_updates."""

    def test_local_source_returns_none(self, monkeypatch):
        """check_tool_updates returns None for LOCAL installs — no PyPI query."""
        tool = ToolSpec(
            tool_id="example-tool",
            package_name="example-mcp-server",
            display_name="example-tool",
            get_version=lambda: "0.1.0",
            is_installed=lambda: True,
            github_repo="wpfleger96/example-tool",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.LOCAL,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.LOCAL, None),
        )
        result = check_tool_updates(tool)
        assert result is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestPerformToolUpgradeLocalSource:
    """Tests that LOCAL-sourced tools skip upgrade and return early."""

    def test_local_source_skips_upgrade(self, monkeypatch):
        """perform_tool_upgrade returns early for LOCAL installs without running subprocess."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.LOCAL,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.LOCAL, None),
        )

        subprocess_called = []
        original_run = subprocess.run

        def spy_run(*args, **kwargs):
            subprocess_called.append(args)
            return original_run(*args, **kwargs)

        monkeypatch.setattr("subprocess.run", spy_run)

        tool = ToolSpec(
            tool_id="example-tool",
            package_name="example-mcp-server",
            display_name="example-tool",
            get_version=lambda: "0.1.0",
            is_installed=lambda: True,
            github_repo="wpfleger96/example-tool",
        )
        success, message, was_upgraded = perform_tool_upgrade(tool)
        assert success is True
        assert was_upgraded is False
        assert not subprocess_called


@pytest.mark.unit
@pytest.mark.bootstrap
class TestIsEnabledFiltering:
    """Tests for is_enabled filtering logic in upgrade command."""

    @staticmethod
    def _make_tool(
        tool_id: str, is_enabled: Callable[[], bool] | None = None
    ) -> ToolSpec:
        return ToolSpec(
            tool_id=tool_id,
            package_name=f"{tool_id}-pkg",
            display_name=tool_id,
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            is_enabled=is_enabled,
        )

    def test_disabled_tool_excluded(self):
        from ai_rules.cli.commands.upgrade import _filter_enabled

        tools = [self._make_tool("example-tool", is_enabled=lambda: False)]
        assert _filter_enabled(tools) == []

    def test_enabled_tool_included(self):
        from ai_rules.cli.commands.upgrade import _filter_enabled

        tools = [self._make_tool("example-tool", is_enabled=lambda: True)]
        assert len(_filter_enabled(tools)) == 1

    def test_tool_without_is_enabled_included(self):
        from ai_rules.cli.commands.upgrade import _filter_enabled

        tools = [self._make_tool("statusline", is_enabled=None)]
        assert len(_filter_enabled(tools)) == 1

    def test_disabled_tool_included_when_explicitly_targeted(self):
        """--only=<tool> bypasses the is_enabled check."""
        resolved_only = "example-tool"
        tools = [self._make_tool("example-tool", is_enabled=lambda: False)]
        tools = [
            t for t in tools if resolved_only is None or t.tool_id == resolved_only
        ]
        tools = [t for t in tools if t.is_installed()]
        if resolved_only is None:
            from ai_rules.cli.commands.upgrade import _filter_enabled

            tools = _filter_enabled(tools)
        assert len(tools) == 1


@pytest.mark.unit
@pytest.mark.bootstrap
class TestMissingToolsFilterEnabled:
    """Tests that missing_tools respects is_enabled filtering."""

    @staticmethod
    def _make_tool(
        tool_id: str,
        installed: bool = True,
        is_enabled: Callable[[], bool] | None = None,
    ) -> ToolSpec:
        return ToolSpec(
            tool_id=tool_id,
            package_name=f"{tool_id}-pkg",
            display_name=tool_id,
            get_version=lambda: "1.0.0",
            is_installed=lambda: installed,
            is_enabled=is_enabled,
        )

    def test_disabled_missing_tool_excluded(self):
        from ai_rules.cli.commands.upgrade import _filter_enabled

        all_tools = [
            self._make_tool("example-tool", installed=False, is_enabled=lambda: False)
        ]
        missing_tools = [t for t in all_tools if not t.is_installed()]
        missing_tools = _filter_enabled(missing_tools)
        assert missing_tools == []

    def test_enabled_missing_tool_included(self):
        from ai_rules.cli.commands.upgrade import _filter_enabled

        all_tools = [self._make_tool("statusline", installed=False, is_enabled=None)]
        missing_tools = [t for t in all_tools if not t.is_installed()]
        missing_tools = _filter_enabled(missing_tools)
        assert len(missing_tools) == 1

    def test_disabled_missing_tool_included_when_explicitly_targeted(self):
        """--only=<tool> bypasses the is_enabled check for missing tools too."""
        from ai_rules.cli.commands.upgrade import _filter_enabled

        resolved_only = "example-tool"
        all_tools = [
            self._make_tool("example-tool", installed=False, is_enabled=lambda: False)
        ]
        missing_tools = [t for t in all_tools if not t.is_installed()]
        if resolved_only is None:
            missing_tools = _filter_enabled(missing_tools)
        assert len(missing_tools) == 1


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGetToolVenvPython:
    """Tests for _get_tool_venv_python helper."""

    def test_reads_version_from_pyvenv_cfg(self, tmp_path, monkeypatch):
        pyvenv_cfg = tmp_path / "uv" / "tools" / "test-pkg" / "pyvenv.cfg"
        pyvenv_cfg.parent.mkdir(parents=True)
        pyvenv_cfg.write_text(
            "home = /usr/bin\n"
            "implementation = CPython\n"
            "version_info = 3.13.3\n"
            "include-system-site-packages = false\n"
        )
        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "uv" / "tools"))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert _get_tool_venv_python("test-pkg") == "3.13.3"

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "uv" / "tools"))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert _get_tool_venv_python("nonexistent-pkg") is None

    def test_returns_none_when_no_version_info(self, tmp_path, monkeypatch):
        pyvenv_cfg = tmp_path / "uv" / "tools" / "test-pkg" / "pyvenv.cfg"
        pyvenv_cfg.parent.mkdir(parents=True)
        pyvenv_cfg.write_text("home = /usr/bin\n")
        monkeypatch.setenv("UV_TOOL_DIR", str(tmp_path / "uv" / "tools"))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert _get_tool_venv_python("test-pkg") is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestFetchRequiresPython:
    """Tests for _fetch_requires_python helper."""

    def test_pypi_source(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen",
            _mock_urlopen(b'{"info": {"requires_python": ">=3.14"}}'),
        )
        result = _fetch_requires_python("test-pkg", "1.0.0", None, ToolSource.PYPI)
        assert result == ">=3.14"

    def test_github_source(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen",
            _mock_urlopen(b'[project]\nrequires-python = ">=3.14"\n'),
        )
        result = _fetch_requires_python(
            "test-pkg", "1.0.0", "owner/repo", ToolSource.GITHUB
        )
        assert result == ">=3.14"

    def test_returns_none_on_network_error(self, monkeypatch):
        def _raise(*args: Any, **kwargs: Any) -> None:
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("ai_rules.bootstrap.updater.urllib.request.urlopen", _raise)
        result = _fetch_requires_python("test-pkg", "1.0.0", None, ToolSource.PYPI)
        assert result is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestComputeRequiredPython:
    """Tests for _compute_required_python helper."""

    @staticmethod
    def _make_tool(
        package_name: str = "test-pkg", github_repo: str | None = None
    ) -> ToolSpec:
        return ToolSpec(
            tool_id="test",
            package_name=package_name,
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo=github_repo,
        )

    def test_returns_none_when_venv_satisfies(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._get_tool_venv_python",
            lambda pkg: "3.14.5",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._fetch_requires_python",
            lambda *a: ">=3.14",
        )
        result = _compute_required_python(self._make_tool(), "2.0.0", ToolSource.PYPI)
        assert result is None

    def test_returns_minimum_when_venv_too_old(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._get_tool_venv_python",
            lambda pkg: "3.13.3",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._fetch_requires_python",
            lambda *a: ">=3.14",
        )
        result = _compute_required_python(self._make_tool(), "2.0.0", ToolSource.PYPI)
        assert result == "3.14"

    def test_returns_none_when_venv_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._get_tool_venv_python",
            lambda pkg: None,
        )
        result = _compute_required_python(self._make_tool(), "2.0.0", ToolSource.PYPI)
        assert result is None

    def test_returns_none_when_requires_python_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._get_tool_venv_python",
            lambda pkg: "3.13.3",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._fetch_requires_python",
            lambda *a: None,
        )
        result = _compute_required_python(self._make_tool(), "2.0.0", ToolSource.PYPI)
        assert result is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestPerformToolUpgradeWithPythonSwitch:
    """Tests for perform_tool_upgrade with Python version switching."""

    @pytest.fixture
    def test_tool(self):
        return ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test-package",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )

    def test_adds_python_flag_when_mismatch(self, test_tool, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source", lambda pkg: ToolSource.PYPI
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._compute_required_python",
            lambda tool, ver, src: "3.14",
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Upgraded test-package from 1.0.0 to 2.0.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, msg, was_upgraded = perform_tool_upgrade(
            test_tool, target_version="2.0.0"
        )
        assert success is True
        assert was_upgraded is True
        assert "--python" in captured_cmd
        assert "3.14" in captured_cmd

    def test_no_python_flag_when_no_mismatch(self, test_tool, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source", lambda pkg: ToolSource.PYPI
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._compute_required_python",
            lambda tool, ver, src: None,
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Nothing to upgrade", stderr=""
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        perform_tool_upgrade(test_tool, target_version="1.0.0")
        assert "--python" not in captured_cmd

    def test_no_python_flag_when_no_target_version(self, test_tool, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source", lambda pkg: ToolSource.PYPI
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Nothing to upgrade", stderr=""
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        perform_tool_upgrade(test_tool)
        assert "--python" not in captured_cmd

    def test_github_source_gets_python_flag(self, test_tool, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.GITHUB,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._compute_required_python",
            lambda tool, ver, src: "3.14",
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Installed 1 executable: test-package",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, msg, was_upgraded = perform_tool_upgrade(
            test_tool, target_version="2.0.0"
        )
        assert success is True
        assert "--python" in captured_cmd
        assert "3.14" in captured_cmd
        assert "--force" in captured_cmd
        assert "--reinstall" in captured_cmd


@pytest.mark.unit
@pytest.mark.bootstrap
class TestCheckToolUpdatesSourceResolution:
    """Tests that check_tool_updates consults config when receipt doesn't match."""

    def test_receipt_pypi_config_github_uses_github_check(self, monkeypatch):
        """receipt=PYPI + config=GITHUB → check_github_updates is called."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )
        github_called = []
        index_called = []
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_github_updates",
            lambda repo, cur, timeout: _track(
                github_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="github",
                ),
            ),
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_index_updates",
            lambda pkg, cur, timeout, repo=None: _track(
                index_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="index",
                ),
            ),
        )
        result = check_tool_updates(tool)
        assert result is not None
        assert len(github_called) == 1
        assert len(index_called) == 0

    def test_receipt_pypi_config_pypi_uses_index_check(self, monkeypatch):
        """receipt=PYPI + config=PYPI → check_index_updates is called (regression guard)."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.PYPI, None),
        )
        github_called = []
        index_called = []
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_github_updates",
            lambda repo, cur, timeout: _track(
                github_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="github",
                ),
            ),
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_index_updates",
            lambda pkg, cur, timeout, repo=None: _track(
                index_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="index",
                ),
            ),
        )
        result = check_tool_updates(tool)
        assert result is not None
        assert len(index_called) == 1
        assert len(github_called) == 0

    def test_receipt_none_config_github_uses_github_check(self, monkeypatch):
        """receipt=None + config=GITHUB → check_github_updates is called."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: None,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )
        github_called = []
        index_called = []
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_github_updates",
            lambda repo, cur, timeout: _track(
                github_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="github",
                ),
            ),
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_index_updates",
            lambda pkg, cur, timeout, repo=None: _track(
                index_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="index",
                ),
            ),
        )
        result = check_tool_updates(tool)
        assert result is not None
        assert len(github_called) == 1
        assert len(index_called) == 0

    def test_receipt_local_config_github_uses_github_check(self, monkeypatch):
        """receipt=LOCAL + config=GITHUB → config wins, check_github_updates is called."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.LOCAL,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )
        github_called = []
        index_called = []
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_github_updates",
            lambda repo, cur, timeout: _track(
                github_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="github",
                ),
            ),
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.check_index_updates",
            lambda pkg, cur, timeout, repo=None: _track(
                index_called,
                UpdateInfo(
                    has_update=False,
                    current_version=cur,
                    latest_version=cur,
                    source="index",
                ),
            ),
        )
        result = check_tool_updates(tool)
        assert result is not None
        assert len(github_called) == 1
        assert len(index_called) == 0


@pytest.mark.unit
@pytest.mark.bootstrap
class TestPerformToolUpgradeSourceResolution:
    """Tests that perform_tool_upgrade uses the config-derived source for install."""

    def test_receipt_pypi_config_github_uses_github_url(self, monkeypatch):
        """receipt=PYPI + config=GITHUB → cmd contains github_install_url, not package name."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Installed 1 executable: test-package",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(tool)
        assert success is True
        assert tool.github_install_url in captured_cmd
        assert "test-package" not in [
            arg for arg in captured_cmd if arg == "test-package"
        ]

    def test_receipt_pypi_config_pypi_uses_package_name(self, monkeypatch):
        """receipt=PYPI + config=PYPI → cmd contains plain package name (regression)."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.PYPI, None),
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Upgraded test-package from 1.0.0 to 1.1.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(tool)
        assert success is True
        assert "test-package" in captured_cmd
        assert tool.github_install_url not in captured_cmd

    def test_receipt_local_config_github_uses_github_url(self, monkeypatch):
        """receipt=LOCAL + config=GITHUB → config wins, github_install_url used."""
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="owner/test-package",
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.LOCAL,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )

        captured_cmd = []

        def mock_run(*args, **kwargs):
            captured_cmd.extend(args[0])

            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Installed 1 executable: test-package",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(tool)
        assert success is True
        assert tool.github_install_url in captured_cmd


@pytest.mark.unit
@pytest.mark.bootstrap
class TestCheckFailedPropagation:
    """Tests that check_failed is set correctly on UpdateInfo."""

    def test_index_check_returncode_error_sets_check_failed(self, monkeypatch):
        """Non-zero returncode from subprocess → check_failed=True."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Network error"
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        result = check_index_updates("test-package", "1.0.0")
        assert result.check_failed is True

    def test_index_check_timeout_sets_check_failed(self, monkeypatch):
        """TimeoutExpired from subprocess → check_failed=True."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired("uvx", 30)

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        result = check_index_updates("test-package", "1.0.0")
        assert result.check_failed is True

    def test_index_check_success_no_update_check_failed_false(self, monkeypatch):
        """Successful parse with no update → check_failed=False."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )

        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="test-package (1.0.0)\nAvailable versions: 1.0.0",
                stderr="",
            )

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        result = check_index_updates("test-package", "1.0.0")
        assert result.check_failed is False

    def test_github_check_network_error_sets_check_failed(self, monkeypatch):
        """URLError from urlopen → check_failed=True."""

        def _raise(*args, **kwargs):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("ai_rules.bootstrap.updater.urllib.request.urlopen", _raise)
        result = check_github_updates("owner/test-package", "1.0.0")
        assert result.check_failed is True

    def test_github_check_success_check_failed_false(self, monkeypatch):
        """Successful GitHub tags response → check_failed=False."""
        import json

        payload = json.dumps([{"name": "v1.0.0"}]).encode()
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen",
            _mock_urlopen(payload),
        )
        result = check_github_updates("owner/test-package", "1.0.0")
        assert result.check_failed is False


@pytest.mark.unit
@pytest.mark.bootstrap
class TestResolveEffectiveSource:
    """Tests for _resolve_effective_source helper."""

    def test_config_github_overrides_receipt_pypi(self, monkeypatch):
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.PYPI,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )
        from ai_rules.bootstrap.updater import _resolve_effective_source

        assert _resolve_effective_source(tool) == ToolSource.GITHUB

    def test_config_github_overrides_receipt_local(self, monkeypatch):
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.LOCAL,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.GITHUB, None),
        )
        from ai_rules.bootstrap.updater import _resolve_effective_source

        assert _resolve_effective_source(tool) == ToolSource.GITHUB

    def test_config_pypi_uses_receipt(self, monkeypatch):
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: ToolSource.GITHUB,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.PYPI, None),
        )
        from ai_rules.bootstrap.updater import _resolve_effective_source

        assert _resolve_effective_source(tool) == ToolSource.GITHUB

    def test_no_receipt_defaults_to_pypi(self, monkeypatch):
        tool = ToolSpec(
            tool_id="test",
            package_name="test-package",
            display_name="test",
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_tool_source",
            lambda pkg: None,
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.get_effective_install_source",
            lambda tool_id: (ToolSource.PYPI, None),
        )
        from ai_rules.bootstrap.updater import _resolve_effective_source

        assert _resolve_effective_source(tool) == ToolSource.PYPI


@pytest.mark.unit
@pytest.mark.bootstrap
class TestFetchChangelogEntries:
    """Tests for fetch_changelog_entries using the GitHub Releases API."""

    def _releases_payload(self, releases: list[dict]) -> bytes:
        return json.dumps(releases).encode()

    def test_returns_entries_in_version_range(self, monkeypatch):
        """Returns entries for versions newer than current and not newer than latest."""
        releases = [
            {"tag_name": "v1.2.0", "body": "## Changes\n\nAdded feature X"},
            {"tag_name": "v1.1.0", "body": "## Changes\n\nFixed bug Y"},
            {"tag_name": "v1.0.0", "body": "## Changes\n\nInitial release"},
        ]
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen",
            _mock_urlopen(self._releases_payload(releases)),
        )

        result = fetch_changelog_entries("owner/repo", "1.0.0", "1.2.0")

        versions = [v for v, _ in result]
        assert "1.2.0" in versions
        assert "1.1.0" in versions
        assert "1.0.0" not in versions

    def test_strips_skills_downloads_trailer(self, monkeypatch):
        """Skills Downloads section appended by CI is removed from release notes."""
        body = (
            "## Changes\n\nSome change\n\n---\n\n"
            "### Skills Downloads\n\n| table content |"
        )
        releases = [{"tag_name": "v2.0.0", "body": body}]
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen",
            _mock_urlopen(self._releases_payload(releases)),
        )

        result = fetch_changelog_entries("owner/repo", "1.0.0", "2.0.0")

        assert len(result) == 1
        _, notes = result[0]
        assert "Skills Downloads" not in notes

    def test_empty_releases_returns_empty_list(self, monkeypatch):
        """Empty releases array returns an empty list."""
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen",
            _mock_urlopen(self._releases_payload([])),
        )

        result = fetch_changelog_entries("owner/repo", "1.0.0", "1.1.0")

        assert result == []

    def test_network_error_returns_empty_list(self, monkeypatch):
        """Network failure returns empty list without raising."""

        def _raise(*args: Any, **kwargs: Any) -> None:
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("ai_rules.bootstrap.updater.urllib.request.urlopen", _raise)

        result = fetch_changelog_entries("owner/repo", "1.0.0", "1.1.0")

        assert result == []
