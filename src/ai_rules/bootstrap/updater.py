"""Update checking and application utilities."""

import json
import logging
import os
import re
import subprocess
import tomllib
import urllib.request

from collections.abc import Callable
from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from .installer import (
    UV_NOT_FOUND_ERROR,
    ToolSource,
    _validate_package_name,
    get_effective_install_source,
    get_tool_source,
    get_tool_version,
    is_command_available,
    make_github_install_url,
)
from .version import is_newer

_SELF_GITHUB_REPO = "wpfleger96/ai-agent-rules"

logger = logging.getLogger(__name__)


def get_configured_index_url() -> str | None:
    """Get package index URL from environment.

    Checks in order of preference:
    1. UV_DEFAULT_INDEX (modern uv, recommended)
    2. UV_INDEX_URL (deprecated uv, still supported)
    3. PIP_INDEX_URL (pip compatibility)

    Returns:
        Index URL if configured, None otherwise
    """
    return (
        os.environ.get("UV_DEFAULT_INDEX")
        or os.environ.get("UV_INDEX_URL")
        or os.environ.get("PIP_INDEX_URL")
    )


@dataclass
class UpdateInfo:
    """Information about available updates."""

    has_update: bool
    current_version: str
    latest_version: str
    source: str
    changelog_entries: list[tuple[str, str]] | None = None
    check_failed: bool = False


@dataclass
class ToolSpec:
    """Specification for an updatable tool."""

    tool_id: str
    package_name: str
    display_name: str
    get_version: Callable[[], str | None]
    is_installed: Callable[[], bool]
    github_repo: str | None = None
    is_enabled: Callable[[], bool] | None = None

    @property
    def github_install_url(self) -> str | None:
        """Get the GitHub install URL for uv tool install."""
        if self.github_repo:
            return make_github_install_url(self.github_repo)
        return None


def fetch_changelog_entries(
    repo: str,
    current_version: str,
    latest_version: str,
    timeout: int = 10,
) -> list[tuple[str, str]]:
    """Fetch changelog entries for versions between current and latest.

    Uses the GitHub Releases API so version headings don't need to be parsed.

    Args:
        repo: GitHub repository in format "owner/repo"
        current_version: Currently installed version
        latest_version: Latest available version
        timeout: Request timeout in seconds (default: 10)

    Returns:
        List of (version, notes) tuples for each version in the range.
        Returns empty list on any error (private repo, network failure, etc).
    """
    try:
        url = f"https://api.github.com/repos/{repo}/releases"

        req = urllib.request.Request(url)
        req.add_header("User-Agent", f"ai-rules/{current_version}")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            releases = json.loads(response.read().decode())

        entries: list[tuple[str, str]] = []
        for release in releases:
            version = release["tag_name"].lstrip("v")
            if not (
                is_newer(version, current_version)
                and (version == latest_version or not is_newer(version, latest_version))
            ):
                continue

            # Strip the CI-appended Skills Downloads trailer if present
            body: str = release.get("body") or ""
            notes = body.split("\n---\n", 1)[0].strip()

            entries.append((version, notes))

        return entries

    except Exception as e:
        logger.debug(f"Changelog fetch failed: {e}")
        return []


def check_index_updates(
    package_name: str,
    current_version: str,
    timeout: int = 30,
    github_repo: str | None = None,
) -> UpdateInfo:
    """Check configured package index for newer version.

    Uses `uvx pip index versions` to query the user's configured index,
    which respects pip.conf and environment variables.

    Args:
        package_name: Package name to check
        current_version: Currently installed version
        timeout: Request timeout in seconds (default: 30)
        github_repo: Optional GitHub repo for fetching changelog (e.g., "owner/repo")

    Returns:
        UpdateInfo with update status
    """
    if not _validate_package_name(package_name):
        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="index",
        )

    if not is_command_available("uvx"):
        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="index",
        )

    try:
        cmd = ["uvx", "--refresh", "pip", "index", "versions", package_name]

        # Pass index URL explicitly since pip doesn't understand UV_* env vars
        if index_url := get_configured_index_url():
            cmd.extend(["--index-url", index_url])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            logger.debug(f"uvx pip index versions failed: {result.stderr}")
            return UpdateInfo(
                has_update=False,
                current_version=current_version,
                latest_version=current_version,
                source="index",
                check_failed=True,
            )

        output = result.stdout.strip()
        match = re.search(r"^\S+\s+\(([^)]+)\)", output)
        if match:
            latest_version = match.group(1)
            has_update = is_newer(latest_version, current_version)

            changelog_entries = None
            if has_update and github_repo:
                changelog_entries = fetch_changelog_entries(
                    github_repo, current_version, latest_version, timeout
                )

            return UpdateInfo(
                has_update=has_update,
                current_version=current_version,
                latest_version=latest_version,
                source="index",
                changelog_entries=changelog_entries,
            )

        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="index",
        )

    except subprocess.TimeoutExpired:
        logger.debug("uvx pip index versions timed out")
        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="index",
            check_failed=True,
        )
    except Exception as e:
        logger.debug(f"Index check failed: {e}")
        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="index",
            check_failed=True,
        )


