import json
import os
import urllib.error
import urllib.request

import pytest


@pytest.mark.unit
class TestSchemaFetcherCacheBehavior:
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
            lambda url, timeout=10: TestSchemaFetcherCacheBehavior._mock_response(
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
            lambda url, timeout=10: TestSchemaFetcherCacheBehavior._mock_response(
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
