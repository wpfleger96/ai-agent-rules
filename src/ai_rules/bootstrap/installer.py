"""Tool installation utilities."""

import os
import re
import shutil
import subprocess
import sys

from enum import Enum, auto
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ToolSource(Enum):
    """Source from which a tool was installed."""

    PYPI = auto()
    GITHUB = auto()


def make_github_install_url(repo: str) -> str:
    """Construct GitHub install URL for uv tool install.

    Args:
        repo: GitHub repository in format "owner/repo"

    Returns:
        Full git+ssh URL for uv tool install
    """
    return f"git+ssh://git@github.com/{repo}.git"


UV_NOT_FOUND_ERROR = "uv not found in PATH. Install from https://docs.astral.sh/uv/"
GITHUB_REPO = "wpfleger96/ai-agent-rules"
STATUSLINE_GITHUB_REPO = "wpfleger96/claude-code-status-line"


def _validate_package_name(package_name: str) -> bool:
    """Validate package name matches PyPI naming convention (PEP 508)."""
    return bool(re.match(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$", package_name))


def get_tool_config_dir(package_name: str = "ai-agent-rules") -> Path:
    """Get config directory for a uv tool installation.

    Computes the expected path where uv tool install places the package:
    $XDG_DATA_HOME/uv/tools/{package}/lib/python{version}/site-packages/ai_rules/config/

    Args:
        package_name: Name of the uv tool package

    Returns:
        Path to the config directory in the uv tools location
    """

    data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"

    return (
        Path(data_home)
        / "uv"
        / "tools"
        / package_name
        / "lib"
        / python_version
        / "site-packages"
        / "ai_rules"
        / "config"
    )


def get_tool_source(package_name: str) -> ToolSource | None:
    """Detect how a uv tool was installed.

    Args:
        package_name: Name of the uv tool package

    Returns:
        ToolSource.PYPI if installed from PyPI
        ToolSource.GITHUB if installed from GitHub
        None if tool not installed or receipt file not found
    """
    data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    receipt_path = Path(data_home) / "uv" / "tools" / package_name / "uv-receipt.toml"

    if not receipt_path.exists():
        return None

    try:
        with open(receipt_path, "rb") as f:
            receipt = tomllib.load(f)

        requirements = receipt.get("tool", {}).get("requirements", [])
        if not requirements:
            return None

        first_req = requirements[0]
        if isinstance(first_req, dict):
            if "git" in first_req and "github.com" in first_req["git"]:
                return ToolSource.GITHUB

        return ToolSource.PYPI

    except (OSError, tomllib.TOMLDecodeError, KeyError, IndexError):
        return None


def is_command_available(command: str) -> bool:
    """Check if a command is available in PATH.

    Args:
        command: Command name to check

    Returns:
        True if command is available, False otherwise
    """
    return shutil.which(command) is not None


def install_tool(
    package_name: str = "ai-agent-rules",
    from_github: bool = False,
    github_url: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Install package as a uv tool.

    Args:
        package_name: Name of package to install (ignored if from_github=True)
        from_github: Install from GitHub instead of PyPI
        github_url: GitHub URL to install from (only used if from_github=True)
        force: Force reinstall if already installed
        dry_run: Show what would be done without executing

    Returns:
        Tuple of (success, message)
    """
    if not from_github and not _validate_package_name(package_name):
        return False, f"Invalid package name: {package_name}"

    if not is_command_available("uv"):
        return False, UV_NOT_FOUND_ERROR

    if from_github:
        source = github_url if github_url else make_github_install_url(GITHUB_REPO)
    else:
        source = package_name
    cmd = ["uv", "tool", "install", source]

    if force:
        cmd.insert(3, "--force")
        if from_github:
            cmd.insert(4, "--reinstall")

    if dry_run:
        return True, f"Would run: {' '.join(cmd)}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return True, "Installation successful"

        error_msg = result.stderr.strip()
        if not error_msg:
            error_msg = "Installation failed with no error message"

        return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "Installation timed out after 60 seconds"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def uninstall_tool(package_name: str = "ai-agent-rules") -> tuple[bool, str]:
    """Uninstall package from uv tools.

    Args:
        package_name: Name of package to uninstall

    Returns:
        Tuple of (success, message)
    """
    if not _validate_package_name(package_name):
        return False, f"Invalid package name: {package_name}"

    if not is_command_available("uv"):
        return False, UV_NOT_FOUND_ERROR

    cmd = ["uv", "tool", "uninstall", package_name]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, "Uninstallation successful"

        error_msg = result.stderr.strip()
        if not error_msg:
            error_msg = "Uninstallation failed with no error message"

        return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "Uninstallation timed out after 30 seconds"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def get_tool_version(tool_name: str) -> str | None:
    """Get installed version of a uv tool by parsing `uv tool list`.

    Args:
        tool_name: Name of the tool package (e.g., "claude-code-statusline")

    Returns:
        Version string (e.g., "0.7.1") or None if not installed
    """
    if not _validate_package_name(tool_name):
        return None

    if not is_command_available("uv"):
        return None

    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            if line.startswith(tool_name):
                match = re.search(r"v?(\d+\.\d+\.\d+)", line)
                if match:
                    return match.group(1)

        return None

    except (subprocess.TimeoutExpired, Exception):
        return None


def ensure_statusline_installed(
    dry_run: bool = False, from_github: bool = False
) -> tuple[str, str | None]:
    """Install or upgrade claude-code-statusline if needed. Fails open.

    Args:
        dry_run: If True, show what would be done without executing
        from_github: Install from GitHub instead of PyPI

    Returns:
        Tuple of (status, message) where status is:
        "already_installed", "installed", "upgraded", "upgrade_available", "failed", or "skipped"
        Message is only provided in dry_run mode or when upgraded
    """
    if is_command_available("claude-statusline"):
        try:
            from ai_rules.bootstrap.updater import (
                check_tool_updates,
                perform_tool_upgrade,
            )
            from ai_rules.tools.statusline import StatuslineTool

            statusline_tool = StatuslineTool.INSTALL_SPEC
            if statusline_tool:
                update_info = check_tool_updates(statusline_tool, timeout=10)
                if update_info and update_info.has_update:
                    if dry_run:
                        return (
                            "upgrade_available",
                            f"Would upgrade statusline {update_info.current_version} → {update_info.latest_version}",
                        )
                    success, msg, _ = perform_tool_upgrade(statusline_tool)
                    if success:
                        return (
                            "upgraded",
                            f"{update_info.current_version} → {update_info.latest_version}",
                        )
        except Exception:
            pass
        return "already_installed", None

    try:
        success, message = install_tool(
            "claude-code-statusline",
            from_github=from_github,
            github_url=make_github_install_url(STATUSLINE_GITHUB_REPO)
            if from_github
            else None,
            force=False,
            dry_run=dry_run,
        )
        if success:
            return "installed", message if dry_run else None
        else:
            return "failed", None
    except Exception:
        return "failed", None
