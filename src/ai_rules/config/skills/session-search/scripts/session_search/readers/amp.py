"""Amp (Sourcegraph) session reader."""

from __future__ import annotations

import argparse
import json
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

AGENT_NAME: str = "amp"

_AMP_THREADS = Path("~/.local/share/amp/threads")
_FORMAT_VERSION_MAX = 100


def detect() -> bool:
    return _AMP_THREADS.expanduser().is_dir()


def _epoch_ms_to_iso(epoch_ms: Any) -> str:
    if not isinstance(epoch_ms, (int, float)):
        return ""
    try:
        dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
        return dt.isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


def _extract_cwd(data: dict[str, Any]) -> str:
    try:
        env = data.get("env")
        if not isinstance(env, dict):
            return ""
        initial = env.get("initial")
        if isinstance(initial, str):
            parsed = json.loads(initial)
        elif isinstance(initial, dict):
            parsed = initial
        else:
            return ""
        trees = parsed.get("trees")
        if not isinstance(trees, list) or not trees:
            return ""
        uri = trees[0].get("uri") if isinstance(trees[0], dict) else None
        if not isinstance(uri, str) or not uri:
            return ""
        if uri.startswith("file://"):
            return uri[len("file://") :]
        return uri
    except (json.JSONDecodeError, AttributeError, TypeError, KeyError):
        return ""


def iter_sessions(args: argparse.Namespace) -> list[Session]:
    threads_dir = _AMP_THREADS.expanduser()

    current_cwd = (
        str(Path(args.cwd).expanduser().resolve()) if getattr(args, "cwd", None) else ""
    )
    current_root = ""
    repo_name = getattr(args, "repo", None) or ""
    if current_cwd:
        _, current_root, repo_name = repo_context(current_cwd, repo_name or None)

    sessions: list[Session] = []

    for path in threads_dir.glob("T-*.json"):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            warn(f"cannot read {path}: {exc}")
            continue

        if not isinstance(data, dict):
            continue

        fmt_version = data.get("v")
        if isinstance(fmt_version, int) and fmt_version > _FORMAT_VERSION_MAX:
            warn(
                f"{path.name}: format version {fmt_version} exceeds known max {_FORMAT_VERSION_MAX}; format may have changed"
            )

        session_id = str(data.get("id") or path.stem)
        created_ms = data.get("created")
        timestamp = _epoch_ms_to_iso(created_ms)

        title = data.get("title") or ""
        if not isinstance(title, str):
            title = ""

        messages = data.get("messages")
        if not isinstance(messages, list):
            messages = []

        updated_at = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                meta = last_msg.get("meta")
                if isinstance(meta, dict):
                    sent_at = meta.get("sentAt")
                    updated_at = _epoch_ms_to_iso(sent_at)
        if not updated_at:
            updated_at = timestamp

        cwd = _extract_cwd(data)

        score, reason = repo_score(cwd, current_cwd, current_root, repo_name)

        session = Session(
            id=session_id,
            agent=AGENT_NAME,
            path=path,
            timestamp=timestamp,
            updated_at=updated_at,
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
    content = record.get("content")
    if not isinstance(content, list):
        return

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")

        if block_type == "text":
            text = str(block.get("text") or "")
            if text:
                yield text

        elif block_type == "tool_use":
            name = str(block.get("name") or "")
            if name:
                yield name
            inp = block.get("input")
            if inp is not None:
                try:
                    yield json.dumps(inp, ensure_ascii=False)
                except (TypeError, ValueError):
                    pass

        elif block_type == "tool_result":
            result_content = block.get("content")
            if isinstance(result_content, list):
                for item in result_content:
                    if isinstance(item, dict):
                        text = str(item.get("text") or "")
                        if text:
                            yield text

        elif block_type == "thinking":
            thinking = str(block.get("thinking") or "")
            if thinking:
                yield thinking


def display_text(record: dict[str, Any], raw: str) -> str:
    role = str(record.get("role") or "")
    content = record.get("content")
    if not isinstance(content, list):
        return json.dumps({"role": role}, ensure_ascii=False)

    parts: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")

        if block_type == "text":
            text = str(block.get("text") or "")
            parts.append({"role": role, "text": text})

        elif block_type == "tool_use":
            name = str(block.get("name") or "")
            inp = block.get("input")
            parts.append({"role": role, "tool": name, "input": inp})

        elif block_type == "tool_result":
            result_content = block.get("content")
            texts: list[str] = []
            if isinstance(result_content, list):
                for item in result_content:
                    if isinstance(item, dict):
                        t = str(item.get("text") or "")
                        if t:
                            texts.append(t)
            parts.append({"role": role, "tool_result": "\n".join(texts)})

    if not parts:
        return json.dumps({"role": role}, ensure_ascii=False)
    if len(parts) == 1:
        return json.dumps(parts[0], ensure_ascii=False)
    return json.dumps(parts, ensure_ascii=False)


def search_session(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
) -> int:
    max_matches = getattr(args, "max_matches", 0)
    width = getattr(args, "width", 280)
    header_printed = False
    matches = 0

    try:
        with session.path.open("r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        warn(f"cannot read {session.path}: {exc}")
        return 0

    if not isinstance(data, dict):
        return 0

    messages = data.get("messages")
    if not isinstance(messages, list):
        return 0

    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue

        searchable_parts = list(iter_search_text(msg, ""))
        combined = "\n".join(searchable_parts)
        if not combined or not pattern.search(combined):
            continue

        if not header_printed:
            label = f" [{session.repo_reason}]" if session.repo_reason else ""
            title_part = f" - {session.title}" if session.title else ""
            print(f"\n=== [{AGENT_NAME}] {session.id}{label}{title_part} ===")
            print(f"    {session.path}")
            header_printed = True

        rendered = display_text(msg, "")
        print(f"[msg {idx}] {truncate(rendered, width)}")
        matches += 1
        if max_matches > 0 and matches >= max_matches:
            return matches

    return matches
