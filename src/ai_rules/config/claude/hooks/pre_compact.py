#!/usr/bin/env python3
"""PreCompact hook: runs distill logic before every Claude Code compaction.

Outputs a high-quality summary as plain text to stdout. Claude Code feeds
this to the compaction model as custom instructions (undocumented but
community-validated via GitHub #14258).

On ANY error: prints nothing and exits 0, letting CC's default compaction
proceed unimpeded.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

try:
    import distill_core  # type: ignore[import-not-found]
except ImportError:
    sys.exit(0)

RECENT_THRESHOLD_SECONDS = 1800  # 30 minutes


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    cwd = hook_input.get("cwd", os.getcwd())
    transcript_path = hook_input.get("transcript_path", "")

    summary_path = distill_core.get_summary_path(cwd)
    if summary_path.exists():
        age = time.time() - summary_path.stat().st_mtime
        if age < RECENT_THRESHOLD_SECONDS:
            print(summary_path.read_text())
            return

    jsonl_path = (
        transcript_path if transcript_path else distill_core.get_jsonl_path(cwd)
    )
    if not jsonl_path or not os.path.exists(jsonl_path):
        return

    transcript = distill_core.extract_transcript(jsonl_path)
    if not transcript.strip():
        return

    prior_summary = distill_core.read_prior_summary(cwd)

    briefing_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "distill_briefing.md"
    )
    if not os.path.exists(briefing_path):
        return

    with open(briefing_path) as f:
        briefing_template = f.read()

    summary = distill_core.run_distill_subprocess(
        transcript=transcript,
        prior_summary=prior_summary,
        briefing_template=briefing_template,
        cwd=cwd,
        timeout=120,
    )

    if summary:
        distill_core.save_artifacts(cwd, summary, transcript)
        print(summary)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
