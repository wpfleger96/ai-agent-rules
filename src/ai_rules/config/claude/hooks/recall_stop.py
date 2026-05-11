#!/usr/bin/env python3
"""Stop hook safety net for recall KB write-back.

Conservative gatekeeper: blocks the stop ONLY when the transcript contains
strong signals that the agent should have persisted knowledge but didn't.
The main Claude session (which has full MCP access) does the actual
evaluation and writing.

Signals checked:
  - User explicitly asked to remember/save/persist something
  - User corrected the agent (directed at the agent, not third-party systems)

Everything else is left to inline agent judgment via AGENTS.md instructions.
This hook is a safety net, not the primary write-back mechanism.
"""

import json
import re
import sys

from pathlib import Path
from typing import Any

PERSIST_PATTERNS = re.compile(
    r"\b(remember\s+this|save\s+this|persist\s+this|"
    r"add\s+(this\s+)?to\s+(the\s+)?(kb|knowledge\s+base|recall)|"
    r"write\s+(this\s+)?(to|in)\s+(the\s+)?(kb|knowledge\s+base|recall)|"
    r"don'?t\s+forget\s+(this|that))\b",
    re.IGNORECASE,
)

CORRECTION_PATTERNS = re.compile(
    r"\b(you'?re\s+(wrong|incorrect|mistaken)|"
    r"you\s+(got|have)\s+(that|it|this)\s+wrong|"
    r"that'?s\s+not\s+(right|correct|true|accurate)|"
    r"no[,.]?\s+that'?s\s+(wrong|incorrect|not\s+right))\b",
    re.IGNORECASE,
)

RECALL_WRITE_TOOLS = {"mcp__recall__write_note", "mcp__recall__edit_note"}
RECALL_MCP_TOOLS = {"mcp__recall__search_notes", "mcp__recall__recall_status"}

BLOCK_REASON_PERSIST = (
    "The user asked to persist knowledge to the recall KB but no write happened. "
    "Evaluate what they wanted saved: search recall first to avoid duplicates, "
    "then call write_note or edit_note. Invoke /kb for formatting conventions."
)

BLOCK_REASON_CORRECTION = (
    "The user corrected an error but the correction wasn't persisted to recall. "
    "Write the correction as a note with a [misconception] tag. Search recall "
    "first to avoid duplicates. Invoke /kb for formatting conventions."
)


def parse_transcript(path: str) -> list[dict[str, Any]]:
    """Parse transcript JSONL into a list of message records."""
    messages: list[dict[str, Any]] = []
    transcript = Path(path)
    if not transcript.exists():
        return messages
    with transcript.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    continue
                if "message" in record:
                    record = record["message"]
                if isinstance(record, dict):
                    messages.append(record)
            except json.JSONDecodeError:
                continue
    return messages


def has_recall_mcp(messages: list[dict[str, Any]]) -> bool:
    """Check if recall MCP tools were used, indicating recall is available."""
    all_tools = RECALL_WRITE_TOOLS | RECALL_MCP_TOOLS
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") in all_tools:
                        return True
    return False


def has_unaddressed_signal(messages: list[dict[str, Any]]) -> str | None:
    """Scan transcript backward for signals not followed by a recall write.

    Returns the block reason if an unaddressed signal is found, None otherwise.
    Each turn gets independent evaluation — a write at turn 1 doesn't satisfy
    a "remember this" at turn 10.
    """
    latest_signal: str | None = None

    for msg in reversed(messages):
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") in RECALL_WRITE_TOOLS:
                        return None

        if msg.get("role") != "user":
            continue

        text_parts: list[str] = []
        raw = msg.get("content", "")
        if isinstance(raw, str):
            text_parts.append(raw)
        elif isinstance(raw, list):
            for block in raw:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

        for text in text_parts:
            if PERSIST_PATTERNS.search(text):
                latest_signal = BLOCK_REASON_PERSIST
            elif CORRECTION_PATTERNS.search(text):
                latest_signal = BLOCK_REASON_CORRECTION

        if latest_signal:
            return latest_signal

    return None


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    messages = parse_transcript(transcript_path)
    if not messages:
        sys.exit(0)

    if not has_recall_mcp(messages):
        sys.exit(0)

    block_reason = has_unaddressed_signal(messages)
    if block_reason:
        sys.stderr.write(block_reason)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
