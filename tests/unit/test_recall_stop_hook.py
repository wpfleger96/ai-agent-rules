"""Tests for the recall Stop hook safety net (recall_stop.py)."""

# Import the hook module directly since it's a standalone script
import importlib.util
import json

from pathlib import Path

import pytest

_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "ai_rules"
    / "config"
    / "claude"
    / "hooks"
    / "recall_stop.py"
)
_spec = importlib.util.spec_from_file_location("recall_stop", _HOOK_PATH)
assert _spec and _spec.loader
recall_stop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recall_stop)


def _write_transcript(path: Path, messages: list[dict]) -> None:
    """Write a list of message dicts as JSONL transcript."""
    with path.open("w") as f:
        for msg in messages:
            f.write(json.dumps({"message": msg}) + "\n")


def _user_msg(text: str) -> dict:
    return {"role": "user", "content": text}


def _user_msg_blocks(texts: list[str]) -> dict:
    return {
        "role": "user",
        "content": [{"type": "text", "text": t} for t in texts],
    }


def _assistant_msg(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _tool_use_msg(tool_name: str) -> dict:
    return {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "name": tool_name, "input": {}},
        ],
    }


# ---------------------------------------------------------------------------
# parse_transcript
# ---------------------------------------------------------------------------


class TestParseTranscript:
    def test_parses_wrapped_messages(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        _write_transcript(path, [_user_msg("hello")])
        msgs = recall_stop.parse_transcript(str(path))
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        msgs = recall_stop.parse_transcript(str(tmp_path / "nope.jsonl"))
        assert msgs == []

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        path.write_text('not json\n{"message": {"role": "user", "content": "hi"}}\n')
        msgs = recall_stop.parse_transcript(str(path))
        assert len(msgs) == 1

    def test_skips_non_dict_json_values(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        path.write_text('"just a string"\n42\n[1,2,3]\n')
        msgs = recall_stop.parse_transcript(str(path))
        assert msgs == []

    def test_handles_empty_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        path.write_text('\n\n{"message": {"role": "user", "content": "hi"}}\n\n')
        msgs = recall_stop.parse_transcript(str(path))
        assert len(msgs) == 1


# ---------------------------------------------------------------------------
# has_recall_mcp
# ---------------------------------------------------------------------------


class TestHasRecallMcp:
    def test_detects_recall_tool_use(self) -> None:
        msgs = [_tool_use_msg("mcp__recall__search_notes")]
        assert recall_stop.has_recall_mcp(msgs) is True

    def test_detects_recall_write(self) -> None:
        msgs = [_tool_use_msg("mcp__recall__write_note")]
        assert recall_stop.has_recall_mcp(msgs) is True

    def test_no_recall_tools(self) -> None:
        msgs = [_tool_use_msg("Bash"), _user_msg("hello")]
        assert recall_stop.has_recall_mcp(msgs) is False

    def test_empty_messages(self) -> None:
        assert recall_stop.has_recall_mcp([]) is False


# ---------------------------------------------------------------------------
# has_unaddressed_signal — persist patterns
# ---------------------------------------------------------------------------


class TestPersistSignals:
    def test_remember_this_triggers(self) -> None:
        msgs = [_user_msg("hey remember this for later")]
        result = recall_stop.has_unaddressed_signal(msgs)
        assert result is not None
        assert "persist" in result.lower()

    def test_save_this_triggers(self) -> None:
        msgs = [_user_msg("save this to the knowledge base")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_add_to_kb_triggers(self) -> None:
        msgs = [_user_msg("add this to the kb")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_write_to_recall_triggers(self) -> None:
        msgs = [_user_msg("write this to recall")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_dont_forget_triggers(self) -> None:
        msgs = [_user_msg("don't forget this")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_no_signal_returns_none(self) -> None:
        msgs = [_user_msg("how does this function work?")]
        assert recall_stop.has_unaddressed_signal(msgs) is None


# ---------------------------------------------------------------------------
# has_unaddressed_signal — correction patterns
# ---------------------------------------------------------------------------


class TestCorrectionSignals:
    def test_youre_wrong_triggers(self) -> None:
        msgs = [_user_msg("you're wrong about that")]
        result = recall_stop.has_unaddressed_signal(msgs)
        assert result is not None
        assert "correction" in result.lower()

    def test_thats_not_right_triggers(self) -> None:
        msgs = [_user_msg("that's not right")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_you_got_that_wrong_triggers(self) -> None:
        msgs = [_user_msg("you got that wrong")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_thats_incorrect_triggers(self) -> None:
        msgs = [_user_msg("no, that's incorrect")]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_no_false_positive_on_affirmation(self) -> None:
        """'no, that's exactly what I wanted' should NOT trigger."""
        msgs = [_user_msg("no, that's exactly what I wanted")]
        assert recall_stop.has_unaddressed_signal(msgs) is None

    def test_no_false_positive_on_third_party(self) -> None:
        """Corrections about external systems should NOT trigger."""
        msgs = [_user_msg("the API response is incorrect sometimes")]
        assert recall_stop.has_unaddressed_signal(msgs) is None

    def test_no_false_positive_on_actually_positive(self) -> None:
        """'actually it is working great' should NOT trigger."""
        msgs = [_user_msg("actually it is working great now")]
        assert recall_stop.has_unaddressed_signal(msgs) is None


# ---------------------------------------------------------------------------
# has_unaddressed_signal — temporal ordering
# ---------------------------------------------------------------------------


class TestTemporalOrdering:
    def test_write_after_signal_clears_it(self) -> None:
        """A recall write AFTER a persist signal means it was addressed."""
        msgs = [
            _user_msg("remember this pattern"),
            _tool_use_msg("mcp__recall__write_note"),
        ]
        assert recall_stop.has_unaddressed_signal(msgs) is None

    def test_write_before_signal_does_not_clear(self) -> None:
        """A recall write BEFORE a persist signal doesn't satisfy it."""
        msgs = [
            _tool_use_msg("mcp__recall__write_note"),
            _user_msg("also remember this other thing"),
        ]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_multiple_signals_last_one_addressed(self) -> None:
        msgs = [
            _user_msg("remember this"),
            _user_msg("save this too"),
            _tool_use_msg("mcp__recall__write_note"),
        ]
        assert recall_stop.has_unaddressed_signal(msgs) is None

    def test_multiple_signals_first_addressed_second_not(self) -> None:
        msgs = [
            _user_msg("remember this"),
            _tool_use_msg("mcp__recall__write_note"),
            _user_msg("also save this other thing"),
        ]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_edit_note_also_clears(self) -> None:
        msgs = [
            _user_msg("you're wrong about that"),
            _tool_use_msg("mcp__recall__edit_note"),
        ]
        assert recall_stop.has_unaddressed_signal(msgs) is None


# ---------------------------------------------------------------------------
# has_unaddressed_signal — block-delimited content
# ---------------------------------------------------------------------------


class TestBlockContent:
    def test_signal_in_content_blocks(self) -> None:
        msgs = [_user_msg_blocks(["some context", "remember this"])]
        assert recall_stop.has_unaddressed_signal(msgs) is not None

    def test_no_signal_in_content_blocks(self) -> None:
        msgs = [_user_msg_blocks(["just a question", "about code"])]
        assert recall_stop.has_unaddressed_signal(msgs) is None


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMain:
    def test_stop_hook_active_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "sys.stdin",
            type(
                "", (), {"read": lambda self: json.dumps({"stop_hook_active": True})}
            )(),
        )
        with pytest.raises(SystemExit) as exc:
            recall_stop.main()
        assert exc.value.code == 0

    def test_missing_transcript_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "sys.stdin", type("", (), {"read": lambda self: json.dumps({})})()
        )
        with pytest.raises(SystemExit) as exc:
            recall_stop.main()
        assert exc.value.code == 0

    def test_no_recall_mcp_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "t.jsonl"
        _write_transcript(transcript, [_user_msg("remember this")])
        monkeypatch.setattr(
            "sys.stdin",
            type(
                "",
                (),
                {"read": lambda self: json.dumps({"transcript_path": str(transcript)})},
            )(),
        )
        with pytest.raises(SystemExit) as exc:
            recall_stop.main()
        assert exc.value.code == 0

    def test_signal_with_recall_mcp_blocks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                _tool_use_msg("mcp__recall__search_notes"),
                _user_msg("remember this pattern"),
            ],
        )
        monkeypatch.setattr(
            "sys.stdin",
            type(
                "",
                (),
                {"read": lambda self: json.dumps({"transcript_path": str(transcript)})},
            )(),
        )
        with pytest.raises(SystemExit) as exc:
            recall_stop.main()
        assert exc.value.code == 2

    def test_no_signal_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "t.jsonl"
        _write_transcript(
            transcript,
            [
                _tool_use_msg("mcp__recall__search_notes"),
                _user_msg("how does this work?"),
            ],
        )
        monkeypatch.setattr(
            "sys.stdin",
            type(
                "",
                (),
                {"read": lambda self: json.dumps({"transcript_path": str(transcript)})},
            )(),
        )
        with pytest.raises(SystemExit) as exc:
            recall_stop.main()
        assert exc.value.code == 0

    def test_malformed_stdin_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "sys.stdin", type("", (), {"read": lambda self: "not json"})()
        )
        with pytest.raises(SystemExit) as exc:
            recall_stop.main()
        assert exc.value.code == 0
