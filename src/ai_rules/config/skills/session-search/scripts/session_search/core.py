"""Shared data model, repo scoring, ranking, and date filtering."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
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
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
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
    except (OSError, subprocess.CalledProcessError):
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


def repo_score(
    session_cwd: str,
    current_cwd: str,
    current_root: str,
    repo_name: str,
) -> tuple[int, str]:
    if not session_cwd:
        return 0, ""
    session_path = str(Path(session_cwd).expanduser())
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
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        if value < since:
            return False
    if args.until:
        until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)
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
