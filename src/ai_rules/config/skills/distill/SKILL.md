---
name: distill
description: >
  Produce a high-fidelity context summary using fresh sub-agent summarization.
  Use when the user asks to 'distill', 'checkpoint context', 'summarize session',
  'compress conversation', or when context is getting long and needs to be condensed.
  Superior to built-in compaction because a fresh sub-agent reads the transcript
  from disk instead of the current model summarizing its own degrading context.
allowed-tools: Bash, Read, Write
model: sonnet
---

## Context

- Date: !`date -u +"%Y-%m-%d"`
- Working directory: !`pwd`
- Project root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Session JSONL: !`python3 -c "import os,glob; cwd=os.getcwd(); home=os.path.expanduser('~'); slug=cwd.replace('/','-'); d=f'{home}/.claude/projects/{slug}'; files=sorted(glob.glob(f'{d}/*.jsonl'), key=os.path.getmtime, reverse=True); print(files[0] if files else 'NOT_FOUND')"`
- Prior distill summary: !`python3 -c "import os; cwd=os.getcwd(); home=os.path.expanduser('~'); slug=cwd.replace('/','-'); p=f'{home}/.claude/distill-summaries/{slug}.md'; print(p if os.path.exists(p) else 'NONE')"`

# Distill

You are a context distillation orchestrator. Your job is to extract the current session transcript, build a briefing for a fresh sub-agent, invoke it via `claude -p`, and persist the artifacts.

The entire distillation pipeline runs via Bash — the transcript and briefing are too large to pass through the Agent tool's prompt parameter (would exceed output token limits). Instead, the briefing is written to a temp file and piped to `claude -p --model sonnet`.

## Phase 1: Extract and Mask Transcript

Extract the conversation from the session JSONL file and apply observation masking. Uses `distill_core` module (symlinked to `~/.claude/hooks/` by ai-rules install).

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
import distill_core

jsonl_path = os.environ.get("SESSION_JSONL", "")
if not jsonl_path or jsonl_path == "NOT_FOUND":
    jsonl_path = distill_core.get_jsonl_path(os.getcwd())

if not jsonl_path:
    print("ERROR: No session JSONL found", file=sys.stderr)
    sys.exit(1)

transcript = distill_core.extract_transcript(jsonl_path)

slug = distill_core.get_project_slug(os.getcwd())
tmp_path = f"/tmp/distill-transcript-{slug}.txt"
with open(tmp_path, "w") as f:
    f.write(transcript)

print(f"Transcript extracted: {len(transcript)} chars -> {tmp_path}")
PYEOF
```

If the output says "ERROR", stop and report the issue to the user.

## Phase 2: Build Briefing and Run Fresh Sub-Agent

Read `references/subagent-briefing.md` and `references/summary-template.md` from this skill's directory. Then run the full pipeline — build the briefing, write it to a temp file, and invoke `claude -p --model sonnet` as a fresh-context subprocess:

```bash
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
import distill_core

cwd = os.getcwd()
slug = distill_core.get_project_slug(cwd)
transcript_path = f"/tmp/distill-transcript-{slug}.txt"

if not os.path.exists(transcript_path):
    print("ERROR: Transcript file not found", file=sys.stderr)
    sys.exit(1)

with open(transcript_path) as f:
    transcript = f.read()

prior_summary = distill_core.read_prior_summary(cwd)

briefing_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "distill_briefing.md"
) if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(__file__)), "distill_briefing.md")) else os.path.expanduser("~/.claude/hooks/distill_briefing.md")

if not os.path.exists(briefing_path):
    print("ERROR: Briefing template not found", file=sys.stderr)
    sys.exit(1)

with open(briefing_path) as f:
    briefing_template = f.read()

print("Running fresh-context distillation subprocess...")
summary = distill_core.run_distill_subprocess(
    transcript=transcript,
    prior_summary=prior_summary,
    briefing_template=briefing_template,
    cwd=cwd,
    timeout=120,
)

if not summary:
    print("ERROR: Distillation subprocess failed or produced no output", file=sys.stderr)
    sys.exit(1)

summary_path, backup_path = distill_core.save_artifacts(cwd, summary, transcript)

os.remove(transcript_path)

print(f"SUMMARY_PATH={summary_path}")
print(f"BACKUP_PATH={backup_path}")
print("===DISTILL_SUMMARY_START===")
print(summary)
print("===DISTILL_SUMMARY_END===")
PYEOF
```

If the output says "ERROR", report the issue to the user.

## Phase 3: Output

Extract the summary from the Phase 2 output (between `===DISTILL_SUMMARY_START===` and `===DISTILL_SUMMARY_END===` markers) and output it to the conversation:

```
<distill-summary>
[the 9-section summary from the subprocess output]

---
Recovery: If details are missing, read the backup transcript at:
`[BACKUP_PATH from Phase 2 output]`
</distill-summary>
```

## Key Requirements

- The sub-agent runs as a `claude -p --model sonnet` subprocess — completely fresh context, no access to this conversation
- NEVER attempt to summarize the conversation from your own context — that's the same-context self-summarization anti-pattern we're specifically avoiding
- The transcript comes from the JSONL file on disk, not from in-context messages
- Observation masking replaces tool results with placeholders to reduce noise
- The 120K char cap keeps the sub-agent's input within its context window
- On any error, report clearly — do not silently produce a partial summary
