"""End-to-end install-and-inspect tests.

Unlike the dry-run/informational E2E tests, these drive a *real* ``install``
(no ``--dry-run``) against a standalone config dir into an isolated HOME and
then assert against the resulting filesystem: that symlinks exist, resolve to
the right content, survive re-installs, and honor backups/repair/exclude/
override/agent-selection. This is the coverage that gives confidence a
refactor of the symlink/merge pipeline preserves real on-disk behavior.
"""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from tests.e2e.helpers import (
    CORE_COMPONENTS,
    CliResult,
    CliRunner,
    build_config_dir,
    find_backups,
    is_windows,
    strip_ansi,
)


def _install(run: CliRunner, config_dir: Path, *extra: str) -> CliResult:
    return run(
        [
            "install",
            "-y",
            "--skip-completions",
            "--only",
            CORE_COMPONENTS,
            "--config-dir",
            str(config_dir),
            *extra,
        ]
    )


@pytest.mark.e2e
class TestRealInstallSymlinks:
    def test_install_succeeds_and_reports_created(self, cli_with_toy_config):
        run, home, config = cli_with_toy_config
        result = _install(run, config)
        output = strip_ansi(result.stdout + result.stderr)
        assert result.returncode == 0, output
        assert "Created" in output

    def test_markdown_symlinks_resolve_to_sources(self, cli_with_toy_config):
        """Instruction/markdown files symlink straight to their source files."""
        run, home, config = cli_with_toy_config
        _install(run, config)

        cases = {
            home / ".claude" / "CLAUDE.md": config / "claude" / "CLAUDE.md",
            home / ".codex" / "AGENTS.md": config / "codex" / "AGENTS.md",
            home / ".gemini" / "GEMINI.md": config / "gemini" / "GEMINI.md",
            home / "AGENTS.md": config / "AGENTS.md",
        }
        for target, source in cases.items():
            assert target.is_symlink(), f"{target} is not a symlink"
            assert target.resolve() == source.resolve()
            assert target.read_text(encoding="utf-8") == source.read_text(
                encoding="utf-8"
            )

    def test_settings_symlink_resolves_with_source_keys(self, cli_with_toy_config):
        """Merged settings keep the source keys and gain the managed marker path."""
        run, home, config = cli_with_toy_config
        _install(run, config)

        settings_link = home / ".claude" / "settings.json"
        assert settings_link.exists()
        data = json.loads(settings_link.read_text(encoding="utf-8"))
        assert data["theme"] == "dark"

    def test_claude_extensions_symlinked(self, cli_with_toy_config):
        run, home, config = cli_with_toy_config
        _install(run, config)

        agent = home / ".claude" / "agents" / "demo-agent.md"
        command = home / ".claude" / "commands" / "hello.md"
        assert agent.is_symlink()
        assert command.is_symlink()
        assert agent.resolve() == (config / "claude" / "agents" / "demo-agent.md")
        assert command.resolve() == (config / "claude" / "commands" / "hello.md")

    def test_skills_symlinked_into_agent_dirs(self, cli_with_toy_config):
        """The shared skill is fanned out to each agent's skills dir."""
        run, home, config = cli_with_toy_config
        _install(run, config)

        source = config / "skills" / "demo-skill"
        expected = [
            home / ".claude" / "skills" / "demo-skill",
            home / ".agents" / "skills" / "demo-skill",  # codex (+ gemini alias)
        ]
        if not is_windows():
            expected.append(home / ".config" / "agents" / "skills" / "demo-skill")
        for link in expected:
            assert link.is_symlink(), f"missing skill link {link}"
            assert link.resolve() == source.resolve()


@pytest.mark.e2e
class TestInstallIdempotency:
    def test_reinstall_is_idempotent(self, cli_with_toy_config):
        run, home, config = cli_with_toy_config
        first = _install(run, config)
        assert first.returncode == 0

        second = _install(run, config)
        output = strip_ansi(second.stdout + second.stderr)
        assert second.returncode == 0, output
        assert "up to date" in output.lower() or "unchanged" in output.lower()

    def test_reinstall_creates_no_backups(self, cli_with_toy_config):
        """A second install over correct symlinks must not back anything up."""
        run, home, config = cli_with_toy_config
        _install(run, config)
        _install(run, config)
        assert find_backups(home) == []


@pytest.mark.e2e
class TestBackupAndRepair:
    def test_existing_real_file_is_backed_up(self, cli_with_toy_config):
        run, home, config = cli_with_toy_config
        target = home / ".claude" / "CLAUDE.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("PRE-EXISTING USER CONTENT\n", encoding="utf-8")

        _install(run, config)

        assert target.is_symlink()
        assert target.resolve() == (config / "claude" / "CLAUDE.md").resolve()
        backups = find_backups(home / ".claude")
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "PRE-EXISTING USER CONTENT\n"

    def test_dangling_symlink_is_repaired(self, cli_with_toy_config):
        run, home, config = cli_with_toy_config
        target = home / ".claude" / "CLAUDE.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(home / "does-not-exist.md")
        assert target.is_symlink() and not target.exists()

        _install(run, config)

        assert target.is_symlink()
        assert target.resolve() == (config / "claude" / "CLAUDE.md").resolve()
        assert target.exists()


@pytest.mark.e2e
class TestExcludeAndOverride:
    def test_excluded_symlink_is_skipped(self, isolated_home, toy_config, tmp_path):
        from tests.e2e.helpers import make_cli_runner

        home, env = isolated_home
        # User config in HOME excludes a specific target.
        (home / ".ai-agent-rules-config.yaml").write_text(
            "version: 1\nexclude_symlinks:\n  - ~/.gemini/GEMINI.md\n",
            encoding="utf-8",
        )
        run = make_cli_runner(home, env)
        _install(run, toy_config)

        assert not (home / ".gemini" / "GEMINI.md").exists()
        # Non-excluded targets are still installed.
        assert (home / ".claude" / "CLAUDE.md").is_symlink()

    def test_settings_override_is_merged(self, isolated_home, tmp_path):
        from tests.e2e.helpers import make_cli_runner

        home, env = isolated_home
        config = build_config_dir(tmp_path / "rules", claude_settings={"theme": "dark"})
        (home / ".ai-agent-rules-config.yaml").write_text(
            "version: 1\n"
            "settings_overrides:\n"
            "  claude:\n"
            "    theme: light\n"
            "    extra: added\n",
            encoding="utf-8",
        )
        run = make_cli_runner(home, env)
        _install(run, config)

        data = json.loads((home / ".claude" / "settings.json").read_text("utf-8"))
        assert data["theme"] == "light"  # override wins
        assert data["extra"] == "added"  # override adds keys


@pytest.mark.e2e
class TestAgentSelection:
    def test_agents_flag_limits_install(self, cli_with_toy_config):
        """``--agents claude`` installs claude (+ shared) but not other agents."""
        run, home, config = cli_with_toy_config
        run(
            [
                "install",
                "-y",
                "--skip-completions",
                "--only",
                CORE_COMPONENTS,
                "--agents",
                "claude",
                "--config-dir",
                str(config),
            ]
        )

        assert (home / ".claude" / "CLAUDE.md").is_symlink()
        assert (home / "AGENTS.md").is_symlink()  # shared always included
        assert not (home / ".codex" / "AGENTS.md").exists()
        assert not (home / ".gemini" / "GEMINI.md").exists()
