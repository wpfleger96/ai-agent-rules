import sys

import pytest

from tests.e2e.helpers import strip_ansi


@pytest.mark.e2e
class TestHelp:
    def test_top_level_help(self, run_cli):
        result = run_cli(["--help"])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Usage:" in output
        assert "install" in output
        assert "status" in output
        assert "validate" in output
        assert "list-agents" in output
        assert "diff" in output
        assert "completions" in output

    def test_install_help(self, run_cli):
        result = run_cli(["install", "--help"])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "--dry-run" in output


@pytest.mark.e2e
class TestStatus:
    def test_status_header(self, run_cli):
        result = run_cli(["status"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "AI Rules Status" in output

    def test_status_exit_1_nothing_installed(self, run_cli):
        result = run_cli(["status"])
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
    def test_list_agents_table(self, run_cli):
        result = run_cli(["list-agents"])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Available AI Agents" in output

    def test_list_agents_columns(self, run_cli):
        result = run_cli(["list-agents"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "ID" in output
        assert "Name" in output
        assert "Symlinks" in output
        assert "Status" in output


@pytest.mark.e2e
class TestDiff:
    def test_diff_header(self, run_cli):
        result = run_cli(["diff"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "Configuration Differences" in output

    def test_diff_always_exit_0(self, run_cli):
        result = run_cli(["diff"])
        assert result.returncode == 0


@pytest.mark.e2e
class TestInstallDryRun:
    def test_dry_run_header(self, run_cli_with_config):
        _run, home_dir, config_dir = run_cli_with_config
        result = _run(["install", "--dry-run", "-y", "--config-dir", str(config_dir)])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Dry run" in output

    def test_dry_run_no_files_created(self, run_cli_with_config):
        _run, home_dir, config_dir = run_cli_with_config
        _run(["install", "--dry-run", "-y", "--config-dir", str(config_dir)])
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
@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
class TestWindowsSpecific:
    def test_powershell_in_completions(self, run_cli):
        result = run_cli(["completions", "status"])
        output = strip_ansi(result.stdout + result.stderr).lower()
        assert "powershell" in output
