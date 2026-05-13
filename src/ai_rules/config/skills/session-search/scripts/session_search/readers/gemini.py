"""Google Gemini CLI session reader."""

from __future__ import annotations

import argparse
import json
import re

from collections.abc import Iterable
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

AGENT_NAME: str = "gemini"


def _gemini_tmp() -> Path:
    return Path("~/.gemini/tmp").expanduser()


def _projects_json() -> Path:
    return Path("~/.gemini/projects.json").expanduser()


def detect() -> bool:
    return _gemini_tmp().exists()


def _load_slug_map() -> dict[str, str]:
    projects_path = _projects_json()
    if not projects_path.exists():
        return {}
    try:
        with projects_path.open("r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    projects = data.get("projects") if isinstance(data, dict) else None
    if not isinstance(projects, dict):
        return {}
    return {
        v: k for k, v in projects.items() if isinstance(k, str) and isinstance(v, str)
    }


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = str(part.get("text") or "")
                if text:
                    parts.append(text)
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    if isinstance(content, dict):
        text = str(content.get("text") or "")
        return text
    return ""


def _read_jsonl_meta(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {"session_id": "", "start_time": "", "last_updated": ""}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            first_line = fh.readline()
    except OSError:
        return meta
    if not first_line.strip():
        return meta
    try:
        record = json.loads(first_line)
    except json.JSONDecodeError:
        return meta
    if not isinstance(record, dict):
        return meta
    meta["session_id"] = str(record.get("sessionId") or record.get("session_id") or "")
    meta["start_time"] = str(record.get("startTime") or record.get("start_time") or "")
    meta["last_updated"] = str(
        record.get("lastUpdated") or record.get("last_updated") or ""
    )
    return meta


def iter_sessions(args: argparse.Namespace) -> list[Session]:
    tmp_dir = _gemini_tmp()
    slug_map = _load_slug_map()

    current_cwd = (
        str(Path(args.cwd).expanduser().resolve()) if getattr(args, "cwd", None) else ""
    )
    current_root = ""
    repo_name = getattr(args, "repo", None) or ""
    if current_cwd:
        _, current_root, repo_name = repo_context(current_cwd, repo_name or None)

    sessions: list[Session] = []

    for slug_dir in tmp_dir.iterdir():
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        cwd = slug_map.get(slug, "")

        chats_dir = slug_dir / "chats"
        if not chats_dir.is_dir():
            continue

        for path in chats_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name

            if name.startswith("session-") and name.endswith(".jsonl"):
                meta = _read_jsonl_meta(path)
                session_id = meta["session_id"] or path.stem
                timestamp = meta["start_time"]
                updated_at = meta["last_updated"]
            elif name.startswith("session-") and name.endswith(".json"):
                session_id = path.stem
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                from datetime import datetime, timezone

                dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                timestamp = dt.isoformat()
                updated_at = ""
            else:
                continue

            score, reason = repo_score(cwd, current_cwd, current_root, repo_name)

            session = Session(
                id=session_id,
                agent=AGENT_NAME,
                path=path,
                timestamp=timestamp,
                updated_at=updated_at,
                title=slug,
                cwd=cwd,
                repo_score=score,
                repo_reason=reason,
            )
            if not in_date_window(session, args):
                continue
            sessions.append(session)

    return sessions


def iter_search_text(record: dict[str, Any], raw: str) -> Iterable[str]:
    record_type = record.get("type")

    if record_type == "user":
        text = _extract_text_from_content(record.get("content"))
        if text:
            yield text

    elif record_type == "gemini":
        text = _extract_text_from_content(record.get("content"))
        if text:
            yield text
        for thought in record.get("thoughts") or []:
            if isinstance(thought, dict):
                t = str(thought.get("text") or "")
                if t:
                    yield t
            elif isinstance(thought, str) and thought:
                yield thought
        for tool_call in record.get("toolCalls") or []:
            if not isinstance(tool_call, dict):
                continue
            name = str(tool_call.get("name") or "")
            if name:
                yield name
            args_val = tool_call.get("args")
            if args_val is not None:
                if isinstance(args_val, str) and args_val:
                    yield args_val
                elif isinstance(args_val, dict):
                    try:
                        yield json.dumps(args_val, ensure_ascii=False)
                    except (TypeError, ValueError):
                        pass


def display_text(record: dict[str, Any], raw: str) -> str:
    record_type = record.get("type")

    if record_type == "user":
        text = _extract_text_from_content(record.get("content"))
        return json.dumps({"role": "user", "text": text}, ensure_ascii=False)

    if record_type == "gemini":
        text = _extract_text_from_content(record.get("content"))
        tool_calls = record.get("toolCalls")
        if tool_calls:
            tool_info = [
                {"name": tc.get("name"), "args": tc.get("args")}
                for tc in tool_calls
                if isinstance(tc, dict)
            ]
            return json.dumps(
                {"role": "gemini", "text": text, "toolCalls": tool_info},
                ensure_ascii=False,
            )
        return json.dumps({"role": "gemini", "text": text}, ensure_ascii=False)

    return raw


def _search_jsonl(
    session: Session,
    pattern: re.Pattern[str],
    args: argparse.Namespace,
) -> int:
    max_matches = getattr(args, "max_matches", 0)
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
                        label = (
                            f" [{session.repo_reason}]" if session.repo_reason else ""
                        )
                        title_part = f" - {session.title}" if session.title else ""
                        print(
                            f"\n=== [{AGENT_NAME}] {session.id}{label}{title_part} ==="
                        )
                        print(f"    {session.path}")
                        header_printed = True
                    rendered = display_text(record, raw)
                    width = getattr(args, "width", 280)
                    print(truncate(rendered, width))
                    matches += 1
                    if max_matches > 0 and matches >= max_matches:
                        return matches
                    break
    except OSError as exc:
        warn(f"cannot read {session.path}: {exc}")

    return matches


def _search_legacy_json(
    session: Session,
    pattern: re.Pattern[str],
    args: argparse.Namespace,
) -> int:
    max_matches = getattr(args, "max_matches", 0)
    header_printed = False
    matches = 0

    try:
        with session.path.open("r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"cannot read {session.path}: {exc}")
        return 0

    history = data.get("history") if isinstance(data, dict) else None
    if not isinstance(history, list):
        return 0

    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "")
        parts = entry.get("parts") or []
        texts: list[str] = []
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict):
                    t = str(part.get("text") or "")
                    if t:
                        texts.append(t)
                elif isinstance(part, str) and part:
                    texts.append(part)
        combined = "\n".join(texts)

        if not combined or not pattern.search(combined):
            continue

        if not header_printed:
            label = f" [{session.repo_reason}]" if session.repo_reason else ""
            title_part = f" - {session.title}" if session.title else ""
            print(f"\n=== [{AGENT_NAME}] {session.id}{label}{title_part} ===")
            print(f"    {session.path}")
            header_printed = True

        width = getattr(args, "width", 280)
        rendered = json.dumps({"role": role, "text": combined}, ensure_ascii=False)
        print(truncate(rendered, width))
        matches += 1
        if max_matches > 0 and matches >= max_matches:
            return matches

    return matches


def search_session(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
) -> int:
    if session.path.suffix == ".jsonl":
        return _search_jsonl(session, pattern, args)
    return _search_legacy_json(session, pattern, args)
