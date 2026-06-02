
from unittest.mock import patch

import pytest

from ai_rules.completions import (
    _LEGACY_MARKER_END,
    _LEGACY_MARKER_START,
    COMPLETION_MARKER_END,
    COMPLETION_MARKER_START,
    detect_shell,
    find_config_file,
    generate_completion_script,
    get_shell_config_candidates,
    install_completion,
    is_completion_installed,
    is_legacy_completion_block,
    uninstall_completion,
    update_completion,
)


@pytest.mark.unit
@pytest.mark.completions
class TestDetectShell:
    """Test shell detection from environment."""

    def test_detect_bash(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(shellingham, "detect_shell", lambda: ("bash", "/bin/bash"))
        assert detect_shell() == "bash"

    def test_detect_zsh(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(
            shellingham, "detect_shell", lambda: ("zsh", "/usr/bin/zsh")
        )
        assert detect_shell() == "zsh"

    def test_unsupported_shell(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(shellingham, "detect_shell", lambda: ("fish", "/bin/fish"))
        assert detect_shell() is None

    def test_no_shell_env(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(
            shellingham,
            "detect_shell",
            lambda: (_ for _ in ()).throw(shellingham.ShellDetectionFailure()),
        )
        monkeypatch.delenv("SHELL", raising=False)
        assert detect_shell() is None


@pytest.mark.unit
@pytest.mark.completions
class TestGetShellConfigCandidates:
    """Test finding shell config file candidates."""

    def test_bash_candidates(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        bashrc = home / ".bashrc"
        bashrc.write_text("# bashrc")

        with patch("ai_rules.completions.Path.home", return_value=home):
            candidates = get_shell_config_candidates("bash")
            assert len(candidates) == 1
            assert candidates[0] == bashrc

    def test_zsh_candidates(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        zshrc = home / ".zshrc"
        zshrc.write_text("# zshrc")

        with patch("ai_rules.completions.Path.home", return_value=home):
            candidates = get_shell_config_candidates("zsh")
            assert len(candidates) == 1
            assert candidates[0] == zshrc

    def test_multiple_candidates(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        bashrc = home / ".bashrc"
        bash_profile = home / ".bash_profile"
        bashrc.write_text("# bashrc")
        bash_profile.write_text("# bash_profile")

        with patch("ai_rules.completions.Path.home", return_value=home):
            candidates = get_shell_config_candidates("bash")
            assert len(candidates) == 2
            assert bashrc in candidates
            assert bash_profile in candidates

    def test_no_existing_files(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        with patch("ai_rules.completions.Path.home", return_value=home):
            candidates = get_shell_config_candidates("bash")
            assert len(candidates) == 0


@pytest.mark.unit
@pytest.mark.completions
class TestFindConfigFile:
    """Test finding the appropriate config file."""

    def test_finds_first_existing(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        bashrc = home / ".bashrc"
        bashrc.write_text("# bashrc")

        with patch("ai_rules.completions.Path.home", return_value=home):
            config_file = find_config_file("bash")
            assert config_file == bashrc

    def test_returns_none_if_no_candidates(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        with patch("ai_rules.completions.Path.home", return_value=home):
            config_file = find_config_file("bash")
            assert config_file is None


@pytest.mark.unit
@pytest.mark.completions
class TestIsCompletionInstalled:
    """Test checking if completion is installed."""

    def test_not_installed(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        config_file.write_text("# Some config\n")

        assert is_completion_installed(config_file) is False

    def test_installed_current_markers(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"# Some config\n{COMPLETION_MARKER_START}\neval something\n{COMPLETION_MARKER_END}\n"
        )

        assert is_completion_installed(config_file) is True

    def test_installed_legacy_markers(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"# Some config\n{_LEGACY_MARKER_START}\neval something\n{_LEGACY_MARKER_END}\n"
        )

        assert is_completion_installed(config_file) is True

    def test_file_not_exists(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        assert is_completion_installed(config_file) is False


@pytest.mark.unit
@pytest.mark.completions
class TestIsLegacyCompletionBlock:
    """Test detecting legacy completion blocks."""

    def test_legacy_markers(self, tmp_path):
        config_file = tmp_path / ".zshrc"
        config_file.write_text(
            f'{_LEGACY_MARKER_START}\neval "$(_AI_RULES_COMPLETE=zsh_source ai-rules)"\n{_LEGACY_MARKER_END}\n'
        )
        assert is_legacy_completion_block(config_file) is True

    def test_current_markers_without_command_v(self, tmp_path):
        config_file = tmp_path / ".zshrc"
        config_file.write_text(
            f'{COMPLETION_MARKER_START}\neval "$(_AI_AGENT_RULES_COMPLETE=zsh_source ai-agent-rules)"\n{COMPLETION_MARKER_END}\n'
        )
        assert is_legacy_completion_block(config_file) is True

    def test_current_format_not_legacy(self, tmp_path):
        config_file = tmp_path / ".zshrc"
        script = generate_completion_script("zsh")
        config_file.write_text(script)
        assert is_legacy_completion_block(config_file) is False

    def test_file_not_exists(self, tmp_path):
        config_file = tmp_path / ".zshrc"
        assert is_legacy_completion_block(config_file) is False

    def test_no_markers_at_all(self, tmp_path):
        config_file = tmp_path / ".zshrc"
        config_file.write_text("# just a normal zshrc\n")
        assert is_legacy_completion_block(config_file) is False


@pytest.mark.unit
@pytest.mark.completions
class TestGenerateCompletionScript:
    """Test completion script generation."""

    def test_generates_bash_script(self):
        script = generate_completion_script("bash")

        assert COMPLETION_MARKER_START in script
        assert COMPLETION_MARKER_END in script
        assert "command -v ai-agent-rules" in script
        assert "_AI_AGENT_RULES_COMPLETE=bash_source ai-agent-rules" in script
        assert "complete -o nosort -F _ai_agent_rules_completion ai-rules" in script

    def test_generates_zsh_script(self):
        script = generate_completion_script("zsh")

        assert COMPLETION_MARKER_START in script
        assert COMPLETION_MARKER_END in script
        assert "command -v ai-agent-rules" in script
        assert "_AI_AGENT_RULES_COMPLETE=zsh_source ai-agent-rules" in script
        assert "compdef _ai_agent_rules_completion ai-rules" in script

    def test_unsupported_shell_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported shell"):
            generate_completion_script("ksh")

    def test_contains_if_guard(self):
        for shell in ("bash", "zsh"):
            script = generate_completion_script(shell)
            assert "if command -v ai-agent-rules >/dev/null 2>&1; then" in script
            assert "fi" in script


@pytest.mark.unit
@pytest.mark.completions
class TestInstallCompletion:
    """Test completion installation."""

    def test_install_bash(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        bashrc = home / ".bashrc"
        bashrc.write_text("# bashrc\n")

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = install_completion("bash", dry_run=False)

            assert success is True
            assert "Completion installed" in message
            content = bashrc.read_text()
            assert COMPLETION_MARKER_START in content
            assert "_AI_AGENT_RULES_COMPLETE=bash_source ai-agent-rules" in content

    def test_install_dry_run(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        bashrc = home / ".bashrc"
        bashrc.write_text("# bashrc\n")

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = install_completion("bash", dry_run=True)

            assert success is True
            assert "Would append" in message
            content = bashrc.read_text()
            assert COMPLETION_MARKER_START not in content

    def test_install_already_installed(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        bashrc = home / ".bashrc"
        script = generate_completion_script("bash")
        bashrc.write_text(f"# bashrc\n{script}\n")

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = install_completion("bash", dry_run=False)

            assert success is True
            assert "already installed" in message

    def test_install_upgrades_legacy_block(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        bashrc = home / ".bashrc"
        bashrc.write_text(
            f'# bashrc\n{_LEGACY_MARKER_START}\neval "$(_AI_RULES_COMPLETE=bash_source ai-rules)"\n{_LEGACY_MARKER_END}\n'
        )

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = install_completion("bash", dry_run=False)

            assert success is True
            assert "updated" in message.lower()
            content = bashrc.read_text()
            assert _LEGACY_MARKER_START not in content
            assert COMPLETION_MARKER_START in content
            assert "command -v ai-agent-rules" in content

    def test_install_no_config_file(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = install_completion("bash", dry_run=False)

            assert success is False
            assert "No bash config file found" in message

    def test_install_unsupported_shell(self):
        success, message = install_completion("ksh", dry_run=False)

        assert success is False
        assert "Unsupported shell" in message


@pytest.mark.unit
@pytest.mark.completions
class TestUpdateCompletion:
    """Test completion update (in-place replacement)."""

    def test_update_replaces_legacy_block(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        zshrc = home / ".zshrc"
        zshrc.write_text(
            f'# before\n{_LEGACY_MARKER_START}\neval "$(_AI_RULES_COMPLETE=zsh_source ai-rules)"\n{_LEGACY_MARKER_END}\n# after\n'
        )

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = update_completion("zsh")

        assert success is True
        content = zshrc.read_text()
        assert "# before\n" in content
        assert "# after\n" in content
        assert _LEGACY_MARKER_START not in content
        assert COMPLETION_MARKER_START in content
        assert "command -v ai-agent-rules" in content
        assert "compdef _ai_agent_rules_completion ai-rules" in content

    def test_update_replaces_current_block(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        zshrc = home / ".zshrc"
        old_script = f'{COMPLETION_MARKER_START}\neval "$(_AI_AGENT_RULES_COMPLETE=zsh_source ai-agent-rules)"\n{COMPLETION_MARKER_END}'
        zshrc.write_text(f"# before\n{old_script}\n# after\n")

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = update_completion("zsh")

        assert success is True
        content = zshrc.read_text()
        assert "# before\n" in content
        assert "# after\n" in content
        assert "command -v ai-agent-rules" in content

    def test_update_installs_when_no_block(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        zshrc = home / ".zshrc"
        zshrc.write_text("# zshrc\n")

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = update_completion("zsh")

        assert success is True
        assert "installed" in message.lower()
        content = zshrc.read_text()
        assert COMPLETION_MARKER_START in content

    def test_update_dry_run(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        zshrc = home / ".zshrc"
        zshrc.write_text(
            f"# zshrc\n{_LEGACY_MARKER_START}\neval old\n{_LEGACY_MARKER_END}\n"
        )

        with patch("ai_rules.completions.Path.home", return_value=home):
            success, message = update_completion("zsh", dry_run=True)

        assert success is True
        assert "Would update" in message
        content = zshrc.read_text()
        assert _LEGACY_MARKER_START in content


@pytest.mark.unit
@pytest.mark.completions
class TestUninstallCompletion:
    """Test completion uninstallation."""

    def test_uninstall_current_markers(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        script = generate_completion_script("bash")
        config_file.write_text(f"# before\n{script}\n# after\n")

        success, message = uninstall_completion(config_file)

        assert success is True
        assert "Completion removed" in message
        content = config_file.read_text()
        assert COMPLETION_MARKER_START not in content
        assert "# before" in content
        assert "# after" in content

    def test_uninstall_legacy_markers(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"# before\n{_LEGACY_MARKER_START}\neval old\n{_LEGACY_MARKER_END}\n# after\n"
        )

        success, message = uninstall_completion(config_file)

        assert success is True
        assert "Completion removed" in message
        content = config_file.read_text()
        assert _LEGACY_MARKER_START not in content
        assert "# before" in content
        assert "# after" in content

    def test_uninstall_both_blocks(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        config_file.write_text(
            f"# before\n{_LEGACY_MARKER_START}\neval old\n{_LEGACY_MARKER_END}\n"
            f"{COMPLETION_MARKER_START}\neval new\n{COMPLETION_MARKER_END}\n# after\n"
        )

        success, message = uninstall_completion(config_file)

        assert success is True
        content = config_file.read_text()
        assert _LEGACY_MARKER_START not in content
        assert COMPLETION_MARKER_START not in content
        assert "# before" in content
        assert "# after" in content

    def test_uninstall_not_installed(self, tmp_path):
        config_file = tmp_path / ".bashrc"
        config_file.write_text("# bashrc\n")

        success, message = uninstall_completion(config_file)

        assert success is True
        assert "not installed" in message

    def test_uninstall_file_not_exists(self, tmp_path):
        config_file = tmp_path / ".bashrc"

        success, message = uninstall_completion(config_file)

        assert success is False
        assert "not found" in message


@pytest.mark.unit
@pytest.mark.completions
class TestPowerShellDetection:
    def test_detect_powershell_via_shellingham_pwsh(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(
            shellingham, "detect_shell", lambda: ("pwsh", "/usr/bin/pwsh")
        )
        assert detect_shell() == "powershell"

    def test_detect_powershell_via_shellingham_powershell(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(
            shellingham, "detect_shell", lambda: ("powershell", "C:\\powershell.exe")
        )
        assert detect_shell() == "powershell"

    def test_fallback_to_shell_env(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(
            shellingham,
            "detect_shell",
            lambda: (_ for _ in ()).throw(shellingham.ShellDetectionFailure()),
        )
        monkeypatch.setenv("SHELL", "/bin/zsh")
        assert detect_shell() == "zsh"

    def test_no_shell_detected(self, monkeypatch):
        import shellingham

        monkeypatch.setattr(
            shellingham,
            "detect_shell",
            lambda: (_ for _ in ()).throw(shellingham.ShellDetectionFailure()),
        )
        monkeypatch.delenv("SHELL", raising=False)
        assert detect_shell() is None


@pytest.mark.unit
@pytest.mark.completions
class TestPowerShellCompletion:
    def test_generate_powershell_script(self):
        script = generate_completion_script("powershell")
        assert COMPLETION_MARKER_START in script
        assert COMPLETION_MARKER_END in script
        assert "Register-ArgumentCompleter" in script
        assert "Get-Command" in script
        assert "ai-agent-rules" in script
        assert "ai-rules" in script

    def test_install_creates_powershell_profile(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        profile = home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        monkeypatch.setattr(
            "ai_rules.completions._get_powershell_profile_path", lambda: profile
        )
        monkeypatch.setattr("ai_rules.completions.Path.home", lambda: home)
        success, message = install_completion("powershell", dry_run=False)
        assert success is True
        assert profile.exists()
        assert COMPLETION_MARKER_START in profile.read_text()

    def test_powershell_block_not_flagged_as_legacy(self, tmp_path):
        config = tmp_path / "profile.ps1"
        script = generate_completion_script("powershell")
        config.write_text(script)
        assert not is_legacy_completion_block(config)
