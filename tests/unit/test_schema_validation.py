import json
import os
import urllib.error
import urllib.request

from importlib.resources import files as resource_files
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import pytest

from ai_rules.config import load_config_file

# Live URLs point at upstream main — intentionally floating so tests catch
# schema drift early. These tests are excluded from default runs via the
# network marker; failures indicate real config/schema divergence.
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


@pytest.mark.schema
@pytest.mark.network
class TestSchemaValidation:
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

    def test_codex_config_validates_against_schema(self, codex_schema):
        config = load_config_file(_config_root() / "codex" / "config.toml", "toml")
        jsonschema.validate(config, codex_schema)

    def test_gemini_settings_validates_against_schema(self, gemini_schema):
        config = load_config_file(_config_root() / "gemini" / "settings.json", "json")
        jsonschema.validate(config, gemini_schema)

    def test_goose_config_validates_against_structural_fixture(self):
        goose_schema = json.loads(GOOSE_SCHEMA_PATH.read_text())
        config = load_config_file(_config_root() / "goose" / "config.yaml", "yaml")
        jsonschema.validate(config, goose_schema)


@pytest.mark.schema
class TestSchemaCacheBehavior:
    @staticmethod
    def _mock_response(data: bytes) -> object:
        class FakeResponse:
            def read(self):
                return data

        return FakeResponse()

    def test_cache_written_after_successful_fetch(
        self, tmp_path, monkeypatch, schema_fetcher
    ):
        schema = {"type": "object"}
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda url, timeout=10: TestSchemaCacheBehavior._mock_response(
                json.dumps(schema).encode()
            ),
        )
        result = schema_fetcher(
            "test", "http://example.com/schema.json", _cache_dir=tmp_path
        )

        assert result == schema
        assert (tmp_path / "test.schema.json").exists()

    def test_cache_reused_within_ttl(self, tmp_path, monkeypatch, schema_fetcher):
        schema = {"type": "object", "cached": True}
        cache_file = tmp_path / "test.schema.json"
        cache_file.write_text(json.dumps(schema))

        def fail_if_called(*args, **kwargs):
            raise AssertionError("urlopen should not be called when cache is fresh")

        monkeypatch.setattr(urllib.request, "urlopen", fail_if_called)
        result = schema_fetcher(
            "test", "http://example.com/schema.json", _cache_dir=tmp_path
        )

        assert result == schema

    def test_stale_cache_used_when_fetch_fails(
        self, tmp_path, monkeypatch, schema_fetcher
    ):
        schema = {"type": "object", "stale": True}
        cache_file = tmp_path / "test.schema.json"
        cache_file.write_text(json.dumps(schema))
        os.utime(cache_file, (0, 0))

        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda url, timeout=10: (_ for _ in ()).throw(
                urllib.error.URLError("network down")
            ),
        )
        result = schema_fetcher(
            "test", "http://example.com/schema.json", _cache_dir=tmp_path
        )

        assert result == schema

    def test_stale_cache_refreshed_when_fetch_succeeds(
        self, tmp_path, monkeypatch, schema_fetcher
    ):
        stale_schema = {"type": "object", "version": "old"}
        fresh_schema = {"type": "object", "version": "new"}
        cache_file = tmp_path / "test.schema.json"
        cache_file.write_text(json.dumps(stale_schema))
        os.utime(cache_file, (0, 0))

        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda url, timeout=10: TestSchemaCacheBehavior._mock_response(
                json.dumps(fresh_schema).encode()
            ),
        )
        result = schema_fetcher(
            "test", "http://example.com/schema.json", _cache_dir=tmp_path
        )

        assert result == fresh_schema
        assert json.loads(cache_file.read_text()) == fresh_schema

    def test_returns_none_when_no_cache_and_no_network(
        self, tmp_path, monkeypatch, schema_fetcher
    ):
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda url, timeout=10: (_ for _ in ()).throw(
                urllib.error.URLError("network down")
            ),
        )
        result = schema_fetcher(
            "test", "http://example.com/schema.json", _cache_dir=tmp_path
        )

        assert result is None
