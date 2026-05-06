import pytest

from ai_rules.cli.components import (
    DIFF_COMPONENTS,
    INSTALL_COMPONENTS,
    STATUS_COMPONENTS,
    UNINSTALL_COMPONENTS,
    VALIDATE_COMPONENTS,
)


@pytest.mark.unit
def test_install_components_run_in_expected_order():
    assert [component.label for component in INSTALL_COMPONENTS] == [
        "Optional Tools",
        "Settings Cache",
        "Legacy Migration",
        "Install Confirmation",
        "Settings Cache Cleanup",
        "User-Level Configuration",
        "MCPs",
        "Claude Plugins",
        "Cleanup",
        "Shell Completions",
    ]


@pytest.mark.unit
def test_status_components_cover_managed_lifecycle_surfaces():
    assert [component.label for component in STATUS_COMPONENTS] == [
        "User-Level Configuration",
        "Settings Cache",
        "MCPs",
        "Claude Plugins",
        "Claude Extensions",
        "Skills",
        "Optional Tools",
        "Shell Completions",
    ]


@pytest.mark.unit
def test_diff_components_include_drift_sources():
    assert [component.label for component in DIFF_COMPONENTS] == [
        "User-Level Configuration",
        "Settings Cache",
        "MCPs",
        "Claude Plugins",
        "Claude Extensions",
        "Skills",
    ]


@pytest.mark.unit
def test_validate_components_check_source_files():
    assert [component.label for component in VALIDATE_COMPONENTS] == ["Source Files"]


@pytest.mark.unit
def test_uninstall_components_only_remove_symlinks_and_mcps():
    assert [component.label for component in UNINSTALL_COMPONENTS] == [
        "User-Level Configuration",
        "MCPs",
    ]
