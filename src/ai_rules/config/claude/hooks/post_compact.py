#!/usr/bin/env python3
"""SessionStart compact hook: re-injects distill summary after CC compaction.

Safety net for the PreCompact hook. If the PreCompact stdout -> compaction
model channel fails (undocumented behavior), this hook ensures the distill
summary still reaches the post-compaction context as a system message.

Simple: read summary file, print to stdout. No subprocess, no heavy logic.
Always exits 0.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

try:
    import distill_core  # type: ignore[import-not-found]
except ImportError:
    sys.exit(0)


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    cwd = hook_input.get("cwd", os.getcwd())

    summary = distill_core.read_prior_summary(cwd)
    if summary:
        print(summary)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
