"""Shared data model, repo scoring, ranking, and date filtering."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Session:
    id: str
    agent: str
    path: Path
    timestamp: str
    updated_at: str
    title: str
    cwd: str
    repo_score: int
    repo_reason: str

    @property
    def sort_time(self) -> str:
        return self.updated_at or self.timestamp


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def date_key(value: str) -> datetime:
    parsed = parse_iso(value)
    if parsed is None:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


# ---------------------------------------------------------------------------
# Repo scoring
# ---------------------------------------------------------------------------


def git_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except OSError, subprocess.CalledProcessError:
        return None
    root = result.stdout.strip()
    return Path(root).resolve() if root else None


def repo_name_from_path(path_text: str) -> str:
    if not path_text:
        return ""
    return Path(path_text).name


def repo_context(cwd_text: str, explicit_repo: str | None) -> tuple[str, str, str]:
    cwd = Path(cwd_text).expanduser().resolve()
    root = git_root(cwd)
    root_text = str(root) if root else str(cwd)
    repo_name = explicit_repo or repo_name_from_path(root_text)
    return str(cwd), root_text, repo_name


def current_repo_context(args: argparse.Namespace) -> tuple[str, str, str]:
    """Resolve (current_cwd, current_root, repo_name) from --cwd/--repo args."""
    current_cwd = (
        str(Path(args.cwd).expanduser().resolve()) if getattr(args, "cwd", None) else ""
    )
    current_root = ""
    repo_name = getattr(args, "repo", None) or ""
    if current_cwd:
        _, current_root, repo_name = repo_context(current_cwd, repo_name or None)
    return current_cwd, current_root, repo_name


def repo_score(
    session_cwd: str,
    current_cwd: str,
    current_root: str,
    repo_name: str,
) -> tuple[int, str]:
    if not session_cwd:
        return 0, ""
    session_path = Path(session_cwd).expanduser().as_posix()
    if session_path == current_cwd or session_path == current_root:
        return 3, "exact-cwd"
    if current_root and session_path.startswith(current_root.rstrip("/") + "/"):
        return 3, "same-root"
    session_repo = repo_name_from_path(session_path)
    if repo_name and session_repo == repo_name:
        return 2, "same-repo"
    if repo_name and f"/{repo_name}" in session_path:
        return 1, "repo-name-in-path"
    return 0, ""


# ---------------------------------------------------------------------------
# Filtering and sorting
# ---------------------------------------------------------------------------


def in_date_window(session: Session, args: argparse.Namespace) -> bool:
    value = date_key(session.sort_time)
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
        if value < since:
            return False
    if args.until:
        until = datetime.fromisoformat(args.until).replace(tzinfo=UTC)
        if value.date() > until.date():
            return False
    return True


def sorted_sessions(sessions: Iterable[Session], oldest: bool) -> list[Session]:
    # Two-pass stable sort: date first (direction from oldest), then repo_score
    # descending. This keeps high-relevance sessions at the top regardless of
    # whether --oldest is set.
    lst = list(sessions)
    lst.sort(key=lambda s: (date_key(s.sort_time), s.title, s.id), reverse=not oldest)
    lst.sort(key=lambda s: s.repo_score, reverse=True)
    return lst


def matches_term(session: Session, term: str) -> bool:
    needle = term.lower()
    haystacks = [
        session.id,
        session.path.name,
        str(session.path),
        session.title,
        session.cwd,
        session.agent,
    ]
    return any(needle in value.lower() for value in haystacks if value)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def truncate(text: str, width: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= width:
        return compact
    return compact[: width - 1] + "..."


def session_to_json(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "agent": session.agent,
        "title": session.title,
        "timestamp": session.timestamp,
        "updated_at": session.updated_at,
        "cwd": session.cwd,
        "path": str(session.path),
        "repo_score": session.repo_score,
        "repo_reason": session.repo_reason,
    }


def print_sessions(sessions: list[Session], limit: int, json_output: bool) -> None:
    shown = sessions if limit <= 0 else sessions[:limit]
    if json_output:
        print(json.dumps([session_to_json(s) for s in shown], indent=2))
        return
    for i, session in enumerate(shown, 1):
        label = f" [{session.repo_reason}]" if session.repo_reason else ""
        agent_tag = f"[{session.agent}]"
        title_part = f" - {session.title}" if session.title else ""
        print(f"{i}. {agent_tag} {session.id}{label}{title_part}")
        print(f"   time: {session.sort_time or session.timestamp}")
        print(f"   cwd:  {session.cwd or '(unknown)'}")
        print(f"   path: {session.path}")
    if len(sessions) > len(shown):
        print(
            f"... {len(sessions) - len(shown)} more matches; "
            "rerun with --limit 0 for all."
        )


def warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def print_session_header(session: Session) -> None:
    """Print the standard once-per-session match header."""
    label = f" [{session.repo_reason}]" if session.repo_reason else ""
    title_part = f" - {session.title}" if session.title else ""
    print(f"\n=== [{session.agent}] {session.id}{label}{title_part} ===")
    print(f"    {session.path}")


def search_jsonl_session(
    session: Session,
    pattern: re.Pattern[str],
    args: argparse.Namespace,
    iter_search_text: Callable[[dict[str, Any], str], Iterable[str]],
    display_text: Callable[[dict[str, Any], str], str],
) -> int:
    """Shared JSONL search loop: print each record once on its first match."""
    max_matches = getattr(args, "max_matches", 0)
    width = getattr(args, "width", 280)
    header_printed = False
    matches = 0

    try:
        with session.path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                raw = raw_line.rstrip("\n")
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    record = {}

                for text in iter_search_text(record, raw):
                    if not pattern.search(text):
                        continue
                    if not header_printed:
                        print_session_header(session)
                        header_printed = True
                    print(truncate(display_text(record, raw), width))
                    matches += 1
                    if max_matches > 0 and matches >= max_matches:
                        return matches
                    break
    except OSError as exc:
        warn(f"cannot read {session.path}: {exc}")

    return matches
