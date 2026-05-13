import argparse
import json
import re
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

from session_search import readers  # noqa: E402
from session_search.core import Session  # noqa: E402
from session_search.readers import amp, claude, codex, gemini, goose  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def make_args(**kwargs: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = dict(
        max_matches=40,
        width=280,
        ignore_case=False,
        cwd="/tmp",
        repo=None,
        all_repos=True,
        since=None,
        until=None,
        oldest=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def make_session(agent: str, path: str, **kwargs: Any) -> Session:
    defaults: dict[str, Any] = dict(
        id="test-session-001",
        timestamp="2026-01-01T10:00:00Z",
        updated_at="2026-01-01T10:00:00Z",
        title="Test Session",
        cwd="/tmp/project",
        repo_score=0,
        repo_reason="",
    )
    defaults.update(kwargs)
    return Session(agent=agent, path=Path(path), **defaults)


# ---------------------------------------------------------------------------
# Codex JSONL fixture
# ---------------------------------------------------------------------------

CODEX_LINES = [
    json.dumps(
        {
            "type": "session_meta",
            "timestamp": "2026-01-01T10:00:00Z",
            "payload": {
                "id": "test-001",
                "timestamp": "2026-01-01T10:00:00Z",
                "cwd": "/tmp/project",
                "agent_role": "assistant",
                "agent_nickname": "",
            },
        }
    ),
    json.dumps(
        {
            "type": "response_item",
            "timestamp": "2026-01-01T10:00:01Z",
            "payload": {
                "role": "assistant",
                "content": [{"text": "Here is the result"}],
            },
        }
    ),
    json.dumps(
        {
            "type": "event_msg",
            "timestamp": "2026-01-01T10:00:02Z",
            "payload": {
                "type": "exec_command_end",
                "command": ["git", "status"],
                "cwd": "/tmp/project",
                "aggregated_output": "On branch main",
                "exit_code": 0,
            },
        }
    ),
]

# ---------------------------------------------------------------------------
# Claude JSONL fixture
# ---------------------------------------------------------------------------

CLAUDE_LINES = [
    json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": "search for foo bar"},
            "cwd": "/tmp/project",
            "sessionId": "test-claude",
            "timestamp": "2026-01-01T10:00:00Z",
            "uuid": "u1",
        }
    ),
    json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I found foo xyz bar in the results"}
                ],
            },
            "cwd": "/tmp/project",
            "sessionId": "test-claude",
            "timestamp": "2026-01-01T10:00:01Z",
            "uuid": "u2",
        }
    ),
]

# ---------------------------------------------------------------------------
# Gemini JSONL fixture
# ---------------------------------------------------------------------------

GEMINI_LINES = [
    json.dumps(
        {
            "type": "user",
            "sessionId": "test-gemini",
            "startTime": "2026-01-01T10:00:00Z",
            "content": "find foo bar in codebase",
        }
    ),
    json.dumps(
        {
            "type": "gemini",
            "content": "I searched and found foo xyz bar",
            "toolCalls": [{"name": "read_file", "args": {"path": "/tmp/test"}}],
        }
    ),
]

# ---------------------------------------------------------------------------
# Amp JSON fixture
# ---------------------------------------------------------------------------

AMP_DATA = {
    "v": 1,
    "id": "T-test",
    "created": 1704067200000,
    "messages": [
        {
            "role": "user",
            "messageId": 0,
            "content": [{"type": "text", "text": "find foo bar"}],
            "meta": {"sentAt": 1704067200000},
        },
        {
            "role": "assistant",
            "messageId": 1,
            "content": [{"type": "text", "text": "foo xyz bar result"}],
            "meta": {"sentAt": 1704067201000},
        },
    ],
    "title": "test thread",
}


# ---------------------------------------------------------------------------
# iter_search_text — Codex
# ---------------------------------------------------------------------------


