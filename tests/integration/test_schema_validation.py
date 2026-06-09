import json

from importlib.resources import files as resource_files
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import pytest

from ai_rules.config import load_config_file

# Top-level keys present in the Claude Code binary but missing from the
# SchemaStore schema. Remove entries as upstream catches up.
# Upstream issue: https://github.com/SchemaStore/schemastore/issues/5484
KNOWN_CLAUDE_SCHEMA_MISSING_KEYS: frozenset[str] = frozenset(
    {
        "autoUpdates",
    }
)

# Live URLs point at upstream main so the integration suite catches real
# provider schema drift during normal test runs.
SCHEMA_URLS = {
    "claude": "https://json.schemastore.org/claude-code-settings.json",
    "codex": "https://raw.githubusercontent.com/openai/codex/refs/heads/main/codex-rs/core/config.schema.json",
    "gemini": "https://raw.githubusercontent.com/google-gemini/gemini-cli/main/schemas/settings.schema.json",
}

GOOSE_SCHEMA_PATH = (
    Path(__file__).parent.parent / "fixtures" / "schemas" / "goose.schema.json"
)


def _config_root() -> Path:
    return Path(str(resource_files("ai_rules") / "config"))


@pytest.mark.integration
@pytest.mark.schema
@pytest.mark.network
class TestProviderSchemaValidation:
    @pytest.fixture(scope="class")
    def claude_schema(self, schema_fetcher):
        schema = schema_fetcher("claude", SCHEMA_URLS["claude"])
        if schema is None:
            pytest.skip("Claude schema unavailable (offline or cache miss)")
        return schema

    @pytest.fixture(scope="class")
    def codex_schema(self, schema_fetcher):
        schema = schema_fetcher("codex", SCHEMA_URLS["codex"])
        if schema is None:
            pytest.skip("Codex schema unavailable (offline or cache miss)")
        return schema

    @pytest.fixture(scope="class")
    def gemini_schema(self, schema_fetcher):
        schema = schema_fetcher("gemini", SCHEMA_URLS["gemini"])
        if schema is None:
            pytest.skip("Gemini schema unavailable (offline or cache miss)")
        return schema

    def test_claude_settings_validates_against_schema(self, claude_schema):
        config = load_config_file(_config_root() / "claude" / "settings.json", "json")
        jsonschema.validate(config, claude_schema)

    def test_claude_settings_has_no_unknown_keys(self, claude_schema):
        """Catch keys we ship that are deprecated or never existed upstream.

        The upstream schema uses additionalProperties: true, so standard
        validation never rejects unknown keys. This test explicitly checks
        that every top-level key in our base settings.json is recognized by
        the schema.
        """
        config = load_config_file(_config_root() / "claude" / "settings.json", "json")
        schema_props = set(claude_schema.get("properties", {}).keys())
        our_keys = set(config.keys())
        unknown = our_keys - schema_props - KNOWN_CLAUDE_SCHEMA_MISSING_KEYS
        assert not unknown, (
            f"Base settings.json contains keys not in upstream schema: {unknown}. "
            f"These may be deprecated — remove them to avoid stale config."
        )

    def test_codex_config_validates_against_schema(self, codex_schema):
        config = load_config_file(_config_root() / "codex" / "config.toml", "toml")
        jsonschema.validate(config, codex_schema)

    def test_gemini_settings_validates_against_schema(self, gemini_schema):
        config = load_config_file(_config_root() / "gemini" / "settings.json", "json")
        jsonschema.validate(config, gemini_schema)


@pytest.mark.integration
@pytest.mark.schema
class TestLocalSchemaValidation:
    def test_goose_config_validates_against_structural_fixture(self):
        goose_schema = json.loads(GOOSE_SCHEMA_PATH.read_text())
        config = load_config_file(_config_root() / "goose" / "config.yaml", "yaml")
        jsonschema.validate(config, goose_schema)
