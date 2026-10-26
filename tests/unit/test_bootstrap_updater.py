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
    _github_token,
    check_github_updates,
    check_index_updates,
    check_tool_updates,
    fetch_changelog_entries,
    get_configured_index_url,
    perform_tool_upgrade,
)


@pytest.fixture(autouse=True)
def _no_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests off the real GITHUB_TOKEN / `gh` credential."""
    monkeypatch.setattr("ai_rules.bootstrap.updater._github_token", lambda: None)


def _http_error(
    code: int, reason: str, headers: dict[str, str]
) -> urllib.error.HTTPError:
    from email.message import Message

    msg = Message()
    for key, value in headers.items():
        msg[key] = value
    return urllib.error.HTTPError(
        "https://api.github.com/repos/o/r/tags", code, reason, msg, None
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


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGithubToken:
    """Token precedence: GITHUB_TOKEN, then `gh auth token`, then none."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Any:
        _github_token.cache_clear()
        yield
        _github_token.cache_clear()

    def _gh_available(self, monkeypatch: pytest.MonkeyPatch, available: bool) -> None:
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available",
            lambda cmd: available and cmd == "gh",
        )

    def test_env_token_wins_without_running_gh(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        self._gh_available(monkeypatch, True)

        def _fail(*args, **kwargs):
            raise AssertionError("gh must not run when GITHUB_TOKEN is set")

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", _fail)
        assert _github_token() == "env-token"

    def test_falls_back_to_gh_auth_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        self._gh_available(monkeypatch, True)
        calls: list[list[str]] = []

        def _run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="gh-token\n", stderr="")

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", _run)
        assert _github_token() == "gh-token"
        assert _github_token() == "gh-token"
        assert calls == [["gh", "auth", "token", "--hostname", "github.com"]]

    def test_gh_pinned_to_github_com_despite_gh_host(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_HOST", "enterprise.example")
        self._gh_available(monkeypatch, True)
        calls: list[list[str]] = []

        def _run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="tok\n", stderr="")

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", _run)
        _github_token()
        assert calls[0][-2:] == ["--hostname", "github.com"]

    def test_env_token_whitespace_is_stripped(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "  env-token\n")
        assert _github_token() == "env-token"

    def test_malformed_token_never_reaches_error_or_logs(self, monkeypatch, caplog):
        import logging

        monkeypatch.setenv("GITHUB_TOKEN", "SYNTHETIC\nSECRET")
        self._gh_available(monkeypatch, False)
        monkeypatch.setattr("ai_rules.bootstrap.updater._github_token", _github_token)
        seen_auth: list[str | None] = []

        def _urlopen(req, *args, **kwargs):
            seen_auth.append(req.get_header("Authorization"))
            raise _http_error(403, "rate limit exceeded", {})

        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen", _urlopen
        )
        with caplog.at_level(logging.DEBUG):
            result = check_github_updates("owner/repo", "1.0.0")
        assert seen_auth == [None]
        assert "SECRET" not in (result.error or "")
        assert "SECRET" not in caplog.text

    def test_gh_missing_means_no_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        self._gh_available(monkeypatch, False)
        assert _github_token() is None

    def test_gh_not_logged_in_means_no_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        self._gh_available(monkeypatch, True)
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="not logged in"
            ),
        )
        assert _github_token() is None

    def test_gh_timeout_means_no_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        self._gh_available(monkeypatch, True)

        def _timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 5)

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", _timeout)
        assert _github_token() is None


@pytest.mark.unit
@pytest.mark.bootstrap
class TestGithubCheckErrors:
    """Failed GitHub checks carry a user-facing reason."""

    def test_rate_limited_403_reports_reason_and_reset(self, monkeypatch):
        from datetime import datetime

        reset = 1_900_000_000
        err = _http_error(
            403,
            "rate limit exceeded",
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
        )

        def _raise(*args, **kwargs):
            raise err

        monkeypatch.setattr("ai_rules.bootstrap.updater.urllib.request.urlopen", _raise)
        result = check_github_updates("owner/repo", "1.0.0")
        expected_reset = datetime.fromtimestamp(reset).strftime("%H:%M:%S")
        assert result.check_failed is True
        assert result.error == (
            f"HTTP 403: rate limit exceeded (resets at {expected_reset})"
        )

    def test_timeout_reports_timed_out(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise TimeoutError("read timed out")

        monkeypatch.setattr("ai_rules.bootstrap.updater.urllib.request.urlopen", _raise)
        result = check_github_updates("owner/repo", "1.0.0")
        assert result.check_failed is True
        assert result.error == "request timed out"

    def test_index_failure_reports_last_stderr_line(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.is_command_available", lambda cmd: True
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                [], 1, stdout="", stderr="warning\nERROR: index unreachable\n"
            ),
        )
        result = check_index_updates("test-package", "1.0.0")
        assert result.error == "ERROR: index unreachable"

    def test_token_sent_and_401_retried_without_it(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._github_token", lambda: "stale-token"
        )
        seen_auth: list[str | None] = []
        ok = _mock_urlopen(json.dumps([{"name": "v1.0.0"}]).encode())

        def _urlopen(req, *args, **kwargs):
            auth = req.get_header("Authorization")
            seen_auth.append(auth)
            assert req.full_url.startswith("https://api.github.com/")
            if auth:
                raise _http_error(401, "Bad credentials", {})
            return ok()

        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen", _urlopen
        )
        result = check_github_updates("owner/repo", "1.0.0")
        assert result.check_failed is False
        assert seen_auth == ["Bearer stale-token", None]

    def test_non_401_error_with_token_is_not_retried(self, monkeypatch):
        monkeypatch.setattr("ai_rules.bootstrap.updater._github_token", lambda: "tok")
        calls: list[int] = []

        def _urlopen(req, *args, **kwargs):
            calls.append(1)
            raise _http_error(500, "Server Error", {})

        monkeypatch.setattr(
            "ai_rules.bootstrap.updater.urllib.request.urlopen", _urlopen
        )
        result = check_github_updates("owner/repo", "1.0.0")
        assert result.error == "HTTP 500: Server Error"
        assert calls == [1]