def test_codex_iter_search_text_exec_command_end_yields_command_and_output():
    record = {
        "type": "event_msg",
        "payload": {
            "type": "exec_command_end",
            "command": ["ls", "-la"],
            "aggregated_output": "total 42\ndrwxr-xr-x  ...",
        },
    }
    results = list(codex.iter_search_text(record, ""))
    combined = " ".join(results)
    assert "ls" in combined
    assert "total 42" in combined


def test_codex_iter_search_text_exec_command_list_yields_shell_quoted_form():
    record = {
        "type": "event_msg",
        "payload": {
            "type": "exec_command_end",
            "command": ["git", "status"],
            "aggregated_output": "On branch main",
        },
    }
    results = list(codex.iter_search_text(record, ""))
    assert any("git" in r and "status" in r for r in results)


def test_codex_iter_search_text_response_item_yields_content_text():
    record = {
        "type": "response_item",
        "payload": {
            "role": "assistant",
            "content": [{"text": "Here is the result"}],
        },
    }
    results = list(codex.iter_search_text(record, ""))
    assert any("Here is the result" in r for r in results)


def test_codex_iter_search_text_session_meta_yields_id_and_cwd():
    record = {
        "type": "session_meta",
        "payload": {"id": "sess-abc", "cwd": "/home/user/project"},
    }
    results = list(codex.iter_search_text(record, ""))
    assert "sess-abc" in results
    assert "/home/user/project" in results


# ---------------------------------------------------------------------------
# iter_search_text — Claude
# ---------------------------------------------------------------------------


def test_claude_iter_search_text_tool_use_yields_name_and_input():
    record = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "id": "123",
                    "input": {"command": "git status"},
                }
            ],
        },
    }
    results = list(claude.iter_search_text(record, ""))
    combined = " ".join(results)
    assert "Bash" in combined
    assert "git status" in combined


def test_claude_iter_search_text_text_block_yields_text():
    record = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "I found something interesting"}],
        },
    }
    results = list(claude.iter_search_text(record, ""))
    assert any("I found something interesting" in r for r in results)


def test_claude_iter_search_text_user_message_yields_content():
    record = {
        "type": "user",
        "message": {"role": "user", "content": "please run git status"},
    }
    results = list(claude.iter_search_text(record, ""))
    assert any("git status" in r for r in results)


# ---------------------------------------------------------------------------
# iter_search_text — Gemini
# ---------------------------------------------------------------------------


def test_gemini_iter_search_text_tool_calls_yields_name_and_args():
    record = {
        "type": "gemini",
        "content": "some text",
        "toolCalls": [{"name": "read_file", "args": {"path": "/tmp/test"}}],
    }
    results = list(gemini.iter_search_text(record, ""))
    combined = " ".join(results)
    assert "read_file" in combined
    assert "/tmp/test" in combined


def test_gemini_iter_search_text_content_text_yielded():
    record = {
        "type": "gemini",
        "content": "I analyzed the foo bar pattern",
        "toolCalls": [],
    }
    results = list(gemini.iter_search_text(record, ""))
    assert any("foo bar" in r for r in results)


def test_gemini_iter_search_text_user_type_yields_content():
    record = {"type": "user", "content": "search the codebase for foo"}
    results = list(gemini.iter_search_text(record, ""))
    assert any("foo" in r for r in results)


# ---------------------------------------------------------------------------
# iter_search_text — Goose
# ---------------------------------------------------------------------------


def test_goose_iter_search_text_tool_request_yields_name_and_arguments():
    record = {
        "role": "user",
        "content_json_parsed": [
            {
                "type": "toolRequest",
                "id": "1",
                "toolCall": {
                    "Ok": {
                        "name": "developer__shell",
                        "arguments": {"command": "echo hello"},
                    }
                },
            }
        ],
    }
    results = list(goose.iter_search_text(record, ""))
    combined = " ".join(results)
    assert "developer__shell" in combined
    assert "echo hello" in combined


