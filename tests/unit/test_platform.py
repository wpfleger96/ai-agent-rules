import pytest

from ai_rules.platform import (
    Platform,
    detect_platform,
    get_appdata_dir,
    get_default_editor,
    get_goose_config_dir,
    get_lib_path_fragment,
    get_statusline_config_dir,
    get_uv_tools_dir,
    is_platform,
)


@pytest.mark.unit
class TestPlatformEnum:
    def test_display_names(self):
        assert Platform.MACOS.display_name == "macOS"
        assert Platform.LINUX.display_name == "Linux"
        assert Platform.WINDOWS.display_name == "Windows"
        assert Platform.WSL.display_name == "WSL"

    def test_is_unix_like(self):
        assert Platform.MACOS.is_unix_like is True
        assert Platform.LINUX.is_unix_like is True
        assert Platform.WSL.is_unix_like is True
        assert Platform.WINDOWS.is_unix_like is False

    def test_enum_values(self):
        assert Platform.MACOS.value == "macos"
        assert Platform.LINUX.value == "linux"
        assert Platform.WINDOWS.value == "windows"
        assert Platform.WSL.value == "wsl"


@pytest.mark.unit
class TestDetectPlatform:
    def test_darwin(self, monkeypatch):
        detect_platform.cache_clear()
        monkeypatch.setattr("ai_rules.platform._platform.system", lambda: "Darwin")
        result = detect_platform()
        assert result == Platform.MACOS
        detect_platform.cache_clear()

    def test_windows(self, monkeypatch):
        detect_platform.cache_clear()
        monkeypatch.setattr("ai_rules.platform._platform.system", lambda: "Windows")
        result = detect_platform()
        assert result == Platform.WINDOWS
        detect_platform.cache_clear()

    def test_linux(self, monkeypatch):
        detect_platform.cache_clear()
        monkeypatch.setattr("ai_rules.platform._platform.system", lambda: "Linux")
        monkeypatch.setattr(
            "ai_rules.platform._platform.uname",
            lambda: type("U", (), {"release": "6.1.0-generic"})(),
        )
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
        result = detect_platform()
        assert result == Platform.LINUX
        detect_platform.cache_clear()

    def test_wsl_via_release(self, monkeypatch):
        detect_platform.cache_clear()
        monkeypatch.setattr("ai_rules.platform._platform.system", lambda: "Linux")
        monkeypatch.setattr(
            "ai_rules.platform._platform.uname",
            lambda: type("U", (), {"release": "5.15.0-1-microsoft-standard-WSL2"})(),
        )
        monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
        result = detect_platform()
        assert result == Platform.WSL
        detect_platform.cache_clear()

    def test_wsl_via_env(self, monkeypatch):
        detect_platform.cache_clear()
        monkeypatch.setattr("ai_rules.platform._platform.system", lambda: "Linux")
        monkeypatch.setattr(
            "ai_rules.platform._platform.uname",
            lambda: type("U", (), {"release": "6.1.0-generic"})(),
        )
        monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
        result = detect_platform()
        assert result == Platform.WSL
        detect_platform.cache_clear()

    def test_unknown_falls_back_to_linux(self, monkeypatch):
        detect_platform.cache_clear()
        monkeypatch.setattr("ai_rules.platform._platform.system", lambda: "FreeBSD")
        result = detect_platform()
        assert result == Platform.LINUX
        detect_platform.cache_clear()


@pytest.mark.unit
class TestIsPlatform:
    def test_matches_detected(self, monkeypatch):
        monkeypatch.setattr("ai_rules.platform.detect_platform", lambda: Platform.MACOS)
        assert is_platform(Platform.MACOS) is True
        assert is_platform(Platform.WINDOWS) is False


@pytest.mark.unit
class TestGetAppdataDir:
    def test_returns_appdata_path(self, monkeypatch):
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        from pathlib import Path

        assert get_appdata_dir() == Path("C:\\Users\\test\\AppData\\Roaming")

    def test_falls_back_to_home_when_unset(self, monkeypatch):
        monkeypatch.delenv("APPDATA", raising=False)
        from pathlib import Path

        result = get_appdata_dir()
        assert result == Path.home() / "AppData" / "Roaming"


@pytest.mark.unit
class TestGetUvToolsDir:
    def test_override_wins(self, monkeypatch):
        from pathlib import Path

        monkeypatch.setenv("UV_TOOL_DIR", "/custom/tools")
        assert get_uv_tools_dir() == Path("/custom/tools")

    def test_windows_default(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        result = get_uv_tools_dir()
        assert "uv" in str(result) and "tools" in str(result)

    def test_unix_default(self, monkeypatch):
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = get_uv_tools_dir()
        result_str = result.as_posix()
        assert "uv/tools" in result_str

    def test_unix_xdg_override(self, monkeypatch):
        from pathlib import Path

        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        result = get_uv_tools_dir()
        assert result == Path("/custom/data/uv/tools")


@pytest.mark.unit
class TestGetLibPathFragment:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        result = get_lib_path_fragment("python3.12")
        assert "Lib" in result
        assert "site-packages" in result
        assert "python3.12" not in result

    def test_unix(self, monkeypatch):
        result = get_lib_path_fragment("python3.12")
        assert "python3.12" in result
        assert "site-packages" in result


@pytest.mark.unit
class TestGetDefaultEditor:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        assert get_default_editor() == "notepad"

    def test_unix(self, monkeypatch):
        assert get_default_editor() == "vi"


@pytest.mark.unit
class TestGetGooseConfigDir:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        result = get_goose_config_dir()
        result_str = str(result)
        assert "Block" in result_str
        assert "goose" in result_str

    def test_unix(self, monkeypatch):
        from pathlib import Path

        result = get_goose_config_dir()
        assert result == Path("~/.config/goose")


@pytest.mark.unit
class TestGetStatuslineConfigDir:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(
            "ai_rules.platform.detect_platform", lambda: Platform.WINDOWS
        )
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        result = get_statusline_config_dir()
        assert "claude-statusline" in str(result)

    def test_unix(self, monkeypatch):
        from pathlib import Path

        result = get_statusline_config_dir()
        assert result == Path("~/.config/claude-statusline")
