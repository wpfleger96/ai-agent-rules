"""Regression guard: generic default deployment must contain no personal markers."""

from __future__ import annotations

import json

from importlib.resources import files as resource_files
from pathlib import Path

import pytest

from ai_rules.profiles import ProfileLoader

# The provenance header intentionally names the managing repo; its URL is
# public repo identity, not leaked personal config. Strip it before scanning.
PROVENANCE_URL = "https://github.com/wpfleger96/ai-agent-rules"

PERSONAL_MARKERS: list[str] = [
    "wpfleger",
    "will pfleger",
    "eastwood",
    "data-lake",
    "enpass",
    "gh-infra",
    "warp-cli",
    "development/personal",
    "gemini_cli.key",
    "escalates to will",
]

# Files (relative to config/) that legitimately contain the given marker.
MARKER_EXEMPTIONS: dict[str, set[str]] = {
    "gemini_cli.key": {
        "skills/crossfire/SKILL.md",
        "skills/code-reviewer/SKILL.md",
    },
}

# Files (relative to config/) exempt from the sweep entirely: author metadata
# and personal reference material that the CLI never deploys to users.
EXEMPT_FILES: set[str] = {
    "buzz/.plugin/plugin.json",
    "chat_agent_hints.md",
}


@pytest.fixture(scope="module")
def config_root() -> Path:
    return Path(str(resource_files("ai_rules") / "config"))


@pytest.mark.unit
class TestDefaultProfileSanitization:
    def test_config_tree_outside_profiles_has_no_personal_markers(
        self, config_root: Path
    ) -> None:
        """Walk config/ (excluding profiles/ and exempt files) and assert no personal markers appear."""
        profiles_dir = config_root / "profiles"

        violations: list[str] = []

        for path in sorted(config_root.rglob("*")):
            if not path.is_file():
                continue
            if path.is_relative_to(profiles_dir):
                continue
            if path.relative_to(config_root).as_posix() in EXEMPT_FILES:
                continue
            # Skip bytecode artifacts: test runs compile config/skills scripts,
            # and .pyc files embed absolute source paths from the local checkout.
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue

            rel_str = path.relative_to(config_root).as_posix()
            text = path.read_text(encoding="utf-8", errors="ignore")
            text_lower = text.replace(PROVENANCE_URL, "").lower()

            for marker in PERSONAL_MARKERS:
                exempted = MARKER_EXEMPTIONS.get(marker, set())
                if rel_str in exempted:
                    continue
                if marker.lower() in text_lower:
                    violations.append(f"{rel_str}: contains marker {marker!r}")

        assert not violations, (
            "Personal markers found in generic config tree:\n" + "\n".join(violations)
        )

    def test_default_profile_contributes_no_agents_md(self) -> None:
        """The default profile must not inject any agents_md content."""
        profile = ProfileLoader().load_profile("default")
        assert profile.agents_md == ""

    def test_default_profile_resolved_settings_have_no_personal_markers(
        self, config_root: Path
    ) -> None:
        """Neither the default profile's settings_overrides nor base claude/settings.json may contain personal markers."""
        profile = ProfileLoader().load_profile("default")

        settings_json = json.dumps(profile.settings_overrides).lower()
        for marker in PERSONAL_MARKERS:
            assert marker.lower() not in settings_json, (
                f"Personal marker {marker!r} found in default profile settings_overrides"
            )

        claude_settings = (
            (config_root / "claude" / "settings.json")
            .read_text(encoding="utf-8")
            .lower()
        )
        for marker in PERSONAL_MARKERS:
            assert marker.lower() not in claude_settings, (
                f"Personal marker {marker!r} found in config/claude/settings.json"
            )

    def test_base_agents_md_has_no_personal_markers(self, config_root: Path) -> None:
        """The base config/AGENTS.md must contain no personal markers."""
        agents_lower = (
            (config_root / "AGENTS.md")
            .read_text(encoding="utf-8")
            .replace(PROVENANCE_URL, "")
            .lower()
        )
        for marker in PERSONAL_MARKERS:
            assert marker.lower() not in agents_lower, (
                f"Personal marker {marker!r} found in config/AGENTS.md"
            )