def test_goose_iter_search_text_text_block_yields_text():
    record = {
        "role": "assistant",
        "content_json_parsed": [
            {"type": "text", "text": "Task completed successfully"}
        ],
    }
    results = list(goose.iter_search_text(record, ""))
    assert "Task completed successfully" in results


def test_goose_iter_search_text_tool_response_yields_output_text():
    record = {
        "role": "user",
        "content_json_parsed": [
            {
                "type": "toolResponse",
                "toolResult": {"Ok": [{"text": "command output here"}]},
            }
        ],
    }
    results = list(goose.iter_search_text(record, ""))
    assert "command output here" in results


# ---------------------------------------------------------------------------
# iter_search_text — Amp
# ---------------------------------------------------------------------------


def test_amp_iter_search_text_tool_use_yields_name_and_input():
    record = {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "1", "name": "Bash", "input": {"command": "ls"}}
        ],
    }
    results = list(amp.iter_search_text(record, ""))
    combined = " ".join(results)
    assert "Bash" in combined
    assert "ls" in combined


def test_amp_iter_search_text_tool_result_yields_content_text():
    record = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "content": [{"type": "text", "text": "file contents here"}],
            }
        ],
    }
    results = list(amp.iter_search_text(record, ""))
    assert "file contents here" in results


def test_amp_iter_search_text_text_block_yields_text():
    record = {
        "role": "user",
        "content": [{"type": "text", "text": "please help me debug"}],
    }
    results = list(amp.iter_search_text(record, ""))
    assert "please help me debug" in results


# ---------------------------------------------------------------------------
# search_session — Codex (file-based)
# ---------------------------------------------------------------------------


def test_codex_search_session_finds_match_in_command_output(tmp_path, capsys):
    session_file = tmp_path / "rollout-2026-01-01T10-00-00-test-001.jsonl"
    session_file.write_text("\n".join(CODEX_LINES) + "\n")

    session = make_session("codex", session_file, id="test-001")
    pattern = re.compile(r"On branch main")
    args = make_args()

    count = codex.search_session(session, pattern, args)

    assert count >= 1
    captured = capsys.readouterr()
    assert "test-001" in captured.out


def test_codex_search_session_header_printed_on_first_match(tmp_path, capsys):
    session_file = tmp_path / "rollout-2026-01-01T10-00-00-test-001.jsonl"
    session_file.write_text("\n".join(CODEX_LINES) + "\n")

    session = make_session("codex", session_file, id="test-001")
    pattern = re.compile(r"git")
    args = make_args()

    codex.search_session(session, pattern, args)

    captured = capsys.readouterr()
    assert "[codex]" in captured.out
    assert "test-001" in captured.out


def test_codex_search_session_max_matches_respected(tmp_path, capsys):
    lines = []
    for i in range(10):
        lines.append(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "exec_command_end",
                        "command": ["echo", f"msg-{i}"],
                        "aggregated_output": f"output-line-{i}",
                    },
                }
            )
        )
    session_file = tmp_path / "rollout-2026-01-01T10-00-00-multi.jsonl"
    session_file.write_text("\n".join(lines) + "\n")

    session = make_session("codex", session_file, id="multi")
    pattern = re.compile(r"output-line")
    args = make_args(max_matches=1)

    count = codex.search_session(session, pattern, args)

    assert count == 1


def test_codex_search_session_no_match_returns_zero(tmp_path, capsys):
    session_file = tmp_path / "rollout-2026-01-01T10-00-00-test-001.jsonl"
    session_file.write_text("\n".join(CODEX_LINES) + "\n")

    session = make_session("codex", session_file, id="test-001")
    pattern = re.compile(r"zzznomatch")
    args = make_args()

    count = codex.search_session(session, pattern, args)

    assert count == 0
    captured = capsys.readouterr()
    assert "[codex]" not in captured.out


