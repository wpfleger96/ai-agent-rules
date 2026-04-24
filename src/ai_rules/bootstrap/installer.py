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
BASIC_MEMORY_GITHUB_REPO = "basicmachines-co/basic-memory"


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
        if not github_url:
            raise ValueError("github_url is required when from_github=True")
        source = github_url
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


def get_effective_install_source(tool_id: str, cli_github_flag: bool = False) -> bool:
    """Resolve whether a tool should use GitHub install.

    Priority (highest first):
    1. cli_github_flag — explicit session override (--github flag)
    2. Merged config (user config > active profile) managed_tools.install_sources
    3. Default: False (PyPI)

    Args:
        tool_id: Tool identifier (e.g., "statusline", "ai-agent-rules")
        cli_github_flag: True if --github was passed on the CLI

    Returns:
        True for GitHub, False for PyPI
    """
    if cli_github_flag:
        return True
    try:
        from ai_rules.config import Config

        config = Config.load()
        source = config.get_tool_install_source(tool_id)
        if source == "github":
            return True
        if source == "pypi":
            return False
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(
            f"Config load failed in install source resolver: {e}"
        )
    return False


def ensure_statusline_installed(
    dry_run: bool = False,
    from_github: bool = False,
    allow_source_switch: bool = False,
) -> tuple[str, str | None]:
    """Install or upgrade claude-code-statusline if needed. Fails open.

    Args:
        dry_run: If True, show what would be done without executing
        from_github: Install from GitHub instead of PyPI
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

    if is_command_available("claude-statusline"):
        if allow_source_switch and statusline_spec:
            current_source = get_tool_source(statusline_spec.package_name)
            desired_source = ToolSource.GITHUB if from_github else ToolSource.PYPI
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
            force=False,
            dry_run=dry_run,
        )
        if success:
            return "installed", message if dry_run else None
        else:
            return "failed", None
    except Exception:
        return "failed", None


def _run_basic_memory_setup(verbose: bool = False) -> None:
    """Run the idempotent basic-memory setup script (git init, GitHub remote).

    Reads basic_memory config from ~/.ai-rules-config.yaml and passes
    as env vars to the setup script.
    """
    setup_script = (
        Path(__file__).parent.parent
        / "config"
        / "claude"
        / "hooks"
        / "basic-memory-setup.sh"
    )
    if not setup_script.exists():
        return

    env = dict(os.environ)
    try:
        import yaml

        user_config_path = Path.home() / ".ai-rules-config.yaml"
        if user_config_path.exists():
            with open(user_config_path) as f:
                user_config = yaml.safe_load(f) or {}
            bm_config = user_config.get("basic_memory", {})
            if bm_config.get("repo"):
                env["BASIC_MEMORY_WIKI_REPO"] = bm_config["repo"]
            if bm_config.get("path"):
                env["BASIC_MEMORY_HOME"] = str(Path(bm_config["path"]).expanduser())
    except Exception:
        pass

    try:
        subprocess.run(
            ["bash", str(setup_script)],
            timeout=60,
            capture_output=not verbose,
            env=env,
        )
    except (subprocess.TimeoutExpired, Exception):
        pass


def _is_basic_memory_configured(config: object) -> bool:
    """Check if basic-memory is configured in the merged MCP config.

    Checks both profile mcp_overrides and the base mcps.json file.
    """
    if hasattr(config, "mcp_overrides") and "basic-memory" in config.mcp_overrides:
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
                if "basic-memory" in data:
                    return True
    except Exception:
        pass

    return False


def ensure_basic_memory_installed(
    dry_run: bool = False,
    from_github: bool = False,
    config: object | None = None,
) -> tuple[str, str | None]:
    """Install or upgrade basic-memory if needed. Runs setup script after. Fails open.

    Args:
        dry_run: If True, show what would be done without executing
        from_github: Install from GitHub instead of PyPI
        config: Config object; if provided and basic-memory is not configured, skip

    Returns:
        Tuple of (status, message) where status is:
        "already_installed", "installed", "upgraded", "upgrade_available", "failed", or "skipped"
    """
    if config is not None and not _is_basic_memory_configured(config):
        return "skipped", None
    if is_command_available("basic-memory"):
        try:
            from ai_rules.bootstrap.updater import (
                check_tool_updates,
                get_tool_by_id,
                perform_tool_upgrade,
            )

            bm_tool = get_tool_by_id("basic-memory")
            if bm_tool:
                update_info = check_tool_updates(bm_tool, timeout=10)
                if update_info and update_info.has_update:
                    if dry_run:
                        return (
                            "upgrade_available",
                            f"Would upgrade basic-memory {update_info.current_version} → {update_info.latest_version}",
                        )
                    success, msg, _ = perform_tool_upgrade(bm_tool)
                    if success:
                        if not dry_run:
                            _run_basic_memory_setup()
                        return (
                            "upgraded",
                            f"{update_info.current_version} → {update_info.latest_version}",
                        )
        except Exception:
            pass
        if not dry_run:
            _run_basic_memory_setup()
        return "already_installed", None

    try:
        success, message = install_tool(
            "basic-memory",
            from_github=from_github,
            github_url=make_github_install_url(BASIC_MEMORY_GITHUB_REPO)
            if from_github
            else None,
            force=False,
            dry_run=dry_run,
        )
        if success:
            if not dry_run:
                _run_basic_memory_setup(verbose=True)
            return "installed", message if dry_run else None
        else:
            return "failed", None
    except Exception:
        return "failed", None
