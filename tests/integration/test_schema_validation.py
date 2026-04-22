import json

from importlib.resources import files as resource_files
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import pytest

from ai_rules.config import load_config_file

# Exact permission strings that the SchemaStore permissionRule pattern
# incorrectly rejects. The regex lookahead (?=.*[^)*?]) requires at least
# one non-wildcard character inside the argument, so bare (*) fails.
# Upstream issue: https://github.com/SchemaStore/schemastore/issues/5598
KNOWN_CLAUDE_SCHEMA_FALSE_POSITIVES: frozenset[str] = frozenset(
    {
        "Read(*)",
        "Skill(*)",
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


def _is_known_false_positive(err: jsonschema.ValidationError) -> bool:
    return (
        err.validator == "pattern"
        and err.instance in KNOWN_CLAUDE_SCHEMA_FALSE_POSITIVES
    )


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
        validator = jsonschema.Draft7Validator(claude_schema)
        all_errors = list(validator.iter_errors(config))

        known = [e for e in all_errors if _is_known_false_positive(e)]
        unexpected = [e for e in all_errors if not _is_known_false_positive(e)]

        if unexpected:
            raise unexpected[0]

        if known:
            pytest.xfail(
                f"SchemaStore permissionRule false positive "
                f"({len(known)} instance(s): {[e.instance for e in known]})"
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