def test_codex_search_session_width_truncation(tmp_path, capsys):
    long_output = "x" * 500
    lines = [
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "command": ["cat", "file"],
                    "aggregated_output": long_output,
                },
            }
        )
    ]
    session_file = tmp_path / "rollout-2026-01-01T10-00-00-wide.jsonl"
    session_file.write_text("\n".join(lines) + "\n")

    session = make_session("codex", session_file, id="wide")
    pattern = re.compile(r"x{10}")
    args = make_args(width=50)

    codex.search_session(session, pattern, args)

    captured = capsys.readouterr()
    content_lines = [
        l
        for l in captured.out.splitlines()
        if l and not l.startswith("===") and not l.startswith("    ")
    ]
    for line in content_lines:
        assert "..." in line or len(line) <= 60


# ---------------------------------------------------------------------------
# search_session — Claude (file-based)
# ---------------------------------------------------------------------------


def test_claude_search_session_finds_match_in_text(tmp_path, capsys):
    session_file = tmp_path / "test-claude.jsonl"
    session_file.write_text("\n".join(CLAUDE_LINES) + "\n")

    session = make_session("claude", session_file, id="test-claude", cwd="/tmp/project")
    pattern = re.compile(r"foo xyz bar")
    args = make_args()

    count = claude.search_session(session, pattern, args)

    assert count >= 1
    captured = capsys.readouterr()
    assert "test-claude" in captured.out


def test_claude_search_session_header_includes_agent_tag(tmp_path, capsys):
    session_file = tmp_path / "test-claude.jsonl"
    session_file.write_text("\n".join(CLAUDE_LINES) + "\n")

    session = make_session("claude", session_file, id="test-claude", cwd="/tmp/project")
    pattern = re.compile(r"foo")
    args = make_args()

    claude.search_session(session, pattern, args)

    captured = capsys.readouterr()
    assert "[claude]" in captured.out


def test_claude_search_session_max_matches_one_stops_early(tmp_path, capsys):
    lines = []
    for i in range(5):
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": f"foo bar iteration {i}"},
                    "cwd": "/tmp",
                    "sessionId": "s1",
                    "timestamp": "2026-01-01T10:00:00Z",
                    "uuid": f"u{i}",
                }
            )
        )
    session_file = tmp_path / "multi.jsonl"
    session_file.write_text("\n".join(lines) + "\n")

    session = make_session("claude", session_file, id="multi", cwd="/tmp")
    pattern = re.compile(r"foo bar")
    args = make_args(max_matches=1)

    count = claude.search_session(session, pattern, args)

    assert count == 1


def test_claude_search_session_tool_use_block_is_searchable(tmp_path, capsys):
    record = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "id": "t1",
                    "input": {"command": "grep -r needle ."},
                }
            ],
        },
        "cwd": "/tmp",
        "sessionId": "tc",
        "timestamp": "2026-01-01T10:00:00Z",
        "uuid": "u1",
    }
    session_file = tmp_path / "tool.jsonl"
    session_file.write_text(json.dumps(record) + "\n")

    session = make_session("claude", session_file, id="tc", cwd="/tmp")
    pattern = re.compile(r"needle")
    args = make_args()

    count = claude.search_session(session, pattern, args)

    assert count >= 1


# ---------------------------------------------------------------------------
# search_session — Gemini (file-based)
# ---------------------------------------------------------------------------


def test_gemini_search_session_jsonl_finds_tool_call_name(tmp_path, capsys):
    session_file = tmp_path / "session-test-gemini.jsonl"
    session_file.write_text("\n".join(GEMINI_LINES) + "\n")

    session = make_session("gemini", session_file, id="test-gemini", cwd="/tmp/project")
    pattern = re.compile(r"read_file")
    args = make_args()

    count = gemini.search_session(session, pattern, args)

    assert count >= 1
    captured = capsys.readouterr()
    assert "[gemini]" in captured.out


def test_gemini_search_session_jsonl_finds_text_content(tmp_path, capsys):
    session_file = tmp_path / "session-test-gemini.jsonl"
    session_file.write_text("\n".join(GEMINI_LINES) + "\n")

    session = make_session("gemini", session_file, id="test-gemini", cwd="/tmp/project")
    pattern = re.compile(r"foo xyz bar")
    args = make_args()

    count = gemini.search_session(session, pattern, args)

    assert count >= 1