def check_github_updates(
    repo: str, current_version: str, timeout: int = 10
) -> UpdateInfo:
    """Check GitHub tags for newer version.

    Args:
        repo: GitHub repository in format "owner/repo"
        current_version: Currently installed version
        timeout: Request timeout in seconds (default: 10)

    Returns:
        UpdateInfo with update status
    """
    try:
        url = f"https://api.github.com/repos/{repo}/tags"

        req = urllib.request.Request(url)
        req.add_header("User-Agent", f"ai-rules/{current_version}")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode())

        if not data or len(data) == 0:
            return UpdateInfo(
                has_update=False,
                current_version=current_version,
                latest_version=current_version,
                source="github",
            )

        latest_tag = data[0]["name"]
        latest_version = latest_tag.lstrip("v")

        has_update = is_newer(latest_version, current_version)

        changelog_entries = None
        if has_update:
            changelog_entries = fetch_changelog_entries(
                repo, current_version, latest_version, timeout
            )

        return UpdateInfo(
            has_update=has_update,
            current_version=current_version,
            latest_version=latest_version,
            source="github",
            changelog_entries=changelog_entries,
        )

    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        logger.debug(f"GitHub check failed: {e}")
        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="github",
            check_failed=True,
        )


def _get_tool_venv_python(package_name: str) -> str | None:
    """Read the Python version from a uv tool's virtual environment."""
    from ai_rules.platform import get_uv_tools_dir

    pyvenv_cfg = get_uv_tools_dir() / package_name / "pyvenv.cfg"
    try:
        for line in pyvenv_cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("version_info"):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def _fetch_requires_python(
    package_name: str,
    version: str,
    github_repo: str | None,
    source: ToolSource,
    timeout: int = 10,
) -> str | None:
    """Fetch the requires-python specifier for a specific package version."""
    try:
        if source == ToolSource.GITHUB and github_repo:
            url = f"https://raw.githubusercontent.com/{github_repo}/v{version}/pyproject.toml"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "ai-rules")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = tomllib.loads(response.read().decode())
            result: str | None = data.get("project", {}).get("requires-python")
            return result
        else:
            url = f"https://pypi.org/pypi/{package_name}/{version}/json"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "ai-rules")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode())
            result = data.get("info", {}).get("requires_python")
            return result
    except Exception as e:
        logger.debug(
            f"Failed to fetch requires-python for {package_name}=={version}: {e}"
        )
        return None


def _compute_required_python(
    tool: ToolSpec,
    target_version: str,
    source: ToolSource,
) -> str | None:
    """Determine if the tool venv needs a Python upgrade for the target version.

    Returns the minimum required Python major.minor (e.g. "3.14") if the
    current venv Python is too old, None otherwise.
    """
    venv_python = _get_tool_venv_python(tool.package_name)
    if not venv_python:
        return None

    requires_python = _fetch_requires_python(
        tool.package_name, target_version, tool.github_repo, source
    )
    if not requires_python:
        return None

    try:
        spec = SpecifierSet(requires_python)
    except InvalidSpecifier:
        return None

    if venv_python in spec:
        return None

    for s in spec:
        if s.operator in (">=", "==", "~="):
            parts = s.version.split(".")
            return f"{parts[0]}.{parts[1]}"
    return None


def _resolve_effective_source(tool: ToolSpec) -> ToolSource:
    """Resolve install source by consulting config, falling back to receipt."""
    receipt_source = get_tool_source(tool.package_name)
    config_source, _ = get_effective_install_source(tool.tool_id)
    if config_source in (ToolSource.GITHUB, ToolSource.LOCAL):
        return config_source
    return receipt_source or ToolSource.PYPI


