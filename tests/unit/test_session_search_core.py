import argparse
import json
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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

from session_search.core import (  # noqa: E402
    Session,
    date_key,
    in_date_window,
    matches_term,
    parse_iso,
    print_sessions,
    repo_name_from_path,
    repo_score,
    session_to_json,
    sorted_sessions,
    truncate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_session(
    id: str = "abc123",
    agent: str = "claude",
    path: str = "/home/user/.claude/sessions/abc123.json",
    timestamp: str = "2024-03-01T10:00:00Z",
    updated_at: str = "",
    title: str = "My Session",
    cwd: str = "/home/user/projects/myrepo",
    score: int = 0,
    reason: str = "",
) -> Session:
    return Session(
        id=id,
        agent=agent,
        path=Path(path),
        timestamp=timestamp,
        updated_at=updated_at,
        title=title,
        cwd=cwd,
        repo_score=score,
        repo_reason=reason,
    )


def make_args(since: str | None = None, until: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(since=since, until=until)


# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------


def test_session_is_frozen():
    s = make_session()
    with pytest.raises(AttributeError):
        s.id = "other"  # type: ignore


def test_sort_time_returns_updated_at_when_present():
    s = make_session(
        timestamp="2024-01-01T00:00:00Z", updated_at="2024-06-01T00:00:00Z"
    )
    assert s.sort_time == "2024-06-01T00:00:00Z"


def test_sort_time_falls_back_to_timestamp_when_updated_at_empty():
    s = make_session(timestamp="2024-01-01T00:00:00Z", updated_at="")
    assert s.sort_time == "2024-01-01T00:00:00Z"


def test_sort_time_falls_back_to_timestamp_when_updated_at_none():
    s = Session(
        id="x",
        agent="claude",
        path=Path("/tmp/x.json"),
        timestamp="2024-01-01T00:00:00Z",
        updated_at=None,  # type: ignore[arg-type]
        title="",
        cwd="",
        repo_score=0,
        repo_reason="",
    )
    assert s.sort_time == "2024-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# parse_iso
# ---------------------------------------------------------------------------


def test_parse_iso_z_suffix_returns_utc_datetime():
    result = parse_iso("2024-03-15T12:30:00Z")
    assert result == datetime(2024, 3, 15, 12, 30, 0, tzinfo=timezone.utc)


def test_parse_iso_timezone_offset_returns_aware_datetime():
    result = parse_iso("2024-03-15T12:30:00+05:00")
    assert result is not None
    assert result.utcoffset() == timedelta(hours=5)


def test_parse_iso_empty_string_returns_none():
    assert parse_iso("") is None


def test_parse_iso_invalid_string_returns_none():
    assert parse_iso("not-a-date") is None


def test_parse_iso_partial_string_returns_none():
    assert parse_iso("2024-13-99") is None


# ---------------------------------------------------------------------------
# date_key
# ---------------------------------------------------------------------------


def test_date_key_valid_iso_returns_datetime():
    result = date_key("2024-03-15T12:00:00Z")
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_date_key_empty_string_returns_min_utc():
    result = date_key("")
    assert result == datetime.min.replace(tzinfo=timezone.utc)


def test_date_key_invalid_string_returns_min_utc():
    result = date_key("garbage")
    assert result == datetime.min.replace(tzinfo=timezone.utc)


def test_date_key_naive_datetime_gets_utc():
    result = date_key("2024-03-15T12:00:00")
    assert result.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# repo_name_from_path
# ---------------------------------------------------------------------------


def test_repo_name_from_path_returns_last_component():
    assert repo_name_from_path("/home/user/projects/myrepo") == "myrepo"


def test_repo_name_from_path_empty_returns_empty():
    assert repo_name_from_path("") == ""


# ---------------------------------------------------------------------------
# repo_score
# ---------------------------------------------------------------------------


def test_repo_score_empty_session_cwd_returns_zero():
    assert repo_score("", "/home/user/myrepo", "/home/user/myrepo", "myrepo") == (0, "")


def test_repo_score_exact_cwd_match():
    assert repo_score(
        "/home/user/myrepo", "/home/user/myrepo", "/home/user/myrepo", "myrepo"
    ) == (
        3,
        "exact-cwd",
    )


def test_repo_score_session_equals_root_returns_exact_cwd():
    assert repo_score(
        "/home/user/myrepo", "/other/path", "/home/user/myrepo", "myrepo"
    ) == (
        3,
        "exact-cwd",
    )


def test_repo_score_subdirectory_of_root_returns_same_root():
    assert repo_score(
        "/home/user/myrepo/subdir",
        "/some/other/path",
        "/home/user/myrepo",
        "myrepo",
    ) == (3, "same-root")


def test_repo_score_same_repo_name():
    assert repo_score(
        "/home/user/work/myrepo",
        "/home/user/other/path",
        "/home/user/other",
        "myrepo",
    ) == (2, "same-repo")


def test_repo_score_repo_name_in_path():
    assert repo_score(
        "/home/user/archive/myrepo/old",
        "/home/user/other",
        "/home/user/other",
        "myrepo",
    ) == (1, "repo-name-in-path")


def test_repo_score_no_match_returns_zero():
    assert repo_score(
        "/home/user/unrelated", "/home/user/myrepo", "/home/user/myrepo", "myrepo"
    ) == (
        0,
        "",
    )


# ---------------------------------------------------------------------------
# in_date_window
# ---------------------------------------------------------------------------


def test_in_date_window_no_filters_returns_true():
    s = make_session(updated_at="2024-03-01T10:00:00Z")
    assert in_date_window(s, make_args()) is True


def test_in_date_window_session_within_window_returns_true():
    s = make_session(updated_at="2024-03-15T10:00:00Z")
    assert in_date_window(s, make_args(since="2024-03-01", until="2024-03-31")) is True


def test_in_date_window_session_before_since_returns_false():
    s = make_session(updated_at="2024-02-28T10:00:00Z")
    assert in_date_window(s, make_args(since="2024-03-01")) is False


def test_in_date_window_session_after_until_returns_false():
    s = make_session(updated_at="2024-04-01T10:00:00Z")
    assert in_date_window(s, make_args(until="2024-03-31")) is False


def test_in_date_window_session_on_until_date_returns_true():
    s = make_session(updated_at="2024-03-31T23:59:59Z")
    assert in_date_window(s, make_args(until="2024-03-31")) is True


# ---------------------------------------------------------------------------
# sorted_sessions
# ---------------------------------------------------------------------------


def test_sorted_sessions_orders_by_repo_score_descending():
    low = make_session(id="low", score=0, updated_at="2024-03-01T00:00:00Z")
    high = make_session(id="high", score=3, updated_at="2024-01-01T00:00:00Z")
    result = sorted_sessions([low, high], oldest=False)
    assert result[0].id == "high"


def test_sorted_sessions_within_same_score_orders_by_recency_descending():
    older = make_session(id="older", score=2, updated_at="2024-01-01T00:00:00Z")
    newer = make_session(id="newer", score=2, updated_at="2024-06-01T00:00:00Z")
    result = sorted_sessions([older, newer], oldest=False)
    assert result[0].id == "newer"


def test_sorted_sessions_oldest_true_sorts_ascending():
    older = make_session(id="older", score=0, updated_at="2024-01-01T00:00:00Z")
    newer = make_session(id="newer", score=0, updated_at="2024-06-01T00:00:00Z")
    result = sorted_sessions([older, newer], oldest=True)
    assert result[0].id == "older"


def test_sorted_sessions_tie_broken_by_title_then_id():
    a = make_session(
        id="zzz", score=1, title="Alpha", updated_at="2024-03-01T00:00:00Z"
    )
    b = make_session(id="aaa", score=1, title="Beta", updated_at="2024-03-01T00:00:00Z")
    result = sorted_sessions([a, b], oldest=False)
    assert result[0].title == "Beta"


# ---------------------------------------------------------------------------
# matches_term
# ---------------------------------------------------------------------------


def test_matches_term_matches_in_id():
    s = make_session(id="unique-abc-id")
    assert matches_term(s, "unique-abc") is True


def test_matches_term_matches_path_name():
    s = make_session(path="/home/user/.claude/sessions/special123.json")
    assert matches_term(s, "special123") is True


def test_matches_term_matches_full_path():
    s = make_session(path="/home/user/.claude/sessions/abc.json")
    assert matches_term(s, ".claude/sessions") is True


def test_matches_term_matches_title():
    s = make_session(title="My Important Project")
    assert matches_term(s, "important") is True


def test_matches_term_matches_cwd():
    s = make_session(cwd="/home/user/projects/special-repo")
    assert matches_term(s, "special-repo") is True


def test_matches_term_matches_agent():
    s = make_session(agent="codex")
    assert matches_term(s, "codex") is True


def test_matches_term_case_insensitive():
    s = make_session(title="My Project")
    assert matches_term(s, "MY PROJECT") is True


def test_matches_term_no_match_returns_false():
    s = make_session(id="abc", title="Hello", cwd="/tmp/foo", agent="claude")
    assert matches_term(s, "zzznomatch") is False


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------


def test_truncate_short_text_unchanged():
    assert truncate("hello world", 20) == "hello world"


def test_truncate_long_text_truncated_with_ellipsis():
    result = truncate("a" * 300)
    assert result.endswith("...")
    assert "a" in result


def test_truncate_whitespace_collapsed():
    assert truncate("hello   world", 50) == "hello world"


def test_truncate_internal_newlines_collapsed():
    assert truncate("line one\nline two", 50) == "line one line two"


def test_truncate_exactly_at_width_not_truncated():
    text = "x" * 280
    assert truncate(text, 280) == text


def test_truncate_one_over_width_gets_ellipsis():
    text = "x" * 281
    result = truncate(text, 280)
    assert result.endswith("...")
    assert result.startswith("x")


# ---------------------------------------------------------------------------
# session_to_json
# ---------------------------------------------------------------------------


def test_session_to_json_contains_expected_keys():
    s = make_session()
    result = session_to_json(s)
    expected_keys = {
        "id",
        "agent",
        "title",
        "timestamp",
        "updated_at",
        "cwd",
        "path",
        "repo_score",
        "repo_reason",
    }
    assert set(result.keys()) == expected_keys


def test_session_to_json_path_is_string():
    s = make_session(path="/tmp/test.json")
    result = session_to_json(s)
    assert isinstance(result["path"], str)
    assert result["path"] == "/tmp/test.json"


def test_session_to_json_agent_field_present():
    s = make_session(agent="codex")
    result = session_to_json(s)
    assert result["agent"] == "codex"


# ---------------------------------------------------------------------------
# print_sessions
# ---------------------------------------------------------------------------


def test_print_sessions_limit_zero_shows_all(capsys):
    sessions = [make_session(id=f"s{i}") for i in range(5)]
    print_sessions(sessions, limit=0, json_output=False)
    captured = capsys.readouterr()
    for i in range(5):
        assert f"s{i}" in captured.out


def test_print_sessions_limit_n_shows_only_first_n(capsys):
    sessions = [make_session(id=f"sess{i}", title=f"Title {i}") for i in range(5)]
    print_sessions(sessions, limit=2, json_output=False)
    captured = capsys.readouterr()
    assert "sess0" in captured.out
    assert "sess1" in captured.out
    assert "sess2" not in captured.out


def test_print_sessions_limit_shows_overflow_hint(capsys):
    sessions = [make_session(id=f"s{i}") for i in range(5)]
    print_sessions(sessions, limit=3, json_output=False)
    captured = capsys.readouterr()
    assert "2 more" in captured.out


def test_print_sessions_json_mode_outputs_valid_json(capsys):
    sessions = [make_session(id="abc"), make_session(id="def")]
    print_sessions(sessions, limit=0, json_output=True)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["id"] == "abc"


def test_print_sessions_json_mode_respects_limit(capsys):
    sessions = [make_session(id=f"s{i}") for i in range(4)]
    print_sessions(sessions, limit=2, json_output=True)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed) == 2