def test_gemini_search_session_jsonl_no_match_returns_zero(tmp_path, capsys):
    session_file = tmp_path / "session-test-gemini.jsonl"
    session_file.write_text("\n".join(GEMINI_LINES) + "\n")

    session = make_session("gemini", session_file, id="test-gemini", cwd="/tmp/project")
    pattern = re.compile(r"zzznomatch")
    args = make_args()

    count = gemini.search_session(session, pattern, args)

    assert count == 0


# ---------------------------------------------------------------------------
# search_session — Goose (SQLite-based)
# ---------------------------------------------------------------------------


def _make_goose_db(path: Path, session_id: str, content_json: str) -> None:
    with sqlite3.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS sessions "
            "(id TEXT PRIMARY KEY, name TEXT, working_dir TEXT, "
            "created_at TEXT, updated_at TEXT)"
        )
        con.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                "test session",
                "/tmp/project",
                "2026-01-01T10:00:00",
                "2026-01-01T10:00:00",
            ),
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS messages "
            "(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, "
            "content_json TEXT, created_timestamp TEXT)"
        )
        con.execute(
            "INSERT INTO messages VALUES (1, ?, 'assistant', ?, '2026-01-01T10:00:00')",
            (session_id, content_json),
        )
        con.commit()


def test_goose_search_session_db_finds_text_content(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "foo xyz bar found"}])
    _make_goose_db(db_path, "goose-sess-001", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-sess-001", cwd="/tmp/project")
    pattern = re.compile(r"foo xyz bar")
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count >= 1
    captured = capsys.readouterr()
    assert "[goose]" in captured.out
    assert "goose-sess-001" in captured.out


def test_goose_search_session_db_regex_no_sql_like_prefilter(
    tmp_path, capsys, monkeypatch
):
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "foo xyz bar"}])
    _make_goose_db(db_path, "goose-regex-001", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-regex-001", cwd="/tmp")
    pattern = re.compile(r"foo.*bar")
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count >= 1


def test_goose_search_session_db_no_match_returns_zero(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "unrelated content"}])
    _make_goose_db(db_path, "goose-nomatch", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-nomatch", cwd="/tmp")
    pattern = re.compile(r"zzznomatch")
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count == 0


def test_goose_search_session_db_max_matches_respected(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "sessions.db"
    with sqlite3.connect(str(db_path)) as con:
        con.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, name TEXT, "
            "working_dir TEXT, created_at TEXT, updated_at TEXT)"
        )
        con.execute(
            "INSERT INTO sessions VALUES (?, 'name', '/tmp', '2026-01-01', '2026-01-01')",
            ("goose-multi",),
        )
        con.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, "
            "role TEXT, content_json TEXT, created_timestamp TEXT)"
        )
        for i in range(5):
            content = json.dumps([{"type": "text", "text": f"foo xyz bar row {i}"}])
            con.execute(
                "INSERT INTO messages VALUES (?, ?, 'assistant', ?, '2026-01-01')",
                (i + 1, "goose-multi", content),
            )
        con.commit()

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-multi", cwd="/tmp")
    pattern = re.compile(r"foo xyz bar")
    args = make_args(max_matches=2)

    count = goose.search_session(session, pattern, args)

    assert count == 2