def perform_tool_upgrade(
    tool: ToolSpec,
    target_version: str | None = None,
) -> tuple[bool, str, bool]:
    """Upgrade a tool via uv, handling PyPI and GitHub sources.

    Args:
        tool: Tool specification to upgrade
        target_version: Expected target version (used to detect Python mismatches)

    Returns:
        Tuple of (success, message, was_upgraded)
        - success: Whether command succeeded
        - message: Human-readable status message
        - was_upgraded: True if package was actually upgraded (not already up-to-date)
    """
    if not is_command_available("uv"):
        return False, UV_NOT_FOUND_ERROR, False

    source = _resolve_effective_source(tool)

    if source == ToolSource.LOCAL:
        return True, "Local install — upgrade manually", False

    python_flag: str | None = None
    if target_version:
        python_flag = _compute_required_python(tool, target_version, source)

    if source == ToolSource.GITHUB and tool.github_install_url:
        cmd = [
            "uv",
            "tool",
            "install",
            "--force",
            "--reinstall",
            tool.github_install_url,
        ]
    else:
        if not _validate_package_name(tool.package_name):
            return False, f"Invalid package name: {tool.package_name}", False
        cmd = ["uv", "tool", "install", "--force", "--reinstall", tool.package_name]

        if index_url := get_configured_index_url():
            cmd.extend(["--default-index", index_url])

    if python_flag:
        cmd.extend(["--python", python_flag])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            output = result.stdout + result.stderr

            upgrade_patterns = [
                r"Upgraded .+ from .+ to .+",
                r"Installed .+ \d+\.\d+",
                r"Successfully installed",
            ]

            already_up_to_date_patterns = [
                r"Nothing to upgrade",
                r"already.*installed",
                r"already.*up.*to.*date",
            ]

            was_upgraded = False
            if any(
                re.search(pattern, output, re.IGNORECASE)
                for pattern in upgrade_patterns
            ):
                was_upgraded = True
            elif any(
                re.search(pattern, output, re.IGNORECASE)
                for pattern in already_up_to_date_patterns
            ):
                was_upgraded = False
            else:
                was_upgraded = True

            return True, "Upgrade successful", was_upgraded

        error_msg = result.stderr.strip()
        if not error_msg:
            error_msg = "Upgrade failed with no error message"

        return False, error_msg, False

    except subprocess.TimeoutExpired:
        return False, "Upgrade timed out after 60 seconds", False
    except Exception as e:
        return False, f"Unexpected error: {e}", False


_SELF_SPEC = ToolSpec(
    tool_id="ai-agent-rules",
    package_name="ai-agent-rules",
    display_name="ai-agent-rules",
    get_version=lambda: get_tool_version("ai-agent-rules"),
    is_installed=lambda: True,
    github_repo=_SELF_GITHUB_REPO,
)


def get_updatable_tools() -> list[ToolSpec]:
    """Get all updatable tool specs: self plus every registered active tool."""
    from ai_rules.bootstrap.registry import ACTIVE_TOOLS

    return [_SELF_SPEC, *(tool.get_install_spec() for tool in ACTIVE_TOOLS)]


def check_tool_updates(tool: ToolSpec, timeout: int = 30) -> UpdateInfo | None:
    """Check for updates for any tool - auto-detect PyPI vs GitHub source.

    Args:
        tool: Tool specification
        timeout: Request timeout in seconds (default: 30)

    Returns:
        UpdateInfo if tool is installed and update check succeeds, None otherwise
    """
    if not tool.is_installed():
        return None

    current = tool.get_version()
    if current is None:
        return None

    source = _resolve_effective_source(tool)

    if source == ToolSource.LOCAL:
        return None

    if source == ToolSource.GITHUB and tool.github_repo:
        return check_github_updates(tool.github_repo, current, timeout)
    else:
        return check_index_updates(
            tool.package_name, current, timeout, tool.github_repo
        )


_TOOL_ID_ALIASES: dict[str, str] = {
    "ai-rules": "ai-agent-rules",
}


def get_tool_by_id(tool_id: str) -> ToolSpec | None:
    """Look up tool spec by ID, with alias support.

    Args:
        tool_id: Tool identifier (e.g., "ai-agent-rules", "ai-rules", "statusline")

    Returns:
        ToolSpec if found, None otherwise
    """
    canonical = _TOOL_ID_ALIASES.get(tool_id, tool_id)
    return next((t for t in get_updatable_tools() if t.tool_id == canonical), None)
