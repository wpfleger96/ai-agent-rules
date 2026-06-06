import os
import subprocess
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
class TestRegistryLifecycle:
    def test_install_dry_run_completes_successfully(self, run_cli_with_config):
        run, home_dir, config_dir = run_cli_with_config
        result = run(["install", "--dry-run", "-y", "--config-dir", str(config_dir)])
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0
        assert "Dry run" in output

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
class TestUpgradeCheckFailed:
    """E2E tests that a failed update check surfaces a warning, not false success."""

    BROKEN_INDEX = "http://localhost:1/nonexistent"
    RECEIPT_TOML = (
        "[tool]\n"
        'requirements = [{ name = "ai-agent-rules" }]\n'
        "entrypoints = [\n"
        '    { name = "ai-agent-rules", install-path = "/tmp/fake/ai-agent-rules",'
        ' from = "ai-agent-rules" },\n'
        '    { name = "ai-rules", install-path = "/tmp/fake/ai-rules",'
        ' from = "ai-agent-rules" },\n'
        "]\n"
    )

    @pytest.fixture
    def broken_index_cli(self, e2e_home, tmp_path):
        """CLI runner with a fake PYPI receipt and an unreachable index URL."""
        import shutil

        from pathlib import Path

        home_dir, env_overrides = e2e_home
        repo_root = Path(__file__).parents[2]
        src_path = repo_root / "src"

        real_tools = Path.home() / ".local" / "share" / "uv" / "tools"
        real_ai_rules = real_tools / "ai-agent-rules"
        if not real_ai_rules.exists():
            pytest.skip("ai-agent-rules not installed via uv tool")

        fake_tools = tmp_path / "uv-tools"
        shutil.copytree(real_ai_rules, fake_tools / "ai-agent-rules", symlinks=True)
        (fake_tools / "ai-agent-rules" / "uv-receipt.toml").write_text(
            self.RECEIPT_TOML
        )

        def _run(args, extra_env=None, timeout=30):
            base_env = {**os.environ, **env_overrides}
            existing_pythonpath = base_env.get("PYTHONPATH", "")
            base_env["PYTHONPATH"] = (
                str(src_path)
                if not existing_pythonpath
                else os.pathsep.join([str(src_path), existing_pythonpath])
            )
            base_env["UV_TOOL_DIR"] = str(fake_tools)
            base_env["UV_DEFAULT_INDEX"] = self.BROKEN_INDEX
            base_env["UV_INDEX_URL"] = self.BROKEN_INDEX
            base_env["PIP_INDEX_URL"] = self.BROKEN_INDEX
            if extra_env:
                base_env.update(extra_env)
            return subprocess.run(
                [sys.executable, "-m", "ai_rules.cli", *args],
                capture_output=True,
                encoding="utf-8",
                check=False,
                cwd=repo_root,
                env=base_env,
                timeout=timeout,
            )

        return _run

    def test_upgrade_check_shows_warning(self, broken_index_cli):
        result = broken_index_cli(["upgrade", "--check"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "Could not check" in output
        assert "already up to date" not in output.lower()

    def test_version_shows_check_failed(self, broken_index_cli):
        result = broken_index_cli(["--version"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "version" in output.lower()
        assert "Could not check for updates" in output

    def test_tool_show_displays_check_failed(self, broken_index_cli):
        result = broken_index_cli(["tool", "show", "ai-agent-rules"])
        output = strip_ansi(result.stdout + result.stderr)
        assert "check failed" in output.lower()
        assert "up to date" not in output.lower()


@pytest.mark.e2e
@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
class TestWindowsSpecific:
    def test_powershell_in_completions(self, run_cli):
        result = run_cli(["completions", "status"])
        output = strip_ansi(result.stdout + result.stderr).lower()
        assert "powershell" in output