def test_goose_search_session_db_case_insensitive_flag(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "FOO XYZ BAR"}])
    _make_goose_db(db_path, "goose-ci-001", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-ci-001", cwd="/tmp")
    pattern = re.compile(r"foo xyz bar", re.IGNORECASE)
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count >= 1


# ---------------------------------------------------------------------------
# search_session — Amp (file-based)
# ---------------------------------------------------------------------------


def test_amp_search_session_finds_text_match(tmp_path, capsys):
    session_file = tmp_path / "T-test.json"
    session_file.write_text(json.dumps(AMP_DATA))

    session = make_session("amp", session_file, id="T-test", title="test thread")
    pattern = re.compile(r"foo xyz bar")
    args = make_args()

    count = amp.search_session(session, pattern, args)

    assert count >= 1
    captured = capsys.readouterr()
    assert "[amp]" in captured.out
    assert "T-test" in captured.out


def test_amp_search_session_finds_tool_use_name(tmp_path, capsys):
    data = {
        "v": 1,
        "id": "T-tool",
        "created": 1704067200000,
        "messages": [
            {
                "role": "assistant",
                "messageId": 0,
                "content": [
                    {
                        "type": "tool_use",
                        "id": "1",
                        "name": "GrepTool",
                        "input": {"pattern": "needle"},
                    }
                ],
                "meta": {"sentAt": 1704067200000},
            }
        ],
        "title": "tool test",
    }
    session_file = tmp_path / "T-tool.json"
    session_file.write_text(json.dumps(data))

    session = make_session("amp", session_file, id="T-tool", title="tool test")
    pattern = re.compile(r"GrepTool")
    args = make_args()

    count = amp.search_session(session, pattern, args)

    assert count >= 1


def test_amp_search_session_max_matches_one_stops_early(tmp_path, capsys):
    data = {
        "v": 1,
        "id": "T-multi",
        "created": 1704067200000,
        "messages": [
            {
                "role": "user",
                "messageId": i,
                "content": [{"type": "text", "text": f"foo bar iteration {i}"}],
                "meta": {"sentAt": 1704067200000 + i * 1000},
            }
            for i in range(5)
        ],
        "title": "multi",
    }
    session_file = tmp_path / "T-multi.json"
    session_file.write_text(json.dumps(data))

    session = make_session("amp", session_file, id="T-multi", title="multi")
    pattern = re.compile(r"foo bar")
    args = make_args(max_matches=1)

    count = amp.search_session(session, pattern, args)

    assert count == 1


def test_amp_search_session_no_match_returns_zero(tmp_path, capsys):
    session_file = tmp_path / "T-test.json"
    session_file.write_text(json.dumps(AMP_DATA))

    session = make_session("amp", session_file, id="T-test", title="test thread")
    pattern = re.compile(r"zzznomatch")
    args = make_args()

    count = amp.search_session(session, pattern, args)

    assert count == 0
    captured = capsys.readouterr()
    assert "[amp]" not in captured.out


# ---------------------------------------------------------------------------
# search_sessions dispatcher
# ---------------------------------------------------------------------------


def test_search_sessions_dispatcher_routes_to_correct_reader(tmp_path, capsys):
    session_file = tmp_path / "test-claude.jsonl"
    session_file.write_text("\n".join(CLAUDE_LINES) + "\n")

    session = make_session("claude", session_file, id="test-claude", cwd="/tmp/project")
    pattern = re.compile(r"foo xyz bar")
    args = make_args()

    total = readers.search_sessions([session], pattern, args)

    assert total >= 1


def test_search_sessions_dispatcher_aggregates_counts_across_sessions(tmp_path, capsys):
    file1 = tmp_path / "claude1.jsonl"
    file1.write_text("\n".join(CLAUDE_LINES) + "\n")

    amp_file = tmp_path / "T-test.json"
    amp_file.write_text(json.dumps(AMP_DATA))

    sessions = [
        make_session("claude", file1, id="c1", cwd="/tmp/project"),
        make_session("amp", amp_file, id="T-test", title="test thread"),
    ]
    pattern = re.compile(r"foo")
    args = make_args()

    total = readers.search_sessions(sessions, pattern, args)

    assert total >= 2


def test_search_sessions_dispatcher_max_matches_stops_early(tmp_path, capsys):
    lines = []
    for i in range(10):
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": f"foo bar hit {i}"},
                    "cwd": "/tmp",
                    "sessionId": "s1",
                    "timestamp": "2026-01-01T10:00:00Z",
                    "uuid": f"u{i}",
                }
            )
        )
    session_file = tmp_path / "multi.jsonl"
    session_file.write_text("\n".join(lines) + "\n")

    session = make_session("claude", session_file, id="multi", cwd="/tmp")
    pattern = re.compile(r"foo bar hit")
    args = make_args(max_matches=3)

    total = readers.search_sessions([session], pattern, args)

    assert total == 3


