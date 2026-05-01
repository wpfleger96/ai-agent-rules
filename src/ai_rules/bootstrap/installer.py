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
    LOCAL = auto()


def make_github_install_url(repo: str) -> str:
    """Construct GitHub install URL for uv tool install.

    Args:
        repo: GitHub repository in format "owner/repo"

    Returns:
        Full git+ssh URL for uv tool install
    """
    return f"git+ssh://git@github.com/{repo}.git"


UV_NOT_FOUND_ERROR = "uv not found in PATH. Install from https://docs.astral.sh/uv/"
RECALL_GITHUB_REPO = "wpfleger96/recall"


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
        ToolSource.LOCAL if installed from a local path
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
            if "path" in first_req or "directory" in first_req:
                return ToolSource.LOCAL

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
    local_path: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Install package as a uv tool.

    Args:
        package_name: Name of package to install (ignored if from_github or local_path)
        from_github: Install from GitHub instead of PyPI
        github_url: GitHub URL to install from (only used if from_github=True)
        local_path: Local filesystem path to install from (takes priority over from_github)
        force: Force reinstall if already installed
        dry_run: Show what would be done without executing

    Returns:
        Tuple of (success, message)
    """
    if not local_path and not from_github and not _validate_package_name(package_name):
        return False, f"Invalid package name: {package_name}"

    if not is_command_available("uv"):
        return False, UV_NOT_FOUND_ERROR

    if local_path:
        source = str(Path(local_path).expanduser().resolve())
    elif from_github:
        if not github_url:
            raise ValueError("github_url is required when from_github=True")
        source = github_url
    else:
        source = package_name
    cmd = ["uv", "tool", "install", source]

    if force:
        cmd.insert(3, "--force")
        if from_github or local_path:
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


def get_effective_install_source(
    tool_id: str, cli_github_flag: bool = False
) -> tuple[ToolSource, str | None]:
    """Resolve the install source for a tool.

    Priority (highest first):
    1. cli_github_flag — explicit session override (--github flag)
    2. Merged config (user config > active profile) managed_tools.install_sources
    3. Default: (ToolSource.PYPI, None)

    Args:
        tool_id: Tool identifier (e.g., "statusline", "ai-agent-rules")
        cli_github_flag: True if --github was passed on the CLI

    Returns:
        Tuple of (ToolSource, local_path). local_path is set only for LOCAL source.
    """
    if cli_github_flag:
        return ToolSource.GITHUB, None
    try:
        from ai_rules.config import Config

        config = Config.load()
        source = config.get_tool_install_source(tool_id)
        if source == "github":
            return ToolSource.GITHUB, None
        if source == "pypi":
            return ToolSource.PYPI, None
        if source and source.startswith("local:"):
            local_path = source[len("local:") :]
            return ToolSource.LOCAL, local_path
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(
            f"Config load failed in install source resolver: {e}"
        )
    return ToolSource.PYPI, None


def ensure_statusline_installed(
    dry_run: bool = False,
    from_github: bool = False,
    local_path: str | None = None,
    allow_source_switch: bool = False,
) -> tuple[str, str | None]:
    """Install or upgrade claude-code-statusline if needed. Fails open.

    Args:
        dry_run: If True, show what would be done without executing
        from_github: Install from GitHub instead of PyPI
        local_path: Local filesystem path to install from (takes priority)
        allow_source_switch: If True and the installed source differs from desired,
            uninstall and reinstall from the correct source (only setup should pass True)

    Returns:
        Tuple of (status, message) where status is one of:
        "already_installed", "installed", "upgraded", "upgrade_available",
        "source_switched", "source_switch_needed", "failed"
        Message is only provided in dry_run mode or when upgraded/switched
    """
    try:
        from ai_rules.tools.statusline import StatuslineTool

        statusline_spec = StatuslineTool.INSTALL_SPEC
    except Exception:
        statusline_spec = None

    if local_path:
        desired_source = ToolSource.LOCAL
    elif from_github:
        desired_source = ToolSource.GITHUB
    else:
        desired_source = ToolSource.PYPI

    if is_command_available("claude-statusline"):
        if allow_source_switch and statusline_spec:
            current_source = get_tool_source(statusline_spec.package_name)
            if current_source is not None and current_source != desired_source:
                if dry_run:
                    return (
                        "source_switch_needed",
                        f"Would switch statusline from {current_source.name} to {desired_source.name}",
                    )
                uninstall_success, _ = uninstall_tool(statusline_spec.package_name)
                if uninstall_success:
                    github_url = (
                        statusline_spec.github_install_url if from_github else None
                    )
                    success, _ = install_tool(
                        statusline_spec.package_name,
                        from_github=from_github,
                        github_url=github_url,
                        local_path=local_path,
                        force=True,
                    )
                    if success:
                        return (
                            "source_switched",
                            f"{current_source.name} → {desired_source.name}",
                        )
                return "failed", None

        try:
            from ai_rules.bootstrap.updater import (
                check_tool_updates,
                perform_tool_upgrade,
            )

            if statusline_spec:
                update_info = check_tool_updates(statusline_spec, timeout=10)
                if update_info and update_info.has_update:
                    if dry_run:
                        return (
                            "upgrade_available",
                            f"Would upgrade statusline {update_info.current_version} → {update_info.latest_version}",
                        )
                    success, msg, _ = perform_tool_upgrade(statusline_spec)
                    if success:
                        return (
                            "upgraded",
                            f"{update_info.current_version} → {update_info.latest_version}",
                        )
        except Exception:
            pass
        return "already_installed", None

    try:
        github_url = (
            statusline_spec.github_install_url
            if (from_github and statusline_spec)
            else None
        )
        success, message = install_tool(
            statusline_spec.package_name
            if statusline_spec
            else "claude-code-statusline",
            from_github=from_github,
            github_url=github_url,
            local_path=local_path,
            force=False,
            dry_run=dry_run,
        )
        if success:
            return "installed", message if dry_run else None
        else:
            return "failed", None
    except Exception:
        return "failed", None


def _is_recall_configured(config: object) -> bool:
    """Check if recall is configured in the merged MCP config."""
    if hasattr(config, "mcp_overrides") and "recall" in config.mcp_overrides:
        return True

    try:
        import importlib.resources

        config_pkg = importlib.resources.files("ai_rules") / "config"
        for mcps_path in [
            config_pkg / "mcps.json",
            config_pkg / "claude" / "mcps.json",
        ]:
            traversable = mcps_path
            if hasattr(traversable, "is_file") and traversable.is_file():
                import json

                data = json.loads(traversable.read_text())
                if "recall" in data:
                    return True
    except Exception:
        pass

    return False


def ensure_recall_installed(
    dry_run: bool = False,
    config: object | None = None,
) -> tuple[str, str | None]:
    """Install or upgrade recall if needed. Fails open.

    Args:
        dry_run: If True, show what would be done without executing
        config: Config object; if provided and recall is not configured, skip

    Returns:
        Tuple of (status, message) where status is:
        "already_installed", "installed", "upgraded", "upgrade_available",
        "source_switched", "source_switch_needed", "failed", or "skipped"
    """
    if config is not None and not _is_recall_configured(config):
        return "skipped", None

    source, local_path = get_effective_install_source("recall")
    from_github = source == ToolSource.GITHUB

    if is_command_available("recall"):
        if source != ToolSource.LOCAL:
            try:
                from ai_rules.bootstrap.updater import (
                    check_tool_updates,
                    get_tool_by_id,
                    perform_tool_upgrade,
                )

                recall_tool = get_tool_by_id("recall")
                if recall_tool:
                    current_source = get_tool_source(recall_tool.package_name)
                    if current_source is not None and current_source != source:
                        if dry_run:
                            return (
                                "source_switch_needed",
                                f"Would switch recall from {current_source.name} to {source.name}",
                            )
                        uninstall_success, _ = uninstall_tool(recall_tool.package_name)
                        if uninstall_success:
                            github_url = (
                                recall_tool.github_install_url if from_github else None
                            )
                            success, _ = install_tool(
                                recall_tool.package_name,
                                from_github=from_github,
                                github_url=github_url,
                                local_path=local_path,
                                force=True,
                            )
                            if success:
                                return (
                                    "source_switched",
                                    f"{current_source.name} → {source.name}",
                                )
                        return "failed", None

                    update_info = check_tool_updates(recall_tool, timeout=10)
                    if update_info and update_info.has_update:
                        if dry_run:
                            return (
                                "upgrade_available",
                                f"Would upgrade recall {update_info.current_version} → {update_info.latest_version}",
                            )
                        success, msg, _ = perform_tool_upgrade(recall_tool)
                        if success:
                            return (
                                "upgraded",
                                f"{update_info.current_version} → {update_info.latest_version}",
                            )
            except Exception:
                pass
        else:
            # LOCAL source: always reinstall to pick up latest local changes
            success, message = install_tool(
                "recall-mcp-server",
                local_path=local_path,
                force=True,
                dry_run=dry_run,
            )
            if dry_run:
                return "upgrade_available", message
            if success:
                return "upgraded", "reinstalled from local path"
            return "failed", None

        return "already_installed", None

    try:
        github_url = (
            make_github_install_url(RECALL_GITHUB_REPO) if from_github else None
        )
        success, message = install_tool(
            "recall-mcp-server",
            from_github=from_github,
            github_url=github_url,
            local_path=local_path,
            force=False,
            dry_run=dry_run,
        )
        if success:
            return "installed", message if dry_run else None
        else:
            return "failed", None
    except Exception:
        return "failed", None
