"""Tests for MCPComponent skipping targets with excluded settings files."""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rich.console import Console

from ai_rules.agents.base import Agent
from ai_rules.cli.components.mcp import MCPComponent
from ai_rules.cli.context import CliContext
from ai_rules.config import Config
from ai_rules.mcp import OperationResult


def _make_agent(is_excluded: bool) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.is_settings_file_excluded = is_excluded
    mgr = MagicMock()
    agent.get_mcp_manager.return_value = mgr
    agent.install_mcps.return_value = (
        OperationResult.ALREADY_INSTALLED,
        "already up to date",
        [],
    )
    agent.get_mcp_status.return_value = None
    return agent


def make_context(tmp_path: Path, targets: tuple) -> CliContext:
    return CliContext(
        console=Console(file=StringIO()),
        config_dir=tmp_path,
        config=Config(),
        profile_name=None,
        all_targets=targets,
        selected_targets=targets,
        yes=True,
    )


@pytest.mark.unit
def test_mcp_install_skips_excluded_target(tmp_path: Path) -> None:
    excluded_agent = _make_agent(is_excluded=True)
    ctx = make_context(tmp_path, (excluded_agent,))

    MCPComponent().install(ctx)

    excluded_agent.install_mcps.assert_not_called()


@pytest.mark.unit
def test_mcp_status_skips_excluded_target(tmp_path: Path) -> None:
    excluded_agent = _make_agent(is_excluded=True)
    ctx = make_context(tmp_path, (excluded_agent,))

    MCPComponent().status(ctx)

    excluded_agent.get_mcp_status.assert_not_called()


@pytest.mark.unit
def test_mcp_install_processes_non_excluded_target(tmp_path: Path) -> None:
    normal_agent = _make_agent(is_excluded=False)
    ctx = make_context(tmp_path, (normal_agent,))

    MCPComponent().install(ctx)

    normal_agent.install_mcps.assert_called_once()
