"""Buzz (Nostr relay) session reader.

Backend is an HTTP relay reached via the `buzz` CLI rather than a local store,
so it is the same shape as goose's SQLite reader: one channel = one session.

Relay facts that shape this reader (all live-verified):
- `messages search` is GLOBAL full-text and hard-caps at 100 results. When the
  result count hits the cap the answer is provably incomplete, so grep falls
  back to a bounded per-channel sweep rather than reporting a partial set.
- `channels list --limit N` under-returns (limit applied before visibility
  filtering), so `iter_sessions` enumerates with no limit and caps locally.
- `created_at` is a unix-epoch int on both channels and events; it must pass
  through `_ts_from_unix` before any `core` time function or the session sorts
  to `datetime.min` and `--since`/`--until` silently drop it.
- There is no working directory, so every Buzz session scores `repo_score=0`
  and ranks purely by recency.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from session_search.core import (
    Session,
    SessionMatchPrinter,
    in_date_window,
    warn,
)

AGENT_NAME: str = "buzz"

# Server ceiling on `messages search`; count == cap means the result set is
# provably truncated, which triggers the bounded per-channel sweep.
_SEARCH_CAP = 100


# Per-process memo of the single global search, keyed by seed. Populated lazily
# inside the grep flow (never in iter_sessions), and read by every candidate
# channel in the same run. Value is channel UUID -> events, or None when the
# search saturated (provably incomplete -> caller must fall back to the sweep).
_search_cache: dict[str, dict[str, list[dict[str, Any]]] | None] = {}

# Guards the one-time "broad pattern; swept top N channels" stderr notice so a
# multi-channel sweep warns once per run, not once per channel.
_sweep_notified = False


def detect() -> bool:
    return bool(os.environ.get("BUZZ_PRIVATE_KEY") and os.environ.get("BUZZ_RELAY_URL"))


def _ts_from_unix(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=UTC).isoformat()


def _run_buzz(*args: str) -> list[dict[str, Any]]:
    """Run a read-only `buzz` command and return its parsed JSON array.

    Non-zero exit or unparseable output -> warn + empty, mirroring goose's
    `sqlite3.Error` path: an unreachable relay yields no sessions, not a crash.
    """
    try:
        result = subprocess.run(
            ["buzz", "--format", "json", *args],
            text=True,
            capture_output=True,
            check=True,
        )
    except OSError as exc:
        warn(f"buzz: cannot run CLI: {exc}")
        return []
    except subprocess.CalledProcessError as exc:
        warn(f"buzz: {' '.join(args)} failed: {exc.stderr.strip() or exc}")
        return []

    try:
        parsed = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        warn(f"buzz: malformed JSON from {' '.join(args)}: {exc}")
        return []
    return parsed if isinstance(parsed, list) else []


def iter_sessions(args: argparse.Namespace) -> list[Session]:
    """One Session per channel. PURE: no search call (so list/find stay cheap)."""
    sessions: list[Session] = []
    for channel in _run_buzz("channels", "list"):
        cid = str(channel.get("channel_id") or "")
        if not cid:
            continue
        timestamp = _ts_from_unix(int(channel.get("created_at") or 0))
        session = Session(
            id=cid,
            agent=AGENT_NAME,
            path=Path(f"buzz:{cid}"),
            timestamp=timestamp,
            updated_at=timestamp,
            title=str(channel.get("name") or ""),
            cwd="",
            repo_score=0,
            repo_reason="",
        )
        if not in_date_window(session, args):
            continue
        sessions.append(session)
    return sessions


def _channel_of(event: dict[str, Any]) -> str:
    for tag in event.get("tags") or []:
        if isinstance(tag, list) and len(tag) >= 2 and tag[0] == "h":
            return str(tag[1])
    return ""


def iter_search_text(record: dict[str, Any], raw: str) -> Iterable[str]:
    content = str(record.get("content") or "")
    if content:
        yield content


def display_text(record: dict[str, Any], raw: str) -> str:
    return json.dumps(
        {
            "pubkey": record.get("pubkey", ""),
            "time": _ts_from_unix(int(record.get("created_at") or 0)),
            "content": str(record.get("content") or ""),
        },
        ensure_ascii=False,
    )


_WORD_RE = re.compile(r"\w")
_OPTIONAL_QUANTIFIERS = frozenset("?*")


def _brace_min_zero(inner: str) -> bool:
    """True when a `{...}` quantifier permits zero repetitions (min == 0).

    `{0}`, `{0,}`, `{0,n}`, and `{,n}` (Python reads an omitted minimum as 0) make
    the preceding char optional, exactly like `?`/`*`. A non-numeric minimum
    (e.g. a literal `{foo}`) is not zero — keep the char; the brace run is already
    excluded from the seed, so the conservative outcome stands.
    """
    minimum = inner.split(",", 1)[0].strip()
    return minimum in ("", "0")


def _literal_seed(pattern: str) -> str:
    """Longest substring the regex requires verbatim, for a server pre-filter.

    Walks the pattern collecting maximal runs of literal word-chars, skipping
    escape sequences (`\\d`), character classes (`[...]`), and quantifier braces
    (`{4}`) — their inner chars are not literal text. A char that is immediately
    optional/repeatable (`?`, `*`) is dropped from the run since a match need not
    contain it. Conservative: when no safe literal exists it returns "" and the
    caller sweeps, so the seed never over-claims.
    """
    runs: list[str] = []
    current: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2  # escape: the escaped char is not a literal match
            runs.append("".join(current))
            current = []
            continue
        if ch == "[":
            end = pattern.find("]", i + 1)
            i = n if end == -1 else end + 1
            runs.append("".join(current))
            current = []
            continue
        if ch == "{":
            end = pattern.find("}", i + 1)
            if current and _brace_min_zero(pattern[i + 1 : end] if end != -1 else ""):
                current.pop()  # {0}, {0,n}, {0,} make the preceding char optional
            i = n if end == -1 else end + 1
            runs.append("".join(current))
            current = []
            continue
        if ch in _OPTIONAL_QUANTIFIERS:
            if current:  # the char it applies to is optional — drop it
                current.pop()
            runs.append("".join(current))
            current = []
            i += 1
            continue
        if _WORD_RE.match(ch):
            current.append(ch)
        else:  # any other metacharacter ends the current run
            runs.append("".join(current))
            current = []
        i += 1
    runs.append("".join(current))
    return max(runs, key=len)


def _grouped_search(seed: str) -> dict[str, list[dict[str, Any]]] | None:
    """Single global search grouped by channel UUID, memoized per seed.

    Returns None when the result set is saturated (count == cap) and therefore
    provably incomplete — the caller must fall back to the bounded sweep.
    """
    if seed not in _search_cache:
        events = _run_buzz(
            "messages", "search", "--query", seed, "--limit", str(_SEARCH_CAP)
        )
        if len(events) >= _SEARCH_CAP:
            _search_cache[seed] = None
        else:
            groups: dict[str, list[dict[str, Any]]] = {}
            for event in events:
                cid = _channel_of(event)
                if cid:
                    groups.setdefault(cid, []).append(event)
            _search_cache[seed] = groups
    return _search_cache[seed]


def _print_matches(
    session: Session,
    events: Iterable[dict[str, Any]],
    pattern: re.Pattern[str],
    args: argparse.Namespace,
) -> int:
    printer = SessionMatchPrinter(session, args)
    for event in events:
        if pattern.search(str(event.get("content") or "")):
            if not printer.emit(display_text(event, "")):
                break
    return printer.matches


def _sweep_channel(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
) -> int:
    """Fetch one channel's messages and regex locally (the bounded fallback)."""
    global _sweep_notified
    if not _sweep_notified:
        limit = getattr(args, "limit_sessions", 0)
        scope = f"top {limit}" if limit and limit > 0 else "all"
        warn(
            f"buzz: broad pattern — swept {scope} channels by recency; "
            "narrow the pattern for a complete global search"
        )
        _sweep_notified = True
    events = _run_buzz("messages", "get", "--channel", session.id, "--kinds", "9")
    return _print_matches(session, events, pattern, args)


