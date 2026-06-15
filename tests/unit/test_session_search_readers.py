"""Unit tests for session_search reader modules (codex, claude, gemini, goose, amp)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from pathlib import Path
from typing import Any

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[2]
        / "src"
        / "ai_rules"
        / "config"
        / "skills"
        / "session-search"
        / "scripts"
    ),
)

import pytest

from session_search.readers import amp, buzz, claude, codex, gemini, goose

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _args(**kwargs: Any) -> argparse.Namespace:
    defaults = {
        "cwd": None,
        "repo": None,
        "all_repos": True,
        "since": None,
        "until": None,
        "limit": 0,
        "max_matches": 0,
        "width": 280,
        "agent": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Codex reader tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCodexReader:
    def test_codex_detect_returns_false_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "nonexistent"))

        assert codex.detect() is False

    def test_codex_detect_returns_true_when_sessions_dir_exists(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "sessions").mkdir()
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))

        assert codex.detect() is True

    def test_codex_detect_returns_true_when_archived_sessions_dir_exists(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "archived_sessions").mkdir()
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))

        assert codex.detect() is True

    def test_codex_iter_sessions_finds_session_with_meta(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))
        sessions_dir = tmp_path / "sessions" / "2026" / "01" / "01"
        sessions_dir.mkdir(parents=True)

        session_file = sessions_dir / "rollout-2026-01-01T10-00-00-abc123ef.jsonl"
        session_meta = {
            "type": "session_meta",
            "payload": {
                "id": "abc123ef",
                "timestamp": "2026-01-01T10:00:00Z",
                "cwd": "/home/user/myproject",
                "agent_role": "coder",
                "agent_nickname": "hal",
            },
        }
        response_item = {
            "type": "response_item",
            "payload": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello from codex"}],
            },
        }
        session_file.write_text(
            json.dumps(session_meta) + "\n" + json.dumps(response_item) + "\n"
        )

        index_entry = {
            "id": "abc123ef",
            "thread_name": "My Thread",
            "updated_at": "2026-01-01T10:05:00Z",
        }
        (tmp_path / "session_index.jsonl").write_text(json.dumps(index_entry) + "\n")

        sessions = codex.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.id == "abc123ef"
        assert s.cwd == "/home/user/myproject"
        assert s.title == "My Thread"
        assert s.agent == "codex"

    def test_codex_iter_sessions_falls_back_to_filename_id(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_file = sessions_dir / "rollout-2026-03-15T08-30-00-deadbeef.jsonl"
        session_file.write_text("{}\n")

        sessions = codex.iter_sessions(_args())

        assert len(sessions) == 1
        assert sessions[0].id == "deadbeef"

    def test_codex_iter_search_text_response_item_yields_text(self):
        record = {
            "type": "response_item",
            "payload": {
                "role": "assistant",
                "content": [{"type": "text", "text": "important output"}],
            },
        }

        texts = list(codex.iter_search_text(record, ""))

        assert "important output" in texts

    def test_codex_iter_search_text_session_meta_yields_fields(self):
        record = {
            "type": "session_meta",
            "payload": {
                "id": "abc123",
                "cwd": "/some/path",
                "agent_role": "coder",
                "agent_nickname": "",
            },
        }

        texts = list(codex.iter_search_text(record, ""))

        assert "abc123" in texts
        assert "/some/path" in texts
        assert "coder" in texts

    def test_codex_iter_search_text_response_item_also_yields_name_and_output(self):
        record = {
            "type": "response_item",
            "payload": {
                "name": "my_tool",
                "arguments": '{"x": 1}',
                "output": "tool ran",
            },
        }

        texts = list(codex.iter_search_text(record, ""))

        assert "my_tool" in texts
        assert "tool ran" in texts

    def test_codex_iter_search_text_skips_unknown_type(self):
        record = {"type": "unknown_type", "payload": {"data": "hidden"}}

        texts = list(codex.iter_search_text(record, "raw line"))

        assert texts == []

    def test_codex_display_text_session_meta_returns_json(self):
        record = {
            "type": "session_meta",
            "payload": {
                "id": "abc",
                "timestamp": "2026-01-01T10:00:00Z",
                "cwd": "/foo",
                "originator": "user",
                "agent_role": "coder",
                "agent_nickname": "bot",
            },
        }

        result = codex.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["id"] == "abc"
        assert parsed["cwd"] == "/foo"

    def test_codex_display_text_response_item_returns_role_and_text(self):
        record = {
            "type": "response_item",
            "payload": {
                "role": "assistant",
                "content": [{"type": "text", "text": "hello"}],
            },
        }

        result = codex.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "assistant"
        assert "hello" in parsed["text"]

    def test_codex_display_text_unknown_type_returns_raw(self):
        raw = '{"type": "unknown"}'
        record = json.loads(raw)

        result = codex.display_text(record, raw)

        assert result == raw

    def test_codex_iter_sessions_empty_dir_returns_no_sessions(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))
        (tmp_path / "sessions").mkdir()

        sessions = codex.iter_sessions(_args())

        assert sessions == []

    def test_codex_iter_sessions_skips_corrupt_json_lines(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path))
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_file = sessions_dir / "rollout-2026-01-01T10-00-00-aabbccdd.jsonl"
        session_file.write_text('NOT VALID JSON\n{"also": bad}\n')

        sessions = codex.iter_sessions(_args())

        assert len(sessions) == 1
        assert sessions[0].id == "aabbccdd"


# ---------------------------------------------------------------------------
# Claude reader tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClaudeReader:
    def test_claude_detect_returns_false_when_no_projects_dir(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "nonexistent"))

        assert claude.detect() is False

    def test_claude_detect_returns_true_when_projects_dir_exists(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "projects").mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))

        assert claude.detect() is True

    def test_claude_iter_sessions_finds_session_with_cwd(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)

        session_uuid = "550e8400-e29b-41d4-a716-446655440000"
        session_file = project_dir / f"{session_uuid}.jsonl"

        user_record = {
            "type": "user",
            "cwd": "/home/user/test-project",
            "message": {"content": "hello"},
        }
        ai_title_record = {"type": "ai-title", "aiTitle": "My session title"}
        session_file.write_text(
            json.dumps(user_record) + "\n" + json.dumps(ai_title_record) + "\n"
        )

        sessions = claude.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.id == session_uuid
        assert s.cwd == "/home/user/test-project"
        assert s.title == "My session title"

    def test_claude_iter_sessions_hint_score_for_matching_repo_name(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        project_dir = tmp_path / "projects" / "-home-user-my-repo"
        project_dir.mkdir(parents=True)

        session_file = project_dir / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jsonl"
        user_record = {
            "type": "user",
            "cwd": "/home/user/my-repo",
            "message": {"content": "hi"},
        }
        session_file.write_text(json.dumps(user_record) + "\n")

        sessions = claude.iter_sessions(_args(repo="my-repo"))

        assert len(sessions) == 1

    def test_claude_iter_sessions_returns_empty_for_empty_projects_dir(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        (tmp_path / "projects").mkdir()

        sessions = claude.iter_sessions(_args())

        assert sessions == []

    def test_claude_iter_search_text_user_string_content(self):
        record = {
            "type": "user",
            "message": {"content": "what is the meaning of life?"},
        }

        texts = list(claude.iter_search_text(record, ""))

        assert "what is the meaning of life?" in texts

    def test_claude_iter_search_text_user_list_content(self):
        record = {
            "type": "user",
            "message": {"content": [{"type": "text", "text": "block content"}]},
        }

        texts = list(claude.iter_search_text(record, ""))

        assert "block content" in texts

    def test_claude_iter_search_text_assistant_text_block(self):
        record = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "assistant reply here"}]},
        }

        texts = list(claude.iter_search_text(record, ""))

        assert "assistant reply here" in texts

    def test_claude_iter_search_text_assistant_tool_use_block(self):
        record = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "bash", "input": {"command": "ls"}}
                ]
            },
        }

        texts = list(claude.iter_search_text(record, ""))

        combined = " ".join(texts)
        assert "bash" in combined
        assert "ls" in combined

    def test_claude_iter_search_text_skips_unknown_type(self):
        record = {"type": "system", "data": "should be ignored"}

        texts = list(claude.iter_search_text(record, ""))

        assert texts == []

    def test_claude_display_text_user_record(self):
        record = {
            "type": "user",
            "message": {"content": "my question"},
        }

        result = claude.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "user"
        assert "my question" in parsed["text"]

    def test_claude_display_text_assistant_text_block(self):
        record = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "my answer"}]},
        }

        result = claude.display_text(record, "")

        assert "assistant" in result
        assert "my answer" in result

    def test_claude_display_text_assistant_tool_use_block(self):
        record = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "read_file",
                        "input": {"path": "/etc/hosts"},
                    }
                ]
            },
        }

        result = claude.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "assistant"
        assert parsed["tool"] == "read_file"

    def test_claude_display_text_unknown_type_returns_raw(self):
        raw = '{"type": "other", "x": 1}'
        record = json.loads(raw)

        result = claude.display_text(record, raw)

        assert result == raw.strip()


# ---------------------------------------------------------------------------
# Gemini reader tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGeminiReader:
    def _gemini_home(self, tmp_path: Path) -> Path:
        return tmp_path / "gemini_home"

    def _patch_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        home = self._gemini_home(tmp_path)
        (home / ".gemini" / "tmp").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("USERPROFILE", str(home))
        return home

    def test_gemini_detect_returns_false_when_no_tmp_dir(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "empty_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        assert gemini.detect() is False

    def test_gemini_detect_returns_true_when_tmp_dir_exists(
        self, tmp_path, monkeypatch
    ):
        self._patch_home(monkeypatch, tmp_path)

        assert gemini.detect() is True

    def test_gemini_iter_sessions_finds_jsonl_session(self, tmp_path, monkeypatch):
        home = self._patch_home(monkeypatch, tmp_path)
        slug = "my-project-slug"
        chats_dir = home / ".gemini" / "tmp" / slug / "chats"
        chats_dir.mkdir(parents=True)

        session_file = chats_dir / "session-2026-01-01T10-00-abcd1234.jsonl"
        first_line = {
            "sessionId": "abcd1234-session",
            "startTime": "2026-01-01T10:00:00Z",
            "lastUpdated": "2026-01-01T10:30:00Z",
        }
        user_line = {"type": "user", "content": "What is this?"}
        gemini_line = {"type": "gemini", "content": "This is a thing."}
        session_file.write_text(
            json.dumps(first_line)
            + "\n"
            + json.dumps(user_line)
            + "\n"
            + json.dumps(gemini_line)
            + "\n"
        )

        projects_json = home / ".gemini" / "projects.json"
        projects_json.write_text(
            json.dumps({"projects": {"/home/user/my-project": slug}})
        )

        sessions = gemini.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.id == "abcd1234-session"
        assert s.cwd == "/home/user/my-project"
        assert s.agent == "gemini"

    def test_gemini_iter_sessions_finds_legacy_json_session(
        self, tmp_path, monkeypatch
    ):
        home = self._patch_home(monkeypatch, tmp_path)
        slug = "legacy-slug"
        chats_dir = home / ".gemini" / "tmp" / slug / "chats"
        chats_dir.mkdir(parents=True)

        legacy_file = chats_dir / "session-legacy.json"
        legacy_data = {
            "history": [
                {"role": "user", "parts": [{"text": "hello"}]},
                {"role": "model", "parts": [{"text": "world"}]},
            ]
        }
        legacy_file.write_text(json.dumps(legacy_data))

        sessions = gemini.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.id == "session-legacy"
        assert s.agent == "gemini"

    def test_gemini_iter_sessions_skips_slug_dir_without_chats(
        self, tmp_path, monkeypatch
    ):
        home = self._patch_home(monkeypatch, tmp_path)
        (home / ".gemini" / "tmp" / "bare-slug").mkdir(parents=True)

        sessions = gemini.iter_sessions(_args())

        assert sessions == []

    def test_gemini_iter_search_text_user_record(self):
        record = {"type": "user", "content": "search query text"}

        texts = list(gemini.iter_search_text(record, ""))

        assert "search query text" in texts

    def test_gemini_iter_search_text_gemini_record_content(self):
        record = {"type": "gemini", "content": "model response text"}

        texts = list(gemini.iter_search_text(record, ""))

        assert "model response text" in texts

    def test_gemini_iter_search_text_gemini_record_thoughts(self):
        record = {
            "type": "gemini",
            "content": "",
            "thoughts": [{"text": "internal reasoning"}],
        }

        texts = list(gemini.iter_search_text(record, ""))

        assert "internal reasoning" in texts

    def test_gemini_iter_search_text_gemini_record_tool_calls(self):
        record = {
            "type": "gemini",
            "content": "",
            "toolCalls": [{"name": "search_web", "args": {"query": "python"}}],
        }

        texts = list(gemini.iter_search_text(record, ""))

        combined = " ".join(texts)
        assert "search_web" in combined
        assert "python" in combined

    def test_gemini_iter_search_text_skips_unknown_type(self):
        record = {"type": "metadata", "data": "ignored"}

        texts = list(gemini.iter_search_text(record, ""))

        assert texts == []

    def test_gemini_display_text_user_record(self):
        record = {"type": "user", "content": "my input"}

        result = gemini.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "user"
        assert parsed["text"] == "my input"

    def test_gemini_display_text_gemini_record_no_tools(self):
        record = {"type": "gemini", "content": "my reply"}

        result = gemini.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "gemini"
        assert parsed["text"] == "my reply"

    def test_gemini_display_text_gemini_record_with_tool_calls(self):
        record = {
            "type": "gemini",
            "content": "",
            "toolCalls": [{"name": "run_code", "args": {"lang": "py"}}],
        }

        result = gemini.display_text(record, "")
        parsed = json.loads(result)

        assert "toolCalls" in parsed
        assert parsed["toolCalls"][0]["name"] == "run_code"

    def test_gemini_display_text_unknown_type_returns_raw(self):
        raw = '{"type": "unknown", "val": 42}'
        record = json.loads(raw)

        result = gemini.display_text(record, raw)

        assert result == raw

    def test_gemini_iter_sessions_empty_chats_dir_returns_no_sessions(
        self, tmp_path, monkeypatch
    ):
        home = self._patch_home(monkeypatch, tmp_path)
        chats_dir = home / ".gemini" / "tmp" / "some-slug" / "chats"
        chats_dir.mkdir(parents=True)

        sessions = gemini.iter_sessions(_args())

        assert sessions == []


# ---------------------------------------------------------------------------
# Goose reader tests
# ---------------------------------------------------------------------------


def _create_goose_db(db_path: Path) -> None:
    con = sqlite3.connect(str(db_path))
    con.execute(
        "CREATE TABLE sessions ("
        "id TEXT PRIMARY KEY, "
        "name TEXT DEFAULT '', "
        "working_dir TEXT NOT NULL, "
        "created_at TIMESTAMP, "
        "updated_at TIMESTAMP, "
        "provider_name TEXT, "
        "goose_mode TEXT DEFAULT 'auto'"
        ")"
    )
    con.execute(
        "CREATE TABLE messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id TEXT NOT NULL, "
        "role TEXT NOT NULL, "
        "content_json TEXT NOT NULL, "
        "created_timestamp INTEGER NOT NULL"
        ")"
    )
    con.commit()
    con.close()


@pytest.mark.unit
class TestGooseReader:
    def _patch_db(self, monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
        monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    def _patch_legacy(self, monkeypatch: pytest.MonkeyPatch, legacy_dir: Path) -> None:
        monkeypatch.setattr(goose, "_legacy_dir", lambda: legacy_dir)

    def test_goose_detect_returns_false_when_neither_source_exists(
        self, tmp_path, monkeypatch
    ):
        self._patch_db(monkeypatch, tmp_path / "nonexistent.db")
        self._patch_legacy(monkeypatch, tmp_path / "nonexistent_dir")

        assert goose.detect() is False

    def test_goose_detect_returns_true_when_db_exists(self, tmp_path, monkeypatch):
        db = tmp_path / "sessions.db"
        _create_goose_db(db)
        self._patch_db(monkeypatch, db)
        self._patch_legacy(monkeypatch, tmp_path / "nonexistent_dir")

        assert goose.detect() is True

    def test_goose_detect_returns_true_when_legacy_jsonl_exists(
        self, tmp_path, monkeypatch
    ):
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "session.jsonl").write_text("{}\n")
        self._patch_db(monkeypatch, tmp_path / "nonexistent.db")
        self._patch_legacy(monkeypatch, legacy_dir)

        assert goose.detect() is True

    def test_goose_iter_sessions_reads_from_sqlite(self, tmp_path, monkeypatch):
        db = tmp_path / "sessions.db"
        _create_goose_db(db)
        con = sqlite3.connect(str(db))
        con.execute(
            "INSERT INTO sessions (id, name, working_dir, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "sess-1",
                "My Session",
                "/home/user/project",
                "2026-01-01T10:00:00",
                "2026-01-01T11:00:00",
            ),
        )
        con.commit()
        con.close()

        self._patch_db(monkeypatch, db)
        legacy_dir = tmp_path / "no_legacy"
        self._patch_legacy(monkeypatch, legacy_dir)

        sessions = goose.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.id == "sess-1"
        assert s.cwd == "/home/user/project"
        assert s.title == "My Session"
        assert s.agent == "goose"

    def test_goose_iter_sessions_prefers_sqlite_over_legacy(
        self, tmp_path, monkeypatch
    ):
        db = tmp_path / "sessions.db"
        _create_goose_db(db)
        con = sqlite3.connect(str(db))
        con.execute(
            "INSERT INTO sessions (id, name, working_dir, created_at) VALUES (?, ?, ?, ?)",
            ("db-session", "DB Session", "/db/path", "2026-01-01T10:00:00"),
        )
        con.commit()
        con.close()

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        meta = {
            "id": "legacy-session",
            "working_dir": "/legacy/path",
            "description": "Old",
        }
        (legacy_dir / "old.jsonl").write_text(json.dumps(meta) + "\n")

        self._patch_db(monkeypatch, db)
        self._patch_legacy(monkeypatch, legacy_dir)

        sessions = goose.iter_sessions(_args())

        ids = [s.id for s in sessions]
        assert "db-session" in ids
        assert "legacy-session" not in ids

    def test_goose_iter_sessions_reads_legacy_when_no_sqlite(
        self, tmp_path, monkeypatch
    ):
        self._patch_db(monkeypatch, tmp_path / "nonexistent.db")

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        meta = {
            "id": "legacy-abc",
            "working_dir": "/some/path",
            "description": "Legacy title",
        }
        (legacy_dir / "legacy-abc.jsonl").write_text(json.dumps(meta) + "\n")
        self._patch_legacy(monkeypatch, legacy_dir)

        sessions = goose.iter_sessions(_args())

        assert len(sessions) == 1
        assert sessions[0].id == "legacy-abc"
        assert sessions[0].title == "Legacy title"

    def test_goose_iter_search_text_text_block(self):
        record = {
            "role": "user",
            "content_json_parsed": [{"type": "text", "text": "user message"}],
        }

        texts = list(goose.iter_search_text(record, ""))

        assert "user message" in texts

    def test_goose_iter_search_text_tool_request_block(self):
        record = {
            "role": "assistant",
            "content_json_parsed": [
                {
                    "type": "toolRequest",
                    "toolCall": {
                        "Ok": {"name": "bash", "arguments": {"command": "echo hi"}}
                    },
                }
            ],
        }

        texts = list(goose.iter_search_text(record, ""))

        combined = " ".join(texts)
        assert "bash" in combined
        assert "echo hi" in combined

    def test_goose_iter_search_text_tool_response_block(self):
        record = {
            "role": "tool",
            "content_json_parsed": [
                {
                    "type": "toolResponse",
                    "toolResult": {"Ok": [{"text": "command output here"}]},
                }
            ],
        }

        texts = list(goose.iter_search_text(record, ""))

        assert "command output here" in texts

    def test_goose_iter_search_text_thinking_block(self):
        record = {
            "role": "assistant",
            "content_json_parsed": [{"type": "thinking", "thinking": "deep thoughts"}],
        }

        texts = list(goose.iter_search_text(record, ""))

        assert "deep thoughts" in texts

    def test_goose_iter_search_text_empty_blocks(self):
        record = {"role": "user", "content_json_parsed": []}

        texts = list(goose.iter_search_text(record, ""))

        assert texts == []

    def test_goose_display_text_text_block(self):
        record = {
            "role": "user",
            "content_json_parsed": [{"type": "text", "text": "my text"}],
        }

        result = goose.display_text(record, "")

        assert "user" in result
        assert "my text" in result

    def test_goose_display_text_tool_request_block(self):
        record = {
            "role": "assistant",
            "content_json_parsed": [
                {
                    "type": "toolRequest",
                    "toolCall": {"Ok": {"name": "list_files", "arguments": {}}},
                }
            ],
        }

        result = goose.display_text(record, "")
        parts = result.split(" | ")
        parsed = json.loads(parts[0])

        assert parsed["tool"] == "list_files"

    def test_goose_display_text_tool_response_block(self):
        record = {
            "role": "tool",
            "content_json_parsed": [
                {
                    "type": "toolResponse",
                    "toolResult": {"Ok": [{"text": "file list here"}]},
                }
            ],
        }

        result = goose.display_text(record, "")

        assert "file list here" in result

    def test_goose_display_text_no_blocks_returns_raw(self):
        raw = "raw fallback"
        record = {"role": "user", "content_json_parsed": []}

        result = goose.display_text(record, raw)

        assert result == raw


# ---------------------------------------------------------------------------
# Amp reader tests
# ---------------------------------------------------------------------------


def _make_amp_thread(tmp_path: Path, thread_id: str, **overrides: Any) -> Path:
    threads_dir = tmp_path / ".local" / "share" / "amp" / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "id": thread_id,
        "v": 1,
        "title": "Test session",
        "created": 1735689600000,
        "env": {
            "initial": json.dumps({"trees": [{"uri": "file:///home/user/test-repo"}]})
        },
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "hello amp"}],
                "meta": {"sentAt": 1735689660000},
            }
        ],
    }
    data.update(overrides)

    path = threads_dir / f"T-{thread_id}.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.unit
class TestAmpReader:
    def _patch_threads_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> Path:
        threads_dir = tmp_path / ".local" / "share" / "amp" / "threads"
        threads_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(amp, "_AMP_THREADS", threads_dir)
        return threads_dir

    def test_amp_detect_returns_false_when_no_threads_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(amp, "_AMP_THREADS", tmp_path / "nonexistent")

        assert amp.detect() is False

    def test_amp_detect_returns_true_when_threads_dir_exists(
        self, tmp_path, monkeypatch
    ):
        self._patch_threads_dir(monkeypatch, tmp_path)

        assert amp.detect() is True

    def test_amp_iter_sessions_extracts_cwd_from_env_initial(
        self, tmp_path, monkeypatch
    ):
        self._patch_threads_dir(monkeypatch, tmp_path)
        _make_amp_thread(tmp_path, "test-uuid-001")

        sessions = amp.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.cwd == "/home/user/test-repo"
        assert s.title == "Test session"
        assert s.agent == "amp"

    def test_amp_iter_sessions_graceful_fallback_when_env_missing(
        self, tmp_path, monkeypatch
    ):
        self._patch_threads_dir(monkeypatch, tmp_path)
        path = _make_amp_thread(tmp_path, "no-env-uuid")

        data = json.loads(path.read_text())
        del data["env"]
        path.write_text(json.dumps(data))

        sessions = amp.iter_sessions(_args())

        assert len(sessions) == 1
        assert sessions[0].cwd == ""

    def test_amp_iter_sessions_graceful_fallback_when_title_null(
        self, tmp_path, monkeypatch
    ):
        self._patch_threads_dir(monkeypatch, tmp_path)
        path = _make_amp_thread(tmp_path, "null-title-uuid")

        data = json.loads(path.read_text())
        data["title"] = None
        path.write_text(json.dumps(data))

        sessions = amp.iter_sessions(_args())

        assert len(sessions) == 1
        assert sessions[0].title == ""

    def test_amp_iter_sessions_graceful_with_empty_messages_array(
        self, tmp_path, monkeypatch
    ):
        self._patch_threads_dir(monkeypatch, tmp_path)
        path = _make_amp_thread(tmp_path, "empty-msgs-uuid")

        data = json.loads(path.read_text())
        data["messages"] = []
        path.write_text(json.dumps(data))

        sessions = amp.iter_sessions(_args())

        assert len(sessions) == 1
        assert sessions[0].id == "empty-msgs-uuid"

    def test_amp_iter_sessions_skips_corrupt_json_file(self, tmp_path, monkeypatch):
        threads_dir = self._patch_threads_dir(monkeypatch, tmp_path)
        (threads_dir / "T-bad-file.json").write_text("not valid json {{{")

        sessions = amp.iter_sessions(_args())

        assert sessions == []

    def test_amp_iter_sessions_returns_empty_for_empty_threads_dir(
        self, tmp_path, monkeypatch
    ):
        self._patch_threads_dir(monkeypatch, tmp_path)

        sessions = amp.iter_sessions(_args())

        assert sessions == []

    def test_amp_iter_search_text_text_block(self):
        record = {
            "role": "user",
            "content": [{"type": "text", "text": "user message"}],
        }

        texts = list(amp.iter_search_text(record, ""))

        assert "user message" in texts

    def test_amp_iter_search_text_tool_use_block(self):
        record = {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "bash", "input": {"command": "pwd"}}
            ],
        }

        texts = list(amp.iter_search_text(record, ""))

        combined = " ".join(texts)
        assert "bash" in combined
        assert "pwd" in combined

    def test_amp_iter_search_text_tool_result_block(self):
        record = {
            "role": "tool",
            "content": [
                {
                    "type": "tool_result",
                    "content": [{"text": "output text here"}],
                }
            ],
        }

        texts = list(amp.iter_search_text(record, ""))

        assert "output text here" in texts

    def test_amp_iter_search_text_thinking_block(self):
        record = {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "chain of thought"}],
        }

        texts = list(amp.iter_search_text(record, ""))

        assert "chain of thought" in texts

    def test_amp_iter_search_text_empty_content(self):
        record = {"role": "user", "content": []}

        texts = list(amp.iter_search_text(record, ""))

        assert texts == []

    def test_amp_iter_search_text_non_list_content_returns_empty(self):
        record = {"role": "user", "content": "plain string"}

        texts = list(amp.iter_search_text(record, ""))

        assert texts == []

    def test_amp_display_text_text_block(self):
        record = {
            "role": "user",
            "content": [{"type": "text", "text": "hello world"}],
        }

        result = amp.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "user"
        assert parsed["text"] == "hello world"

    def test_amp_display_text_tool_use_block(self):
        record = {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "read_file", "input": {"path": "/foo.txt"}}
            ],
        }

        result = amp.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "assistant"
        assert parsed["tool"] == "read_file"

    def test_amp_display_text_tool_result_block(self):
        record = {
            "role": "tool",
            "content": [
                {
                    "type": "tool_result",
                    "content": [{"text": "result content"}],
                }
            ],
        }

        result = amp.display_text(record, "")
        parsed = json.loads(result)

        assert "tool_result" in parsed

    def test_amp_display_text_empty_content_returns_role_only(self):
        record = {"role": "system", "content": []}

        result = amp.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "system"

    def test_amp_display_text_non_list_content_returns_role_only(self):
        record = {"role": "user", "content": None}

        result = amp.display_text(record, "")
        parsed = json.loads(result)

        assert parsed["role"] == "user"


# ---------------------------------------------------------------------------
# Buzz reader tests
# ---------------------------------------------------------------------------


def _buzz_channel(channel_id: str, name: str, created_at: int) -> dict[str, Any]:
    return {"channel_id": channel_id, "name": name, "created_at": created_at}


def _buzz_event(channel_id: str, content: str, created_at: int = 1781525643) -> dict:
    return {
        "id": "evt-" + channel_id,
        "kind": 9,
        "pubkey": "abc",
        "content": content,
        "created_at": created_at,
        "tags": [["h", channel_id]],
    }


def _grep_args(pattern: str, **kwargs: Any) -> argparse.Namespace:
    return _args(
        pattern=pattern,
        id=kwargs.pop("id", None),
        limit_sessions=kwargs.pop("limit_sessions", 25),
        **kwargs,
    )


@pytest.mark.unit
class TestBuzzReader:
    @pytest.fixture(autouse=True)
    def _reset_module_state(self):
        buzz._search_cache.clear()
        buzz._sweep_notified = False
        yield
        buzz._search_cache.clear()
        buzz._sweep_notified = False

    def _mock_buzz(self, monkeypatch, handler):
        monkeypatch.setattr(buzz, "_run_buzz", handler)

    # -- detect ----------------------------------------------------------

    def test_buzz_detect_returns_true_when_both_env_vars_present(self, monkeypatch):
        monkeypatch.setenv("BUZZ_PRIVATE_KEY", "nsec1xxx")
        monkeypatch.setenv("BUZZ_RELAY_URL", "wss://relay")

        assert buzz.detect() is True

    def test_buzz_detect_returns_false_when_relay_url_missing(self, monkeypatch):
        monkeypatch.setenv("BUZZ_PRIVATE_KEY", "nsec1xxx")
        monkeypatch.delenv("BUZZ_RELAY_URL", raising=False)

        assert buzz.detect() is False

    def test_buzz_detect_returns_false_when_private_key_missing(self, monkeypatch):
        monkeypatch.delenv("BUZZ_PRIVATE_KEY", raising=False)
        monkeypatch.setenv("BUZZ_RELAY_URL", "wss://relay")

        assert buzz.detect() is False

    # -- iter_sessions ---------------------------------------------------

    def test_buzz_iter_sessions_maps_channel_to_session(self, monkeypatch):
        self._mock_buzz(
            monkeypatch,
            lambda *a: [_buzz_channel("uuid-1", "general", 1781525643)],
        )

        sessions = buzz.iter_sessions(_args())

        assert len(sessions) == 1
        s = sessions[0]
        assert s.id == "uuid-1"
        assert s.title == "general"
        assert s.agent == "buzz"
        assert s.cwd == ""
        assert s.repo_score == 0
        assert str(s.path) == "buzz:uuid-1"
        # epoch int converted to ISO, sortable by core.date_key
        assert s.timestamp.startswith("2026-")
        assert s.timestamp == s.updated_at

    def test_buzz_iter_sessions_skips_channel_without_id(self, monkeypatch):
        self._mock_buzz(
            monkeypatch,
            lambda *a: [{"name": "broken", "created_at": 1781525643}],
        )

        assert buzz.iter_sessions(_args()) == []

    def test_buzz_iter_sessions_since_includes_recent_session(self, monkeypatch):
        # Regression: epoch int must convert or core.in_date_window drops it.
        recent = _buzz_channel("uuid-recent", "recent", 1781525643)  # 2026-06
        self._mock_buzz(monkeypatch, lambda *a: [recent])

        sessions = buzz.iter_sessions(_args(since="2026-01-01"))

        assert [s.id for s in sessions] == ["uuid-recent"]

    def test_buzz_iter_sessions_since_excludes_old_session(self, monkeypatch):
        old = _buzz_channel("uuid-old", "old", 1262304000)  # 2010-01-01
        self._mock_buzz(monkeypatch, lambda *a: [old])

        sessions = buzz.iter_sessions(_args(since="2026-01-01"))

        assert sessions == []

    # -- iter_search_text / display_text ---------------------------------

    def test_buzz_iter_search_text_yields_content(self):
        record = {"content": "hello world"}

        assert list(buzz.iter_search_text(record, "")) == ["hello world"]

    def test_buzz_iter_search_text_empty_content_yields_nothing(self):
        assert list(buzz.iter_search_text({"content": ""}, "")) == []

    def test_buzz_display_text_returns_json_with_converted_time(self):
        record = {"pubkey": "pk", "content": "msg", "created_at": 1781525643}

        parsed = json.loads(buzz.display_text(record, ""))

        assert parsed["pubkey"] == "pk"
        assert parsed["content"] == "msg"
        assert parsed["time"].startswith("2026-")

    # -- grep: fast path (unsaturated global search) ---------------------

    def test_buzz_grep_unsaturated_groups_by_h_tag_and_applies_full_regex(
        self, monkeypatch, capsys
    ):
        calls = []

        def handler(*args):
            calls.append(args)
            # global search returns hits across two channels, under the cap
            return [
                _buzz_event("uuid-1", "the password is hunter2"),
                _buzz_event("uuid-2", "the weather is nice"),
            ]

        self._mock_buzz(monkeypatch, handler)
        session = buzz.Session(
            id="uuid-1", agent="buzz", path=Path("buzz://uuid-1"),
            timestamp="2026-06-15T00:00:00+00:00",
            updated_at="2026-06-15T00:00:00+00:00",
            title="general", cwd="", repo_score=0, repo_reason="",
        )
        import re as _re

        count = buzz.search_session(session, _re.compile("password"), _grep_args("password"))

        assert count == 1
        # exactly one global search call, no per-channel get
        assert calls == [("messages", "search", "--query", "password", "--limit", "100")]
        out = capsys.readouterr().out
        assert "hunter2" in out

    def test_buzz_grep_memoizes_global_search_across_sessions(self, monkeypatch):
        calls = []

        def handler(*args):
            calls.append(args)
            return [_buzz_event("uuid-1", "match here")]

        self._mock_buzz(monkeypatch, handler)
        import re as _re

        pattern = _re.compile("match")
        args = _grep_args("match")
        for cid in ("uuid-1", "uuid-2"):
            s = buzz.Session(
                id=cid, agent="buzz", path=Path(f"buzz://{cid}"),
                timestamp="2026-06-15T00:00:00+00:00",
                updated_at="2026-06-15T00:00:00+00:00",
                title="t", cwd="", repo_score=0, repo_reason="",
            )
            buzz.search_session(s, pattern, args)

        # single global search despite two candidate sessions
        assert len(calls) == 1

    # -- grep: saturated -> bounded sweep --------------------------------

    def test_buzz_grep_saturated_falls_back_to_per_channel_sweep(
        self, monkeypatch, capsys
    ):
        calls = []

        def handler(*args):
            calls.append(args)
            if args[:2] == ("messages", "search"):
                # saturated: exactly the cap
                return [_buzz_event("uuid-x", "common") for _ in range(buzz._SEARCH_CAP)]
            # per-channel get for the swept channel
            return [_buzz_event("uuid-1", "the common word matches")]

        self._mock_buzz(monkeypatch, handler)
        session = buzz.Session(
            id="uuid-1", agent="buzz", path=Path("buzz://uuid-1"),
            timestamp="2026-06-15T00:00:00+00:00",
            updated_at="2026-06-15T00:00:00+00:00",
            title="general", cwd="", repo_score=0, repo_reason="",
        )
        import re as _re

        count = buzz.search_session(session, _re.compile("common"), _grep_args("common"))

        assert count == 1
        # search fired once (saturated), then a per-channel get for the candidate
        assert ("messages", "search", "--query", "common", "--limit", "100") in calls
        assert ("messages", "get", "--channel", "uuid-1", "--kinds", "9") in calls
        assert "swept" in capsys.readouterr().err

    # -- grep: no literal seed -> sweep ----------------------------------

    def test_buzz_grep_no_seed_goes_straight_to_sweep(self, monkeypatch, capsys):
        calls = []

        def handler(*args):
            calls.append(args)
            return [_buzz_event("uuid-1", "year 2026 here")]

        self._mock_buzz(monkeypatch, handler)
        session = buzz.Session(
            id="uuid-1", agent="buzz", path=Path("buzz://uuid-1"),
            timestamp="2026-06-15T00:00:00+00:00",
            updated_at="2026-06-15T00:00:00+00:00",
            title="general", cwd="", repo_score=0, repo_reason="",
        )
        import re as _re

        # \d{4} has no [A-Za-z0-9_] literal run usable as a seed
        count = buzz.search_session(session, _re.compile(r"\d{4}"), _grep_args(r"\d{4}"))

        assert count == 1
        # never issued a global search; went straight to per-channel get
        assert all(c[:2] != ("messages", "search") for c in calls)
        assert ("messages", "get", "--channel", "uuid-1", "--kinds", "9") in calls

    # -- grep: --id fragment ---------------------------------------------

    def test_buzz_grep_id_fragment_fetches_channel_directly(self, monkeypatch):
        calls = []

        def handler(*args):
            calls.append(args)
            return [_buzz_event("uuid-1", "scoped match")]

        self._mock_buzz(monkeypatch, handler)
        # dispatcher resolves the fragment to this full-UUID candidate; the
        # reader fetches it directly and never touches global search.
        session = buzz.Session(
            id="uuid-1", agent="buzz", path=Path("buzz://uuid-1"),
            timestamp="2026-06-15T00:00:00+00:00",
            updated_at="2026-06-15T00:00:00+00:00",
            title="general", cwd="", repo_score=0, repo_reason="",
        )
        import re as _re

        count = buzz.search_session(
            session, _re.compile("scoped"), _grep_args("scoped", id="uuid")
        )

        assert count == 1
        assert calls == [("messages", "get", "--channel", "uuid-1", "--kinds", "9")]

    # -- graceful degradation --------------------------------------------

    def test_buzz_iter_sessions_empty_when_run_buzz_returns_empty(self, monkeypatch):
        self._mock_buzz(monkeypatch, lambda *a: [])

        assert buzz.iter_sessions(_args()) == []

    def test_buzz_run_buzz_nonzero_exit_warns_and_returns_empty(
        self, monkeypatch, capsys
    ):
        import subprocess as _sp

        def fake_run(*a, **kw):
            raise _sp.CalledProcessError(2, a[0], stderr="relay unreachable")

        monkeypatch.setattr(buzz.subprocess, "run", fake_run)

        assert buzz._run_buzz("channels", "list") == []
        assert "relay unreachable" in capsys.readouterr().err

    def test_buzz_run_buzz_malformed_json_warns_and_returns_empty(
        self, monkeypatch, capsys
    ):
        class _Result:
            stdout = "not json"

        monkeypatch.setattr(buzz.subprocess, "run", lambda *a, **kw: _Result())

        assert buzz._run_buzz("channels", "list") == []
        assert "malformed JSON" in capsys.readouterr().err

    # -- literal seed extraction -----------------------------------------

    def test_buzz_literal_seed_plain_word(self):
        assert buzz._literal_seed("deployment") == "deployment"

    def test_buzz_literal_seed_picks_longest_run(self):
        assert buzz._literal_seed("ab.cdef.gh") == "cdef"

    def test_buzz_literal_seed_ignores_escaped_class(self):
        # \d{4} has no literal text: 'd' is escaped, '4' is inside a quantifier
        assert buzz._literal_seed(r"\d{4}") == ""

    def test_buzz_literal_seed_ignores_char_class(self):
        assert buzz._literal_seed(r"[a-z]+error") == "error"

    def test_buzz_literal_seed_drops_optional_char(self):
        # 'colou?r' -> the optional 'u' must not anchor the seed
        assert buzz._literal_seed("colou?r") == "colo"
