"""Goose (by Block) session reader."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from session_search.core import (
    Session,
    in_date_window,
    repo_context,
    repo_score,
    truncate,
    warn,
)

AGENT_NAME: str = "goose"


def _db_path() -> Path:
    return Path("~/.local/share/goose/sessions/sessions.db").expanduser()


def _legacy_dir() -> Path:
    return Path("~/.config/goose/sessions").expanduser()


def detect() -> bool:
    return _db_path().exists() or any(_legacy_dir().glob("*.jsonl"))


def _conn(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def _ts_from_unix(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=timezone.utc).isoformat()


def iter_sessions(args: argparse.Namespace) -> list[Session]:
    current_cwd = (
        str(Path(args.cwd).expanduser().resolve()) if getattr(args, "cwd", None) else ""
    )
    current_root = ""
    repo_name = getattr(args, "repo", None) or ""
    if current_cwd:
        _, current_root, repo_name = repo_context(current_cwd, repo_name or None)

    db = _db_path()
    if db.exists():
        return _iter_db_sessions(db, args, current_cwd, current_root, repo_name)

    legacy = _legacy_dir()
    if legacy.exists():
        return _iter_legacy_sessions(legacy, args, current_cwd, current_root, repo_name)

    return []


def _iter_db_sessions(
    db: Path,
    args: argparse.Namespace,
    current_cwd: str,
    current_root: str,
    repo_name: str,
) -> list[Session]:
    sessions: list[Session] = []
    try:
        with _conn(db) as con:
            cur = con.execute(
                "SELECT id, name, working_dir, created_at, updated_at FROM sessions"
            )
            for row in cur.fetchall():
                sid, name, working_dir, created_at, updated_at = row
                cwd = working_dir or ""
                title = name or ""
                timestamp = str(created_at or "")
                updated = str(updated_at or "")

                score, reason = repo_score(cwd, current_cwd, current_root, repo_name)

                session = Session(
                    id=str(sid),
                    agent=AGENT_NAME,
                    path=db,
                    timestamp=timestamp,
                    updated_at=updated,
                    title=title,
                    cwd=cwd,
                    repo_score=score,
                    repo_reason=reason,
                )
                if not in_date_window(session, args):
                    continue
                sessions.append(session)
    except sqlite3.Error as exc:
        warn(f"goose: cannot read {db}: {exc}")

    return sessions


def _iter_legacy_sessions(
    legacy_dir: Path,
    args: argparse.Namespace,
    current_cwd: str,
    current_root: str,
    repo_name: str,
) -> list[Session]:
    sessions: list[Session] = []
    for path in sorted(legacy_dir.glob("*.jsonl")):
        sid = path.stem
        cwd = ""
        title = ""
        timestamp = ""
        updated = ""

        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                first_line = fh.readline()
            if first_line:
                try:
                    meta = json.loads(first_line)
                    cwd = str(meta.get("working_dir") or "")
                    title = str(meta.get("description") or "")
                    timestamp = str(meta.get("created_at") or "")
                    updated = str(meta.get("updated_at") or "")
                    if meta.get("id"):
                        sid = str(meta["id"])
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass

        if not timestamp:
            try:
                mtime = path.stat().st_mtime
                timestamp = _ts_from_unix(int(mtime))
            except OSError:
                pass

        score, reason = repo_score(cwd, current_cwd, current_root, repo_name)

        session = Session(
            id=sid,
            agent=AGENT_NAME,
            path=path,
            timestamp=timestamp,
            updated_at=updated,
            title=title,
            cwd=cwd,
            repo_score=score,
            repo_reason=reason,
        )
        if not in_date_window(session, args):
            continue
        sessions.append(session)

    return sessions


def iter_search_text(record: dict[str, Any], raw: str) -> Iterable[str]:
    blocks = record.get("content_json_parsed") or []

    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")

        if btype == "text":
            text = str(block.get("text") or "")
            if text:
                yield text

        elif btype == "toolRequest":
            tool_call = block.get("toolCall") or {}
            ok = tool_call.get("Ok") or {}
            name = str(ok.get("name") or "")
            arguments = ok.get("arguments")
            if name:
                yield name
            if arguments is not None:
                yield json.dumps(arguments, ensure_ascii=False)

        elif btype == "toolResponse":
            tool_result = block.get("toolResult") or {}
            items = tool_result.get("Ok") or []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        text = str(item.get("text") or "")
                        if text:
                            yield text

        elif btype == "thinking":
            thinking = str(block.get("thinking") or "")
            if thinking:
                yield thinking


def display_text(record: dict[str, Any], raw: str) -> str:
    role = record.get("role", "")
    blocks = record.get("content_json_parsed") or []

    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")

        if btype == "text":
            text = str(block.get("text") or "")
            if text:
                parts.append(
                    json.dumps({"role": role, "text": text}, ensure_ascii=False)
                )

        elif btype == "toolRequest":
            tool_call = block.get("toolCall") or {}
            ok = tool_call.get("Ok") or {}
            name = str(ok.get("name") or "")
            args = ok.get("arguments")
            parts.append(
                json.dumps(
                    {"role": role, "tool": name, "args": args}, ensure_ascii=False
                )
            )

        elif btype == "toolResponse":
            tool_result = block.get("toolResult") or {}
            items = tool_result.get("Ok") or []
            texts = []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        text = str(item.get("text") or "")
                        if text:
                            texts.append(text)
            parts.append(
                json.dumps(
                    {"role": role, "tool_result": " ".join(texts)}, ensure_ascii=False
                )
            )

    if parts:
        return " | ".join(parts)
    return raw


def _search_db_session(
    session: Session,
    pattern: re.Pattern[str],
    args: argparse.Namespace,
) -> int:
    max_matches = getattr(args, "max_matches", 0)
    width = getattr(args, "width", 280)
    header_printed = False
    matches = 0

    try:
        with _conn(session.path) as con:
            cur = con.execute(
                "SELECT role, content_json, created_timestamp"
                " FROM messages"
                " WHERE session_id = ?"
                " ORDER BY created_timestamp",
                (session.id,),
            )
            for row in cur.fetchall():
                role, content_json_raw, created_ts = row
                try:
                    blocks = json.loads(content_json_raw)
                except (json.JSONDecodeError, TypeError):
                    blocks = []

                record = {"role": role, "content_json_parsed": blocks}
                searchable = " ".join(iter_search_text(record, content_json_raw or ""))

                if not pattern.search(searchable):
                    continue

                if not header_printed:
                    label = f" [{session.repo_reason}]" if session.repo_reason else ""
                    title_part = f" - {session.title}" if session.title else ""
                    print(f"\n=== [{AGENT_NAME}] {session.id}{label}{title_part} ===")
                    print(f"    {session.path}")
                    header_printed = True

                rendered = display_text(record, content_json_raw or "")
                print(truncate(rendered, width))
                matches += 1

                if max_matches > 0 and matches >= max_matches:
                    return matches

    except sqlite3.Error as exc:
        warn(f"goose: cannot read session {session.id} from {session.path}: {exc}")

    return matches


def _search_legacy_session(
    session: Session,
    pattern: re.Pattern[str],
    args: argparse.Namespace,
) -> int:
    max_matches = getattr(args, "max_matches", 0)
    width = getattr(args, "width", 280)
    header_printed = False
    matches = 0

    try:
        with session.path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                raw = raw_line.rstrip("\n")
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if not isinstance(entry, dict):
                    continue

                role = str(entry.get("role") or "")
                content = entry.get("content")
                if not isinstance(content, list):
                    continue

                record = {"role": role, "content_json_parsed": content}
                searchable = " ".join(iter_search_text(record, raw))

                if not pattern.search(searchable):
                    continue

                if not header_printed:
                    label = f" [{session.repo_reason}]" if session.repo_reason else ""
                    title_part = f" - {session.title}" if session.title else ""
                    print(f"\n=== [{AGENT_NAME}] {session.id}{label}{title_part} ===")
                    print(f"    {session.path}")
                    header_printed = True

                rendered = display_text(record, raw)
                print(truncate(rendered, width))
                matches += 1

                if max_matches > 0 and matches >= max_matches:
                    return matches

    except OSError as exc:
        warn(f"goose: cannot read {session.path}: {exc}")

    return matches


def search_session(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
) -> int:
    if session.path == _db_path():
        return _search_db_session(session, pattern, args)
    return _search_legacy_session(session, pattern, args)
