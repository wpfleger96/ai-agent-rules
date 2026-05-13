"""Claude Code (Anthropic) session reader."""

from __future__ import annotations

import argparse
import json
import os
import re

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

AGENT_NAME: str = "claude"

_DEFAULT_PASS2_LIMIT = 50


def _config_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return Path("~/.claude").expanduser()


def detect() -> bool:
    return (_config_dir() / "projects").is_dir()


def _projects_dir() -> Path:
    return _config_dir() / "projects"


def _dir_contains_repo(dir_name: str, repo_name: str) -> bool:
    return repo_name.lower() in dir_name.lower()


def _parse_tail_records(tail_bytes: bytes) -> dict[str, Any]:
    text = tail_bytes.decode("utf-8", errors="replace")
    result: dict[str, Any] = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        rtype = record.get("type")
        if rtype == "custom-title" and "customTitle" not in result:
            title = record.get("customTitle") or record.get("title")
            if title:
                result["customTitle"] = title
        elif rtype == "ai-title" and "aiTitle" not in result:
            title = record.get("aiTitle") or record.get("title")
            if title:
                result["aiTitle"] = title
    return result


def _read_head_record(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record: dict[str, Any] = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(record, dict):
                    continue
                rtype = record.get("type")
                if rtype in ("user", "assistant") and record.get("cwd"):
                    return record
    except OSError:
        pass
    return {}


def iter_sessions(args: argparse.Namespace) -> list[Session]:
    projects = _projects_dir()
    requested_agent = getattr(args, "agent", None)
    if requested_agent and requested_agent != AGENT_NAME:
        return []

    current_cwd_text = getattr(args, "cwd", None) or os.getcwd()
    current_cwd, current_root, repo_name = repo_context(
        current_cwd_text, getattr(args, "repo", None)
    )

    # Pass 1: stat-only scan
    candidates: list[
        tuple[int, float, Path, str]
    ] = []  # (hint_score, mtime, path, dir_name)
    try:
        project_entries = list(projects.iterdir())
    except OSError as exc:
        warn(f"cannot read {projects}: {exc}")
        return []

    for project_dir in project_entries:
        if not project_dir.is_dir():
            continue
        dir_name = project_dir.name
        hint = 1 if (repo_name and _dir_contains_repo(dir_name, repo_name)) else 0
        try:
            jsonl_entries = list(project_dir.iterdir())
        except OSError:
            continue
        for entry in jsonl_entries:
            if not entry.is_file() or not entry.name.endswith(".jsonl"):
                continue
            try:
                st = os.stat(entry)
            except OSError:
                continue
            candidates.append((hint, st.st_mtime, entry, dir_name))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Build preliminary Session objects with mtime-derived timestamps
    preliminary: list[Session] = []
    for hint_score, mtime, path, _ in candidates:
        session_id = path.stem
        updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        session = Session(
            id=session_id,
            agent=AGENT_NAME,
            path=path,
            timestamp=updated_at,
            updated_at=updated_at,
            title="",
            cwd="",
            repo_score=hint_score,
            repo_reason="repo-name-in-path" if hint_score else "",
        )
        preliminary.append(session)

    # Date filtering on preliminary sessions before Pass 2
    after_date = [s for s in preliminary if in_date_window(s, args)]

    limit = getattr(args, "limit", 0) or getattr(args, "limit_sessions", 0)
    pass2_count = (
        max(limit, _DEFAULT_PASS2_LIMIT)
        if limit > 0
        else max(len(after_date), _DEFAULT_PASS2_LIMIT)
    )

    refined: list[Session] = []
    for i, session in enumerate(after_date):
        if i < pass2_count:
            head = _read_head_record(session.path)
            try:
                size = os.path.getsize(session.path)
                with open(session.path, "rb") as fh:
                    fh.seek(max(0, size - 2048))
                    tail_bytes = fh.read()
            except OSError:
                tail_bytes = b""

            tail_data = _parse_tail_records(tail_bytes)
            session_cwd = head.get("cwd", "")
            slug = head.get("slug", "")
            timestamp = head.get("timestamp", session.timestamp)

            title = (
                tail_data.get("customTitle") or tail_data.get("aiTitle") or slug or ""
            )

            if session_cwd:
                score, reason = repo_score(
                    session_cwd, current_cwd, current_root, repo_name
                )
            else:
                score, reason = session.repo_score, session.repo_reason

            refined.append(
                Session(
                    id=session.id,
                    agent=AGENT_NAME,
                    path=session.path,
                    timestamp=timestamp,
                    updated_at=session.updated_at,
                    title=title,
                    cwd=session_cwd,
                    repo_score=score,
                    repo_reason=reason,
                )
            )
        else:
            refined.append(session)

    return refined


def iter_search_text(record: dict[str, Any], raw: str) -> Iterable[str]:
    rtype = record.get("type")

    if rtype == "user":
        content = record.get("message", {}).get("content")
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        yield text
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    inner = block.get("content", [])
                    if isinstance(inner, list):
                        for inner_block in inner:
                            if (
                                isinstance(inner_block, dict)
                                and inner_block.get("type") == "text"
                            ):
                                t = inner_block.get("text", "")
                                if t:
                                    yield t

    elif rtype == "assistant":
        content = record.get("message", {}).get("content")
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text = block.get("text", "")
                    if text:
                        yield text
                elif btype == "tool_use":
                    name = block.get("name", "")
                    inp = block.get("input", {})
                    yield f"{name} {json.dumps(inp)}"

    elif rtype == "summary":
        text = record.get("summary", "")
        if text:
            yield text


def display_text(record: dict[str, Any], raw: str) -> str:
    rtype = record.get("type")

    if rtype == "user":
        parts = list(iter_search_text(record, raw))
        text = " ".join(parts)
        return json.dumps({"role": "user", "text": text})

    elif rtype == "assistant":
        content = record.get("message", {}).get("content")
        blocks = content if isinstance(content, list) else []
        rendered: list[str] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                if text:
                    rendered.append(json.dumps({"role": "assistant", "text": text}))
            elif btype == "tool_use":
                name = block.get("name", "")
                inp = block.get("input", {})
                rendered.append(
                    json.dumps({"role": "assistant", "tool": name, "input": inp})
                )
        if not rendered and isinstance(content, str) and content:
            return json.dumps({"role": "assistant", "text": content})
        return "\n".join(rendered) if rendered else raw.strip()

    elif rtype == "summary":
        text = record.get("summary", "")
        return json.dumps({"summary": text})

    return raw.strip()


def search_session(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
) -> int:
    max_matches = getattr(args, "max_matches", 0)
    width = getattr(args, "width", 280)

    match_count = 0
    header_printed = False

    try:
        fh = open(session.path, encoding="utf-8", errors="replace")
    except OSError as exc:
        warn(f"cannot open {session.path}: {exc}")
        return 0

    with fh:
        for raw in fh:
            raw_stripped = raw.strip()
            if not raw_stripped:
                continue
            try:
                record = json.loads(raw_stripped)
            except json.JSONDecodeError:
                continue

            searchable = " ".join(iter_search_text(record, raw_stripped))
            if not pattern.search(searchable):
                continue

            if not header_printed:
                agent_tag = f"[{AGENT_NAME}]"
                title_part = f" - {session.title}" if session.title else ""
                cwd_part = session.cwd or "(unknown)"
                print(f"\n=== {agent_tag} {session.id}{title_part}")
                print(f"    cwd: {cwd_part}")
                header_printed = True

            rendered = display_text(record, raw_stripped)
            print(truncate(rendered, width))

            match_count += 1
            if max_matches > 0 and match_count >= max_matches:
                break

    return match_count
