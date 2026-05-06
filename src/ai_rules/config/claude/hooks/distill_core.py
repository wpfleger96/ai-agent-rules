"""Shared distillation logic for PreCompact and SessionStart hooks.

Extracts conversation transcripts from JSONL, applies observation masking,
runs a fresh-context summarization subprocess, and persists artifacts.
"""

import glob
import json
import os
import shutil
import subprocess

from datetime import datetime
from pathlib import Path


def get_project_slug(cwd: str) -> str:
    return cwd.replace("/", "-")


def get_jsonl_path(cwd: str) -> str | None:
    home = os.path.expanduser("~")
    slug = get_project_slug(cwd)
    proj_dir = f"{home}/.claude/projects/{slug}"
    files = sorted(glob.glob(f"{proj_dir}/*.jsonl"), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def get_summary_path(cwd: str) -> Path:
    home = os.path.expanduser("~")
    slug = get_project_slug(cwd)
    return Path(home) / ".claude" / "distill-summaries" / f"{slug}.md"


def get_backup_path(cwd: str, date: str | None = None) -> Path:
    home = os.path.expanduser("~")
    slug = get_project_slug(cwd)
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    return Path(home) / ".claude" / "distill-backups" / f"{date}-{slug}.txt"


def read_prior_summary(cwd: str) -> str | None:
    path = get_summary_path(cwd)
    if path.exists():
        return path.read_text()
    return None


def extract_transcript(jsonl_path: str, max_chars: int = 120_000) -> str:
    lines: list[str] = []

    with open(jsonl_path) as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg_type = record.get("type", "")
            if msg_type == "summary":
                text = record.get("summary", "")
                if text:
                    lines.append(f"[PRIOR COMPACTION SUMMARY]\n{text}\n")
                continue

            message = record.get("message", {})
            if not isinstance(message, dict):
                continue

            role = message.get("role", "")
            if role not in ("user", "assistant"):
                continue

            content = message.get("content", "")
            if isinstance(content, str):
                lines.append(f"[{role.upper()}]\n{content}\n")
            elif isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict):
                        parts.append(_process_content_block(block))
                if parts:
                    lines.append(
                        f"[{role.upper()}]\n" + "\n".join(p for p in parts if p) + "\n"
                    )

    transcript = "\n".join(lines)

    if len(transcript) > max_chars:
        transcript = transcript[-max_chars:]
        first_newline = transcript.find("\n")
        if first_newline > 0:
            transcript = transcript[first_newline + 1 :]
        transcript = "[...transcript truncated from oldest end...]\n\n" + transcript

    return transcript


def _process_content_block(block: dict[str, object]) -> str:
    btype = block.get("type", "")

    if btype == "text":
        return str(block.get("text", ""))

    if btype == "tool_use":
        name = block.get("name", "unknown")
        inp = block.get("input", {})
        inp_str = json.dumps(inp) if isinstance(inp, dict) else str(inp)
        if len(inp_str) > 500:
            inp_str = inp_str[:500] + "..."
        return f"[Tool Call: {name}({inp_str})]"

    if btype == "tool_result":
        tool_id = block.get("tool_use_id", "unknown")
        result_content = block.get("content", "")
        if isinstance(result_content, str):
            char_count = len(result_content)
        elif isinstance(result_content, list):
            char_count = sum(len(json.dumps(r)) for r in result_content)
        else:
            char_count = len(str(result_content))
        return f"[Tool Result: {tool_id} -- {char_count} chars, masked]"

    return str(block.get("text", ""))


def run_distill_subprocess(
    transcript: str,
    prior_summary: str | None,
    briefing_template: str,
    cwd: str | None = None,
    timeout: int = 120,
) -> str | None:
    prior = prior_summary if prior_summary else "[None — first distillation]"
    date = datetime.now().strftime("%Y-%m-%d")
    if cwd is None:
        cwd = os.getcwd()

    briefing = briefing_template
    briefing = briefing.replace("{{DATE}}", date)
    briefing = briefing.replace("{{PROJECT}}", cwd)
    briefing = briefing.replace("{{PRIOR_SUMMARY}}", prior)
    briefing = briefing.replace("{{TRANSCRIPT}}", transcript)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "sonnet"],
            input=briefing,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def save_artifacts(cwd: str, summary: str, transcript: str) -> tuple[Path, Path]:
    summary_path = get_summary_path(cwd)
    backup_path = get_backup_path(cwd)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    prev_path = summary_path.with_name(f"{summary_path.stem}-prev{summary_path.suffix}")
    if summary_path.exists():
        shutil.move(str(summary_path), str(prev_path))

    summary_path.write_text(summary)
    backup_path.write_text(transcript)

    return summary_path, backup_path
