"""End-to-end coverage of the settings-cache merge/preserve pipeline.

These tests pin the behavior of the layered cache build
(``merge_settings`` -> ``_reconcile_cache`` -> ``ManagedFieldsTracker``) across
a real install -> user-edit -> source-change -> reinstall cycle. They are the
behavioral oracle for any future consolidation of that pipeline: the exact
guarantees asserted here are the ones that must not regress.

Two distinct preservation mechanisms are exercised against Claude (the only
agent with a managed-fields tracker, since its config is JSON):

* Top-level keys — ai-rules-contributed keys update/disappear with the source
  while unmanaged user keys survive (``_reconcile_cache`` user pass-through +
  ``_contributed_keys`` tracking).
* Preserved fields — agent-managed structures like ``hooks`` deep-merge user
  additions back in while stale ai-rules contributions are pruned
  (``ManagedFieldsTracker.cleanup_stale_entries`` / ``_cleanup_hooks``).
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.helpers import build_config_dir, goose_config_dir, make_cli_runner

ONLY = ["--only", "settings,agents-md,config", "--agents", "claude"]


def _hook_entry(command: str) -> dict:
    return {"hooks": [{"type": "command", "command": command}]}


@pytest.fixture
def claude_merge_env(isolated_home, tmp_path):
    """Install Claude from a toy config and return helpers to drive reinstalls.

    Yields ``(write_source, reinstall, settings_path)`` where ``write_source``
    rewrites the base ``claude/settings.json`` and ``reinstall`` runs the
    scoped install again. Changing the source content makes the cache stale via
    the content diff in ``is_cache_stale`` (base-settings mtime is ignored), so
    no artificial mtime bump is needed.
    """
    home, env = isolated_home
    config = build_config_dir(tmp_path / "rules")
    run = make_cli_runner(home, env)
    source = config / "claude" / "settings.json"
    settings_path = home / ".claude" / "settings.json"

    def write_source(settings: dict) -> None:
        source.write_text(json.dumps(settings), encoding="utf-8")

    def reinstall() -> None:
        result = run(
            ["install", "-y", "--skip-completions", *ONLY, "--config-dir", str(config)]
        )
        assert result.returncode == 0, result.stdout + result.stderr

    return write_source, reinstall, settings_path


@pytest.mark.e2e
class TestSettingsMergePreservation:
    def test_top_level_user_key_survives_while_airules_keys_track_source(
        self, claude_merge_env
    ):
        write_source, reinstall, settings_path = claude_merge_env

        # 1. Install with two ai-rules-managed top-level keys.
        write_source({"theme": "dark", "oldKey": "x"})
        reinstall()
        assert json.loads(settings_path.read_text("utf-8")) == {
            "oldKey": "x",
            "theme": "dark",
        }

        # 2. User adds an unmanaged top-level key to the live (symlinked) cache.
        data = json.loads(settings_path.read_text("utf-8"))
        data["userKey"] = "keep"
        settings_path.write_text(json.dumps(data), encoding="utf-8")

        # 3. Source changes: an ai-rules key updates, another is removed.
        write_source({"theme": "light"})
        reinstall()

        final = json.loads(settings_path.read_text("utf-8"))
        assert final["theme"] == "light", "ai-rules key should update with source"
        assert "oldKey" not in final, "stale ai-rules key should be pruned"
        assert final["userKey"] == "keep", "unmanaged user key must survive"

    def test_preserved_hooks_field_prunes_stale_airules_entry_keeps_user_hook(
        self, claude_merge_env
    ):
        write_source, reinstall, settings_path = claude_merge_env

        # 1. Install with an ai-rules-contributed hook under a preserved field.
        write_source(
            {
                "theme": "dark",
                "hooks": {"UserPromptSubmit": [_hook_entry("airules-cmd")]},
            }
        )
        reinstall()

        # 2. User appends their own hook to the same event in the live cache.
        data = json.loads(settings_path.read_text("utf-8"))
        data["hooks"]["UserPromptSubmit"].append(_hook_entry("user-cmd"))
        settings_path.write_text(json.dumps(data), encoding="utf-8")

        # 3. Source drops the ai-rules hook entirely.
        write_source({"theme": "dark"})
        reinstall()

        final = json.loads(settings_path.read_text("utf-8"))
        commands = [
            hook["command"]
            for entry in final.get("hooks", {}).get("UserPromptSubmit", [])
            for hook in entry["hooks"]
        ]
        assert "airules-cmd" not in commands, "stale ai-rules hook should be pruned"
        assert "user-cmd" in commands, "user-added hook must be preserved"

    def test_preserved_field_deep_merges_for_non_tracker_yaml_agent(
        self, isolated_home, tmp_path
    ):
        """Goose (yaml, no ManagedFieldsTracker) still preserves user entries.

        Exercises the non-json branch of _reconcile_cache: there is no tracker,
        so the top-level user-key pass-through is skipped, but the preserved
        'extensions' field must still deep-merge a user-added extension back in
        across a rebuild while a new ai-rules extension is also applied.
        """
        import yaml

        home, env = isolated_home
        config = build_config_dir(tmp_path / "rules")
        run = make_cli_runner(home, env)
        source = config / "goose" / "config.yaml"
        live = goose_config_dir(home) / "config.yaml"
        only = ["--only", "settings,agents-md,config", "--agents", "goose"]

        def reinstall() -> None:
            result = run(
                [
                    "install",
                    "-y",
                    "--skip-completions",
                    *only,
                    "--config-dir",
                    str(config),
                ]
            )
            assert result.returncode == 0, result.stdout + result.stderr

        # 1. Install with an ai-rules-contributed extension.
        source.write_text(
            yaml.safe_dump({"extensions": {"airules-ext": {"enabled": True}}}),
            encoding="utf-8",
        )
        reinstall()
        assert live.is_symlink(), "goose config.yaml should be a managed symlink"

        # 2. User adds their own extension to the live (symlinked) config.
        data = yaml.safe_load(live.read_text("utf-8")) or {}
        data.setdefault("extensions", {})["user-ext"] = {"enabled": True}
        live.write_text(yaml.safe_dump(data), encoding="utf-8")

        # 3. Source adds a second ai-rules extension, forcing a real rebuild
        #    (the preserved 'extensions' field now differs from the cache).
        source.write_text(
            yaml.safe_dump(
                {
                    "extensions": {
                        "airules-ext": {"enabled": True},
                        "airules-ext2": {"enabled": True},
                    }
                }
            ),
            encoding="utf-8",
        )
        reinstall()

        final = yaml.safe_load(live.read_text("utf-8")) or {}
        extensions = final.get("extensions", {})
        assert "user-ext" in extensions, "user extension must survive the rebuild"
        assert "airules-ext2" in extensions, "new ai-rules extension should be applied"
