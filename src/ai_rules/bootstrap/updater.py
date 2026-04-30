"""Update checking and application utilities."""

import json
import logging
import os
import re
import subprocess
import urllib.request

from collections.abc import Callable
from dataclasses import dataclass

from .installer import (
    UV_NOT_FOUND_ERROR,
    ToolSource,
    _validate_package_name,
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


@dataclass
class ToolSpec:
    """Specification for an updatable tool."""

    tool_id: str
    package_name: str
    display_name: str
    get_version: Callable[[], str | None]
    is_installed: Callable[[], bool]
    github_repo: str | None = None

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
        url = f"https://raw.githubusercontent.com/{repo}/main/CHANGELOG.md"

        req = urllib.request.Request(url)
        req.add_header("User-Agent", f"ai-rules/{current_version}")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            changelog_content = response.read().decode()

        entries: list[tuple[str, str]] = []
        current_entry_version: str | None = None
        current_entry_lines: list[str] = []

        for line in changelog_content.split("\n"):
            version_match = re.match(r"^##\s+v?(\d+\.\d+\.\d+)", line)
            if version_match:
                if current_entry_version and current_entry_lines:
                    version_obj = current_entry_version
                    if is_newer(version_obj, current_version) and (
                        version_obj == latest_version
                        or not is_newer(version_obj, latest_version)
                    ):
                        entries.append(
                            (current_entry_version, "\n".join(current_entry_lines))
                        )

                current_entry_version = version_match.group(1)
                current_entry_lines = []
            elif current_entry_version and line.strip():
                current_entry_lines.append(line)

        if current_entry_version and current_entry_lines:
            if is_newer(current_entry_version, current_version) and (
                current_entry_version == latest_version
                or not is_newer(current_entry_version, latest_version)
            ):
                entries.append((current_entry_version, "\n".join(current_entry_lines)))

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
        )
    except Exception as e:
        logger.debug(f"Index check failed: {e}")
        return UpdateInfo(
            has_update=False,
            current_version=current_version,
            latest_version=current_version,
            source="index",
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
        )


def perform_tool_upgrade(tool: ToolSpec) -> tuple[bool, str, bool]:
    """Upgrade a tool via uv, handling PyPI and GitHub sources.

    Args:
        tool: Tool specification to upgrade

    Returns:
        Tuple of (success, message, was_upgraded)
        - success: Whether command succeeded
        - message: Human-readable status message
        - was_upgraded: True if package was actually upgraded (not already up-to-date)
    """
    if not is_command_available("uv"):
        return False, UV_NOT_FOUND_ERROR, False

    source = get_tool_source(tool.package_name)

    if source == ToolSource.LOCAL:
        return True, "Local install — upgrade manually", False

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
        cmd = ["uv", "tool", "upgrade", tool.package_name, "--no-cache"]

        # Ensure upgrade uses same index as version check
        # Use --default-index (modern) not --index-url (deprecated)
        if index_url := get_configured_index_url():
            cmd.extend(["--default-index", index_url])

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
    """Get all updatable tool specs, deriving from registered Tool classes."""
    from ai_rules.tools.statusline import StatuslineTool

    tools: list[ToolSpec] = [_SELF_SPEC]
    if StatuslineTool.INSTALL_SPEC is not None:
        tools.append(StatuslineTool.INSTALL_SPEC)
    return tools


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

    source = get_tool_source(tool.package_name)

    if source == ToolSource.LOCAL:
        return None  # Local installs don't have a remote version to check

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
