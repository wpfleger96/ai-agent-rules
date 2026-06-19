import json
import os
import tempfile
import time
import urllib.error
import urllib.request

from pathlib import Path
from typing import Any

import pytest

from click.testing import CliRunner

_SCHEMA_CACHE_DIR = Path(__file__).parent / "fixtures" / "schemas" / "cache"


def _atomic_write(path: Path, data: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, data.encode())
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd)
        os.unlink(tmp)
        raise


def get_schema(
    agent: str,
    url: str,
    ttl_days: int = 1,
    _cache_dir: Path | None = None,
) -> dict[str, Any] | None:
    cache_dir = _cache_dir or _SCHEMA_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{agent}.schema.json"

    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < ttl_days * 86400:
            try:
                result: dict[str, Any] = json.loads(cache_file.read_text())
                return result
            except json.JSONDecodeError:
                pass

    try:
        resp = urllib.request.urlopen(url, timeout=10)  # noqa: S310
        data = resp.read().decode()
        schema: dict[str, Any] = json.loads(data)
        _atomic_write(cache_file, data)
        return schema
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        if cache_file.exists():
            try:
                stale: dict[str, Any] = json.loads(cache_file.read_text())
                return stale
            except json.JSONDecodeError:
                pass
        return None


@pytest.fixture(scope="session")
def schema_fetcher():
    """Provide the get_schema function for schema validation tests."""
    return get_schema


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear Config._load_cached() cache before each test to prevent cache pollution."""
    from ai_rules.config import Config

    if hasattr(Config._load_cached, "cache_clear"):
        Config._load_cached.cache_clear()
    yield
    if hasattr(Config._load_cached, "cache_clear"):
        Config._load_cached.cache_clear()


@pytest.fixture(autouse=True)
def mock_platform_for_tests(monkeypatch):
    from ai_rules.platform import Platform, detect_platform

    detect_platform.cache_clear()
    monkeypatch.setattr(
        "ai_rules.platform.detect_platform",
        lambda: Platform.LINUX,
    )
    yield
    detect_platform.cache_clear()


@pytest.fixture(autouse=True)
def _patch_home_from_env(monkeypatch):
    """Make Path.home() follow the HOME env var on all platforms.

    On Windows, Path.home() reads USERPROFILE, not HOME. This fixture
    ensures Path.home() always returns the HOME env var value, so tests
    that only set HOME still get correct isolation on all platforms.
    The HOME value is read lazily at call time so test-level monkeypatches
    to HOME are visible to Path.home() invocations inside the test.
    """
    original_home = Path.home

    def _home() -> Path:
        env_home = os.environ.get("HOME")
        if env_home:
            return Path(env_home)
        return original_home()

    monkeypatch.setattr(Path, "home", staticmethod(_home))


def pytest_configure(config):
    """Register custom test markers to make testing and iterating easier on the developer."""
    config.addinivalue_line(
        "markers", "unit: Unit tests that do not modify real files on the system"
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests that modify real files on the system (e.g., symlinks)",
    )
    config.addinivalue_line("markers", "cli: Tests for the CLI sub-module")
    config.addinivalue_line("markers", "config: Tests for the config sub-module")
    config.addinivalue_line("markers", "agents: Tests for the agents sub-module")
    config.addinivalue_line("markers", "bootstrap: Tests for the bootstrap sub-module")
    config.addinivalue_line(
        "markers",
        "schema: Tests that validate bundled configs against provider or fixture schemas",
    )
    config.addinivalue_line(
        "markers",
        "network: Tests that fetch remote schemas during execution",
    )


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Create a mock home directory for testing."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.setenv("APPDATA", str(home_dir / "AppData" / "Roaming"))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))
    return home_dir


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing CLI commands."""
    return CliRunner()


def write_config_tree(root: Path, files: dict[str, str]) -> Path:
    """Materialize a config-dir tree from {relative_path: content}."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


@pytest.fixture(scope="session")
def config_tree_writer():
    """Expose write_config_tree to sub-conftest fixtures (e.g. tests/e2e)."""
    return write_config_tree


@pytest.fixture
def test_repo(tmp_path):
    """Create a test repository structure with config files.

    Note: As of v0.5.0, config structure changed from repo/config/* to package/config/*.
    This fixture mimics the new package structure for testing.
    """
    return write_config_tree(
        tmp_path / "test-config",
        {
            "AGENTS.md": "# Shared Agent Rules\nTest content",
            "claude/settings.json": '{"test": "settings"}',
            "claude/CLAUDE.md": "@~/AGENTS.md\n",
            "claude/agents/test-agent.md": "# Test Agent\nAgent content",
            "claude/commands/test-command.md": "# Test Command\nCommand content",
            "claude/mcps.json": "{}",
            "codex/config.toml": 'model = "gpt-5.2-codex"\napproval_policy = "on-request"\n',
            "codex/AGENTS.md": "@~/AGENTS.md\n",
            "gemini/settings.json": '{"name": "gemini-3.1-pro-preview"}',
            "gemini/GEMINI.md": "@~/AGENTS.md\n",
            "amp/settings.json": '{"amp.anthropic.thinking.enabled": true, "amp.showCosts": true}',
            "amp/AGENTS.md": "@~/AGENTS.md\n",
            "goose/config.yaml": "test: config",
            "goose/.goosehints": "@~/AGENTS.md\n",
        },
    )
