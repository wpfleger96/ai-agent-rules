"""Tests for update checking and application utilities."""

import subprocess

from collections.abc import Callable

import pytest

from ai_rules.bootstrap.installer import UV_NOT_FOUND_ERROR, ToolSource
from ai_rules.bootstrap.updater import (
    ToolSpec,
    check_index_updates,
    get_configured_index_url,
    perform_tool_upgrade,
)


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
            class Result:
                returncode = 0
                stdout = "test-package (1.0.0)\nAvailable versions: 1.0.0"
                stderr = ""

            return Result()

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
            class Result:
                returncode = 0
                stdout = "test-package (1.1.0)\nAvailable versions: 1.1.0, 1.0.0"
                stderr = ""

            return Result()

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
            class Result:
                returncode = 1
                stdout = ""
                stderr = "Network error"

            return Result()

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
            class Result:
                returncode = 0
                stdout = "Unexpected output format"
                stderr = ""

            return Result()

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
            class Result:
                returncode = 0
                stderr = ""
                stdout = "Upgraded test-package from 1.0.0 to 1.1.0"

            return Result()

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
            class Result:
                returncode = 1
                stderr = "Package not found"
                stdout = ""

            return Result()

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
            class Result:
                returncode = 1
                stderr = ""
                stdout = ""

            return Result()

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
            class Result:
                returncode = 0
                stderr = ""
                stdout = "Upgraded test-package from 1.0.0 to 1.1.0"

            return Result()

        monkeypatch.setattr("ai_rules.bootstrap.updater.subprocess.run", mock_run)
        success, message, was_upgraded = perform_tool_upgrade(test_tool)

        assert success is True
        assert was_upgraded is True


@pytest.mark.unit
@pytest.mark.bootstrap
class TestIsEnabledFiltering:
    """Tests that is_enabled is respected in upgrade filtering (cli.py pattern)."""

    def _make_tool(
        self, tool_id: str, is_enabled: Callable[[], bool] | None = None
    ) -> ToolSpec:
        return ToolSpec(
            tool_id=tool_id,
            package_name=tool_id,
            display_name=tool_id,
            get_version=lambda: "1.0.0",
            is_installed=lambda: True,
            github_repo="org/repo",
            is_enabled=is_enabled,
        )

    def test_disabled_tool_excluded_in_default_upgrade(self):
        tools = [self._make_tool("basic-memory", is_enabled=lambda: False)]
        tools = [t for t in tools if t.is_installed()]
        tools = [t for t in tools if t.is_enabled is None or t.is_enabled()]
        assert len(tools) == 0

    def test_tool_with_no_gate_always_included(self):
        tools = [self._make_tool("statusline", is_enabled=None)]
        tools = [t for t in tools if t.is_installed()]
        tools = [t for t in tools if t.is_enabled is None or t.is_enabled()]
        assert len(tools) == 1

    def test_enabled_tool_included(self):
        tools = [self._make_tool("basic-memory", is_enabled=lambda: True)]
        tools = [t for t in tools if t.is_installed()]
        tools = [t for t in tools if t.is_enabled is None or t.is_enabled()]
        assert len(tools) == 1

    def test_disabled_tool_still_included_when_explicitly_targeted(self):
        """When user passes --only=basic-memory, is_enabled is not checked."""
        resolved_only = "basic-memory"
        tools = [self._make_tool("basic-memory", is_enabled=lambda: False)]
        tools = [
            t for t in tools if resolved_only is None or t.tool_id == resolved_only
        ]
        tools = [t for t in tools if t.is_installed()]
        # is_enabled check only runs when resolved_only is None
        if resolved_only is None:
            tools = [t for t in tools if t.is_enabled is None or t.is_enabled()]
        assert len(tools) == 1