@pytest.mark.unit
@pytest.mark.bootstrap
class TestUpgradeFailedChecks:
    """`upgrade` must not claim tools are current when a check failed."""

    def _tool(self, tool_id: str) -> ToolSpec:
        return ToolSpec(
            tool_id=tool_id,
            package_name=tool_id,
            display_name=tool_id,
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
        )

    def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        infos: dict[str, UpdateInfo],
        args: tuple[str, ...] = ("-y", "--skip-install"),
        stdin: str | None = None,
    ) -> Any:
        from click.testing import CliRunner

        from ai_rules.cli.commands.upgrade import upgrade

        tools = [self._tool(tid) for tid in infos]
        upgraded: list[str] = []
        monkeypatch.setattr("ai_rules.bootstrap.get_updatable_tools", lambda: tools)
        monkeypatch.setattr(
            "ai_rules.bootstrap.check_tool_updates",
            lambda tool, **kw: infos[tool.tool_id],
        )
        monkeypatch.setattr(
            "ai_rules.bootstrap.updater._resolve_effective_source",
            lambda tool: ToolSource.GITHUB,
        )

        def _upgrade(tool, **kwargs):
            upgraded.append(tool.tool_id)
            return True, "Upgrade successful", True

        monkeypatch.setattr("ai_rules.bootstrap.perform_tool_upgrade", _upgrade)
        result = CliRunner().invoke(upgrade, list(args), input=stdin)
        return result, upgraded

    def _failed(self) -> UpdateInfo:
        return UpdateInfo(
            has_update=False,
            current_version="1.0.0",
            latest_version="1.0.0",
            source="github",
            check_failed=True,
            error="HTTP 403: rate limit exceeded (resets at 19:10:00)",
        )

    def test_all_failed_reports_reasons_and_exits_nonzero(self, monkeypatch):
        result, upgraded = self._run(monkeypatch, {"broken": self._failed()})
        assert result.exit_code == 1
        assert "All tools are up to date" not in result.output
        assert "broken: HTTP 403: rate limit exceeded" in result.output
        assert upgraded == []

    def test_available_updates_still_install_before_nonzero_exit(self, monkeypatch):
        update = UpdateInfo(
            has_update=True,
            current_version="1.0.0",
            latest_version="2.0.0",
            source="github",
        )
        result, upgraded = self._run(
            monkeypatch, {"outdated": update, "broken": self._failed()}
        )
        assert upgraded == ["outdated"]
        assert result.exit_code == 1
        assert "broken: HTTP 403" in result.output

    def test_all_current_exits_zero(self, monkeypatch):
        current = UpdateInfo(
            has_update=False,
            current_version="1.0.0",
            latest_version="1.0.0",
            source="github",
        )
        result, _ = self._run(monkeypatch, {"fine": current})
        assert result.exit_code == 0
        assert "All tools are up to date" in result.output

    @pytest.mark.parametrize(
        "args", [("--force", "--check"), ("--force", "-y", "--skip-install")]
    )
    def test_force_still_reports_failure_and_exits_nonzero(self, monkeypatch, args):
        result, _ = self._run(monkeypatch, {"broken": self._failed()}, args=args)
        assert result.exit_code == 1
        assert "broken: HTTP 403" in result.output

    def test_cancel_after_failed_check_exits_nonzero(self, monkeypatch):
        update = UpdateInfo(
            has_update=True,
            current_version="1.0.0",
            latest_version="2.0.0",
            source="github",
        )
        result, upgraded = self._run(
            monkeypatch,
            {"outdated": update, "broken": self._failed()},
            args=("--skip-install",),
            stdin="n\n",
        )
        assert upgraded == []
        assert result.exit_code == 1
        assert "broken: HTTP 403" in result.output


@pytest.mark.unit
@pytest.mark.bootstrap
def test_redirect_drops_authorization(monkeypatch):
    """The real HTTPRedirectHandler must not forward the token to the new host."""
    import io
    import urllib.request
    import urllib.response

    from email.message import Message

    seen: list[tuple[str, str | None]] = []

    class FakeTransport(urllib.request.BaseHandler):
        handler_order = 100

        def https_open(self, req: urllib.request.Request) -> Any:
            seen.append((req.full_url, req.get_header("Authorization")))
            headers = Message()
            if req.host == "api.github.com":
                headers["Location"] = "https://outside.example/redirected"
                body, code = b"", 302
            else:
                body, code = json.dumps([{"name": "v1.0.0"}]).encode(), 200
            resp = urllib.response.addinfourl(
                io.BytesIO(body), headers, req.full_url, code
            )
            resp.msg = "Found" if code == 302 else "OK"  # type: ignore[attr-defined]
            return resp

    opener = urllib.request.build_opener(FakeTransport())
    monkeypatch.setattr("ai_rules.bootstrap.updater._github_token", lambda: "tok")
    monkeypatch.setattr(
        "ai_rules.bootstrap.updater.urllib.request.urlopen",
        lambda req, timeout: opener.open(req, timeout=timeout),
    )
    result = check_github_updates("owner/repo", "1.0.0")
    assert result.check_failed is False
    assert seen == [
        ("https://api.github.com/repos/owner/repo/tags", "Bearer tok"),
        ("https://outside.example/redirected", None),
    ]
