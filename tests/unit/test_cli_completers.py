"""Tests locking CLI completer wiring and the facade patch seam.

The --only completers resolve their component list by attribute name on
ai_rules.cli.components at completion time (to keep command imports lazy).
A typo or rename there is invisible to mypy and would only surface as
silently broken shell completion — these tests make it fail CI instead.
"""

from __future__ import annotations

import click
import pytest

from ai_rules.cli import main

COMPLETER_CASES = [
    ("install", "INSTALL_COMPONENTS", True),
    ("status", "STATUS_COMPONENTS", False),
    ("uninstall", "UNINSTALL_COMPONENTS", False),
    ("diff", "DIFF_COMPONENTS", False),
    ("validate", "VALIDATE_COMPONENTS", False),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_name,components_attr,filterable_only", COMPLETER_CASES
)
def test_only_completer_returns_component_ids(
    command_name, components_attr, filterable_only
):
    import ai_rules.cli.components as components_module

    command = main.commands[command_name]
    param = next(p for p in command.params if p.name == "component_filter")
    ctx = click.Context(command)

    items = param.shell_complete(ctx, "")

    components = getattr(components_module, components_attr)
    expected = [
        c.component_id for c in components if c.filterable or not filterable_only
    ]
    assert [item.value for item in items] == expected
    assert expected, f"{components_attr} produced no completion candidates"


@pytest.mark.unit
def test_build_cli_context_honors_facade_patch(tmp_path, monkeypatch, mock_home):
    """build_cli_context must resolve get_config_dir through the facade seam."""
    import ai_rules.cli as cli_facade

    from ai_rules.cli.components import STATUS_COMPONENTS

    config_dir = tmp_path / "facade-config"
    config_dir.mkdir()
    monkeypatch.setattr(cli_facade, "get_config_dir", lambda: config_dir)

    cli_ctx = cli_facade.build_cli_context(STATUS_COMPONENTS, None, None)

    assert cli_ctx.config_dir == config_dir
