#!/usr/bin/env python3
"""Stop hook safety net for recall KB write-back.

Conservative gatekeeper: blocks the stop ONLY when the transcript contains
strong signals that the agent should have persisted knowledge but didn't.
The main Claude session (which has full MCP access) does the actual
evaluation and writing.

Signals checked:
  - User explicitly asked to remember/save/persist something
  - User corrected the agent and the correction wasn't persisted

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
    r"\b(that'?s\s+(wrong|incorrect|not\s+right|not\s+true|inaccurate)|"
    r"no[,.]?\s+(that'?s|it'?s|actually)|"
    r"you'?re\s+wrong|"
    r"incorrect[,.]|"
    r"actually[,.]?\s+(it|that|the)\s+(is|was|should))\b",
    re.IGNORECASE,
)

RECALL_WRITE_TOOLS = {"mcp__recall__write_note", "mcp__recall__edit_note"}

BLOCK_REASON = (
    "The session contains knowledge that should be persisted to the recall KB "
    "but wasn't written yet. Evaluate what's worth persisting: search recall "
    "first to avoid duplicates, then call write_note or edit_note. "
    "Invoke /kb for formatting conventions."
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
                if "message" in record:
                    record = record["message"]
                messages.append(record)
            except json.JSONDecodeError:
                continue
    return messages


def recall_already_wrote(messages: list[dict[str, Any]]) -> bool:
    """Check if recall write tools were called in recent messages."""
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") in RECALL_WRITE_TOOLS:
                        return True
    return False


def extract_user_text(messages: list[dict[str, Any]]) -> list[str]:
    """Extract text from user messages."""
    texts = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
    return texts


def has_persist_signal(user_texts: list[str]) -> bool:
    """Check if user explicitly asked to persist knowledge."""
    return any(PERSIST_PATTERNS.search(text) for text in user_texts)


def has_correction_signal(user_texts: list[str]) -> bool:
    """Check if user corrected the agent."""
    return any(CORRECTION_PATTERNS.search(text) for text in user_texts)


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

    if recall_already_wrote(messages):
        sys.exit(0)

    user_texts = extract_user_text(messages)

    if has_persist_signal(user_texts) or has_correction_signal(user_texts):
        sys.stderr.write(BLOCK_REASON)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
