import sys

import pytest

from tests.e2e.helpers import strip_ansi


@pytest.mark.e2e
class TestStatus:
    def test_status_header_and_exit_code(self, run_cli):
        result = run_cli(["status"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "AI Rules Status" in output
        assert result.returncode == 1


@pytest.mark.e2e
class TestValidate:
    def test_validate_bundled_config(self, run_cli):
        result = run_cli(["validate"])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "All source files are valid!" in output


@pytest.mark.e2e
class TestListAgents:
    def test_list_agents_table_and_columns(self, run_cli):
        result = run_cli(["list-agents"])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Available AI Agents" in output
        assert "ID" in output
        assert "Name" in output
        assert "Symlinks" in output
        assert "Status" in output


@pytest.mark.e2e
class TestDiff:
    def test_diff_header_and_exit_code(self, run_cli):
        result = run_cli(["diff"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "Configuration Differences" in output
        assert result.returncode == 0


@pytest.mark.e2e
class TestInstallDryRun:
    def test_dry_run_header_and_no_files_created(self, run_cli_with_config):
        _run, home_dir, config_dir = run_cli_with_config
        result = _run(["install", "--dry-run", "-y", "--config-dir", str(config_dir)])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Dry run" in output
        assert not (home_dir / ".claude").exists()


@pytest.mark.e2e
class TestCompletionsStatus:
    def test_completions_shows_shells(self, run_cli):
        result = run_cli(["completions", "status"])
        output = strip_ansi(result.stdout + result.stderr).lower()
        assert result.returncode == 0
        assert "bash" in output
        assert "zsh" in output


@pytest.mark.e2e
class TestRegistryLifecycle:
    def test_status_shows_optional_tools(self, run_cli):
        result = run_cli(["status"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "Optional Tools" in output
        assert "statusline" in output

    def test_uninstall_shows_optional_tools(self, run_cli):
        result = run_cli(["uninstall", "-y"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "Optional Tools" in output
        assert "statusline" in output

    def test_install_only_filter_accepts_settings(self, run_cli_with_config):
        run, home_dir, config_dir = run_cli_with_config
        result = run(
            [
                "install",
                "--dry-run",
                "-y",
                "--only",
                "settings",
                "--config-dir",
                str(config_dir),
            ]
        )
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Invalid component ID" not in output

    def test_install_only_filter_rejects_invalid(self, run_cli_with_config):
        run, home_dir, config_dir = run_cli_with_config
        result = run(
            [
                "install",
                "--dry-run",
                "-y",
                "--only",
                "nonexistent",
                "--config-dir",
                str(config_dir),
            ]
        )
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 1
        assert "Invalid component ID" in output


@pytest.mark.e2e
@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
class TestWindowsSpecific:
    def test_powershell_in_completions(self, run_cli):
        result = run_cli(["completions", "status"])
        output = strip_ansi(result.stdout + result.stderr).lower()
        assert "powershell" in output