def test_search_sessions_dispatcher_unknown_agent_skipped(tmp_path, capsys):
    session = make_session("unknown_agent", tmp_path / "dummy.json", id="x")
    pattern = re.compile(r"anything")
    args = make_args()

    total = readers.search_sessions([session], pattern, args)

    assert total == 0


# ---------------------------------------------------------------------------
# cmd_grep — CLI integration
# ---------------------------------------------------------------------------


def test_cmd_grep_returns_zero_on_match(tmp_path, monkeypatch, capsys):
    session_file = tmp_path / "test-claude.jsonl"
    session_file.write_text("\n".join(CLAUDE_LINES) + "\n")

    session = make_session("claude", session_file, id="test-claude", cwd="/tmp/project")
    monkeypatch.setattr(
        readers,
        "iter_all_sessions",
        lambda _args: [session],
    )

    from session_search.__main__ import cmd_grep

    args = make_args(
        pattern=r"foo xyz bar",
        id=None,
        limit_sessions=25,
        all_repos=True,
    )
    args.pattern = r"foo xyz bar"

    result = cmd_grep(args)

    assert result == 0


def test_cmd_grep_returns_one_on_no_match(tmp_path, monkeypatch, capsys):
    session_file = tmp_path / "test-claude.jsonl"
    session_file.write_text("\n".join(CLAUDE_LINES) + "\n")

    session = make_session("claude", session_file, id="test-claude", cwd="/tmp/project")
    monkeypatch.setattr(
        readers,
        "iter_all_sessions",
        lambda _args: [session],
    )

    from session_search.__main__ import cmd_grep

    args = make_args(
        pattern=r"zzznomatch",
        id=None,
        limit_sessions=25,
        all_repos=True,
    )
    args.pattern = r"zzznomatch"

    result = cmd_grep(args)

    assert result == 1
    captured = capsys.readouterr()
    assert "No matches" in captured.out


def test_cmd_grep_returns_two_on_invalid_regex(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(readers, "iter_all_sessions", lambda _args: [])

    from session_search.__main__ import cmd_grep

    args = make_args(
        pattern=r"[invalid(",
        id=None,
        limit_sessions=25,
        all_repos=True,
    )
    args.pattern = r"[invalid("

    result = cmd_grep(args)

    assert result == 2


# ---------------------------------------------------------------------------
# Regex correctness — critical fix verification
# ---------------------------------------------------------------------------


def test_goose_regex_foo_star_bar_matches_foo_xyz_bar(tmp_path, monkeypatch, capsys):
    """Verify regex is applied directly without SQL LIKE prefilter."""
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "foo xyz bar"}])
    _make_goose_db(db_path, "goose-regex-fix", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-regex-fix", cwd="/tmp")
    pattern = re.compile(r"foo.*bar")
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count >= 1


def test_goose_regex_case_insensitive_matches_uppercase(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "NEEDLE in haystack"}])
    _make_goose_db(db_path, "goose-ci-needle", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-ci-needle", cwd="/tmp")
    pattern = re.compile(r"needle", re.IGNORECASE)
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count >= 1


def test_goose_regex_does_not_match_partial_without_wildcard(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "sessions.db"
    content = json.dumps([{"type": "text", "text": "foo baz bar"}])
    _make_goose_db(db_path, "goose-partial", content)

    monkeypatch.setattr(goose, "_db_path", lambda: db_path)

    session = make_session("goose", db_path, id="goose-partial", cwd="/tmp")
    pattern = re.compile(r"foo xyz bar")
    args = make_args()

    count = goose.search_session(session, pattern, args)

    assert count == 0
