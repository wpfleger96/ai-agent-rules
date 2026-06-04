"""Tests for AgentsMdComponent lifecycle."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from rich.console import Console

from ai_rules.agents.shared import SharedAgent
from ai_rules.cli.components.agents_md import AgentsMdComponent
from ai_rules.cli.context import CliContext
from ai_rules.config import Config


def make_context(
    tmp_path: Path,
    *,
    config: Config | None = None,
    selected_targets: tuple = (),
) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=config or Config(),
        profile_name=None,
        all_targets=selected_targets,
        selected_targets=selected_targets,
    )


@pytest.mark.unit
class TestAgentsMdComponentInstall:
    """Test AgentsMdComponent install behavior."""

    def test_install_with_agents_md_calls_build_on_shared_agent(
        self, test_repo: Path, mock_home: Path
    ) -> None:
        config = Config(agents_md="## Extra content")
        shared = SharedAgent(test_repo, config)
        ctx = make_context(test_repo, config=config, selected_targets=(shared,))

        result = AgentsMdComponent().install(ctx)

        assert result.changed is True
        assert result.counts.get("cache_updated") == 1
        cache_path = config.get_merged_agents_md_path()
        assert cache_path is not None
        assert cache_path.exists()

    def test_install_without_agents_md_is_noop(
        self, test_repo: Path, mock_home: Path
    ) -> None:
        config = Config(agents_md="")
        shared = SharedAgent(test_repo, config)
        ctx = make_context(test_repo, config=config, selected_targets=(shared,))

        result = AgentsMdComponent().install(ctx)

        assert result.changed is False
        assert result.counts == {}

    def test_install_without_shared_agent_is_noop(
        self, test_repo: Path, mock_home: Path
    ) -> None:
        config = Config(agents_md="## Extra content")
        ctx = make_context(test_repo, config=config, selected_targets=())

        result = AgentsMdComponent().install(ctx)

        assert result.changed is False


@pytest.mark.unit
class TestAgentsMdComponentUninstall:
    """Test AgentsMdComponent uninstall behavior."""

    def test_uninstall_removes_cache_file_when_present(
        self, test_repo: Path, mock_home: Path
    ) -> None:
        config = Config(agents_md="## Extra content")
        shared = SharedAgent(test_repo, config)
        # Pre-build the cache so a file exists to remove
        shared.build_merged_agents_md()
        cache_path = config.get_merged_agents_md_path()
        assert cache_path is not None and cache_path.exists()

        ctx = make_context(test_repo, config=config, selected_targets=(shared,))
        result = AgentsMdComponent().uninstall(ctx)

        assert result.changed is True
        assert not cache_path.exists()

    def test_uninstall_is_noop_when_cache_absent(
        self, test_repo: Path, mock_home: Path
    ) -> None:
        config = Config(agents_md="## Extra content")
        shared = SharedAgent(test_repo, config)
        ctx = make_context(test_repo, config=config, selected_targets=(shared,))

        result = AgentsMdComponent().uninstall(ctx)

        assert result.changed is False
