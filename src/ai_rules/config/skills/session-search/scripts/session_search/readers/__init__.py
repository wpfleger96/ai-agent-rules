"""Reader dispatcher: auto-detect installed agents and aggregate sessions."""

from __future__ import annotations

import argparse
import re

from typing import TYPE_CHECKING, Any

from session_search.core import Session, warn

if TYPE_CHECKING:
    pass

# Lazy imports to avoid import errors when an agent's deps are missing.
# Each reader module exports: AGENT_NAME, detect, iter_sessions,
# iter_search_text, display_text


def _load_readers() -> list[Any]:
    from session_search.readers import amp, claude, codex, gemini, goose

    return [codex, claude, gemini, goose, amp]


def iter_all_sessions(args: argparse.Namespace) -> list[Session]:
    requested = getattr(args, "agent", None)
    sessions: list[Session] = []
    for reader in _load_readers():
        if requested and reader.AGENT_NAME != requested:
            continue
        if not reader.detect():
            if requested:
                warn(
                    f"{reader.AGENT_NAME}: data directory not found — "
                    "no sessions available"
                )
            continue
        try:
            sessions.extend(reader.iter_sessions(args))
        except Exception as exc:
            warn(f"skipping {reader.AGENT_NAME}: {exc}")
    return sessions


def search_sessions(
    sessions: list[Session],
    pattern: re.Pattern[str],
    args: argparse.Namespace,
) -> int:
    """Grep across session files/records. Returns match count."""
    from session_search.readers import amp, claude, codex, gemini, goose

    reader_map = {r.AGENT_NAME: r for r in [codex, claude, gemini, goose, amp]}
    total_matches = 0
    for session in sessions:
        reader = reader_map.get(session.agent)
        if reader is None:
            continue
        try:
            if args.max_matches > 0:
                remaining = args.max_matches - total_matches
                if remaining <= 0:
                    break
                session_args_dict = dict(vars(args))
                session_args_dict["max_matches"] = remaining
                session_args = argparse.Namespace(**session_args_dict)
            else:
                session_args = args
            count = reader.search_session(session, pattern, session_args)
        except Exception as exc:
            warn(f"error searching {session.agent} session {session.id}: {exc}")
            continue
        total_matches += count
        if args.max_matches > 0 and total_matches >= args.max_matches:
            break
    return total_matches
