import pytest

from ai_rules.platform import (
    get_appdata_dir,
    get_default_editor,
    get_goose_config_dir,
    get_lib_path_fragment,
    get_statusline_config_dir,
    get_uv_tools_dir,
    is_windows,
)


@pytest.mark.unit
class TestIsWindows:
    def test_returns_true_on_win32(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
        assert is_windows() is True

    def test_returns_false_on_linux(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        assert is_windows() is False

    def test_returns_false_on_darwin(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "darwin")
        assert is_windows() is False


@pytest.mark.unit
class TestGetAppdataDir:
    def test_returns_appdata_path(self, monkeypatch):
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        from pathlib import Path

        assert get_appdata_dir() == Path("C:\\Users\\test\\AppData\\Roaming")

    def test_raises_if_unset(self, monkeypatch):
        monkeypatch.delenv("APPDATA", raising=False)
        with pytest.raises(RuntimeError, match="APPDATA"):
            get_appdata_dir()


@pytest.mark.unit
class TestGetUvToolsDir:
    def test_override_wins(self, monkeypatch):
        from pathlib import Path

        monkeypatch.setenv("UV_TOOL_DIR", "/custom/tools")
        assert get_uv_tools_dir() == Path("/custom/tools")

    def test_windows_default(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        result = get_uv_tools_dir()
        assert "uv" in str(result) and "tools" in str(result)

    def test_unix_default(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_uv_tools_dir()
        result_str = result.as_posix()
        assert "uv/tools" in result_str

    def test_unix_xdg_override(self, monkeypatch):
        from pathlib import Path

        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        result = get_uv_tools_dir()
        assert result == Path("/custom/data/uv/tools")


@pytest.mark.unit
class TestGetLibPathFragment:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
        result = get_lib_path_fragment("python3.12")
        assert "Lib" in result
        assert "site-packages" in result
        assert "python3.12" not in result

    def test_unix(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        result = get_lib_path_fragment("python3.12")
        assert "python3.12" in result
        assert "site-packages" in result


@pytest.mark.unit
class TestGetDefaultEditor:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
        assert get_default_editor() == "notepad"

    def test_unix(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        assert get_default_editor() == "vi"


@pytest.mark.unit
class TestGetGooseConfigDir:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        result = get_goose_config_dir()
        result_str = str(result)
        assert "Block" in result_str
        assert "goose" in result_str

    def test_unix(self, monkeypatch):
        from pathlib import Path

        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        result = get_goose_config_dir()
        assert result == Path("~/.config/goose")


@pytest.mark.unit
class TestGetStatuslineConfigDir:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.sys.platform", "win32")
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        result = get_statusline_config_dir()
        assert "claude-statusline" in str(result)

    def test_unix(self, monkeypatch):
        from pathlib import Path

        monkeypatch.setattr("ai_rules.platform.sys.platform", "linux")
        result = get_statusline_config_dir()
        assert result == Path("~/.config/claude-statusline")