def rank_candidates(sessions: list[Session], args: argparse.Namespace) -> list[Session]:
    """Float channels that match the grep seed to the front, densest first.

    `cmd_grep` truncates candidates by recency BEFORE searching, so a relevant
    but older channel is dropped from the candidate set and never searched. The
    same global search the grep flow already runs (and memoizes) knows the exact
    set of matching channels across the whole relay, so reorder by descending
    match-event count here — before the truncation slice — and the dense match
    survives the cut. Unmatched channels trail in their incoming (recency) order.

    Returns the input unchanged when ranking cannot help or must not run:
    `--id` (scoped to 1-2 channels; firing the global search would regress the
    scoping contract), no literal seed, or a saturated search (None) — the
    bounded sweep owns that case and its stderr notice stays intact.
    """
    if getattr(args, "id", None):
        return sessions
    seed = _literal_seed(args.pattern)
    groups = _grouped_search(seed) if seed else None
    if not groups:
        return sessions
    # Stable: ties keep incoming recency order; unmatched (count 0) trail.
    return sorted(sessions, key=lambda s: len(groups.get(s.id, [])), reverse=True)


def search_session(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
) -> int:
    # --id scoping: the dispatcher has already filtered candidates to channels
    # whose UUID contains the fragment, so fetch this channel directly.
    if getattr(args, "id", None):
        events = _run_buzz("messages", "get", "--channel", session.id, "--kinds", "9")
        return _print_matches(session, events, pattern, args)

    seed = _literal_seed(args.pattern)
    if seed:
        groups = _grouped_search(seed)
        if groups is not None:
            return _print_matches(session, groups.get(session.id, []), pattern, args)

    # No literal seed, or the global search saturated: bounded per-channel sweep.
    return _sweep_channel(session, pattern, args)
