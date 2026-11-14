from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

from ai_rules.agents.claude import ClaudeAgent
from ai_rules.agents.shared import SharedAgent
from ai_rules.cli.components.source_files import SourceFilesComponent
from ai_rules.cli.context import CliContext, ComponentResult
from ai_rules.config import Config
from ai_rules.targets.base import ConfigTarget


def _validate(config: Config, *targets: ConfigTarget) -> ComponentResult:
    ctx = CliContext(
        console=Console(file=StringIO()),
        config_dir=Path(),
        config=config,
        profile_name=None,
        all_targets=targets,
        selected_targets=targets,
    )
    return SourceFilesComponent().validate(ctx)


@pytest.mark.unit
class TestSourceFilesValidate:
    def test_unbuilt_agents_md_cache_is_not_an_issue(
        self,
        test_repo: Path,
        mock_home: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config = Config(agents_md="## Extra\n")
        shared = SharedAgent(test_repo, config)

        result = _validate(config, shared)

        output = capsys.readouterr().out
        assert result.ok is True
        assert result.counts["errors"] == 0
        assert "AGENTS.md (built on install)" in output
        assert not (mock_home / ".ai-agent-rules").exists()

    def test_missing_bundled_source_is_still_an_issue(
        self,
        test_repo: Path,
        mock_home: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (test_repo / "claude" / "CLAUDE.md").unlink()
        config = Config(agents_md="## Extra\n")
        claude = ClaudeAgent(test_repo, config)
        shared = SharedAgent(test_repo, config)

        result = _validate(config, claude, shared)

        output = capsys.readouterr().out
        assert result.ok is False
        assert result.counts["errors"] == 1
        assert "Source file does not exist" in output
