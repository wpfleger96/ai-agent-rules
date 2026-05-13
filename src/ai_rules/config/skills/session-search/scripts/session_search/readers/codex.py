"""Codex CLI session reader."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex

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

AGENT_NAME: str = "codex"

SESSION_RE = re.compile(
    r"rollout-(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-(?P<id>[0-9a-fA-F-]+)\.jsonl$"
)


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def detect() -> bool:
    home = _codex_home()
    return (home / "sessions").exists() or (home / "archived_sessions").exists()


def _read_index(index_path: Path) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    if not index_path.exists():
        return by_id
    with index_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            session_id = str(item.get("id") or "")
            if session_id:
                by_id[session_id] = {
                    "thread_name": str(item.get("thread_name") or ""),
                    "updated_at": str(item.get("updated_at") or ""),
                }
    return by_id


def _fallback_id_and_timestamp(path: Path) -> tuple[str, str]:
    match = SESSION_RE.search(path.name)
    if not match:
        return "", ""
    session_id = match.group("id")
    stamp = match.group("stamp")
    date_part, time_part = stamp.split("T", 1)
    timestamp = f"{date_part}T{time_part.replace('-', ':')}Z"
    return session_id, timestamp


def _session_meta(path: Path) -> dict[str, str]:
    fallback_id, fallback_timestamp = _fallback_id_and_timestamp(path)
    meta: dict[str, str] = {
        "id": fallback_id,
        "timestamp": fallback_timestamp,
        "cwd": "",
        "agent_role": "",
        "agent_nickname": "",
    }
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for _ in range(40):
                line = fh.readline()
                if not line:
                    break
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("type") != "session_meta":
                    continue
                payload = item.get("payload") or {}
                meta["id"] = str(payload.get("id") or meta["id"])
                meta["timestamp"] = str(
                    payload.get("timestamp")
                    or item.get("timestamp")
                    or meta["timestamp"]
                )
                meta["cwd"] = str(payload.get("cwd") or "")
                meta["agent_role"] = str(payload.get("agent_role") or "")
                meta["agent_nickname"] = str(payload.get("agent_nickname") or "")
                break
    except OSError:
        pass
    return meta


def iter_sessions(args: argparse.Namespace) -> list[Session]:
    home = _codex_home()
    index = _read_index(home / "session_index.jsonl")

    current_cwd = (
        str(Path(args.cwd).expanduser().resolve()) if getattr(args, "cwd", None) else ""
    )
    current_root = ""
    repo_name = getattr(args, "repo", None) or ""
    if current_cwd:
        _, current_root, repo_name = repo_context(current_cwd, repo_name or None)

    dirs: list[Path] = []
    if (home / "sessions").exists():
        dirs.append(home / "sessions")
    if (home / "archived_sessions").exists():
        dirs.append(home / "archived_sessions")

    sessions: list[Session] = []
    all_repos = getattr(args, "all_repos", False)
    for sessions_dir in dirs:
        for path in sessions_dir.rglob("*.jsonl"):
            if not SESSION_RE.search(path.name):
                continue
            meta = _session_meta(path)
            session_id = meta["id"]
            idx_entry = index.get(session_id, {})
            title = idx_entry.get("thread_name", "")
            updated_at = idx_entry.get("updated_at", "")
            timestamp = meta["timestamp"]
            cwd = meta["cwd"]

            score, reason = repo_score(cwd, current_cwd, current_root, repo_name)
            if all_repos:
                score, reason = 0, ""

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
    payload = record.get("payload") or {}
    record_type = record.get("type")

    if record_type == "session_meta":
        for key in ("id", "cwd", "agent_role", "agent_nickname"):
            val = str(payload.get(key) or "")
            if val:
                yield val

    elif record_type == "turn_context":
        for key in ("cwd", "summary"):
            val = str(payload.get(key) or "")
            if val:
                yield val

    elif record_type == "response_item":
        content = payload.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = str(part.get("text") or "")
                    if text:
                        yield text
        for key in ("name", "arguments", "output"):
            val = str(payload.get(key) or "")
            if val:
                yield val

    elif record_type == "event_msg":
        event_payload = payload
        command = event_payload.get("command")
        if isinstance(command, list):
            yield " ".join(shlex.quote(str(p)) for p in command)
        elif command:
            yield str(command)
        for key in ("aggregated_output", "stdout", "stderr"):
            val = str(event_payload.get(key) or "")
            if val:
                yield val
        msg = str(event_payload.get("message") or "")
        if msg:
            yield msg
        text = str(event_payload.get("text") or "")
        if text:
            yield text

    elif record_type == "compacted":
        summary = str(payload.get("summary") or "")
        if summary:
            yield summary


def display_text(record: dict[str, Any], raw: str) -> str:
    payload = record.get("payload") or {}
    record_type = record.get("type")

    if record_type == "session_meta":
        keep = {
            k: payload.get(k)
            for k in (
                "id",
                "timestamp",
                "cwd",
                "originator",
                "agent_role",
                "agent_nickname",
            )
        }
        return json.dumps(keep, ensure_ascii=False)

    if record_type == "turn_context":
        keep = {
            k: payload.get(k)
            for k in ("cwd", "turn_id", "current_date", "timezone", "summary")
        }
        return json.dumps(keep, ensure_ascii=False)

    if record_type == "event_msg":
        event_type = payload.get("type")
        if event_type == "exec_command_end":
            command = payload.get("command")
            if isinstance(command, list):
                command_text = " ".join(shlex.quote(str(part)) for part in command)
            else:
                command_text = str(command or "")
            keep = {
                "event": event_type,
                "cwd": payload.get("cwd"),
                "command": command_text,
                "output": (
                    payload.get("aggregated_output")
                    or payload.get("stdout")
                    or payload.get("stderr")
                ),
            }
            return json.dumps(keep, ensure_ascii=False)
        keep = {
            "event": event_type,
            "message": payload.get("message"),
            "thread_name": payload.get("thread_name"),
            "text": payload.get("text"),
        }
        return json.dumps({k: v for k, v in keep.items() if v}, ensure_ascii=False)

    if record_type == "response_item":
        role = payload.get("role")
        content = payload.get("content")
        if isinstance(content, list):
            texts = [
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict)
            ]
            if any(texts):
                return json.dumps(
                    {"role": role, "text": "\n".join(texts)}, ensure_ascii=False
                )
        keep = {
            k: payload.get(k) for k in ("type", "role", "name", "arguments", "output")
        }
        return json.dumps({k: v for k, v in keep.items() if v}, ensure_ascii=False)

    return raw


def search_session(
    session: Session, pattern: re.Pattern[str], args: argparse.Namespace
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
                    print(truncate(rendered))
                    matches += 1
                    if max_matches > 0 and matches >= max_matches:
                        return matches
                    break

    except OSError as exc:
        warn(f"cannot read {session.path}: {exc}")

    return matches
