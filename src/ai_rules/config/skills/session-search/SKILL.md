---
name: session-search
description: >
  Use this skill to find, locate, or search previous coding agent sessions or
  conversations. Triggers on requests to search session transcripts or
  conversation history, recover commands or outputs from earlier sessions,
  compare recent sessions for a repository, or search across Claude Code,
  Codex CLI, Gemini CLI, Goose, or Amp session history.
---

## Context

- Current directory: !`pwd`
- Git repo root: !`git rev-parse --show-toplevel 2>/dev/null || echo "NOT_IN_GIT"`
- Repo name: !`basename $(git rev-parse --show-toplevel 2>/dev/null) 2>/dev/null || echo "UNKNOWN"`

# Session Search

Searches session transcripts across all detected coding agents: Claude Code, Codex CLI, Gemini CLI, Goose, and Amp. Results are ranked by current repo match, then by recency.

## Quick Start

Resolve `<skill-dir>` as the directory containing this SKILL.md file.

```bash
# Find sessions by title, ID fragment, or cwd (metadata only — use grep for content)
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search find "authentication"

# Search transcript content for a regex pattern
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search grep "authentication refactor" --limit-sessions 20

# List recent sessions for the current repo
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search list --limit 10
```

## Context Hygiene

For broad or exploratory searches, delegate to a subagent and return only IDs, titles, timestamps, cwd values, paths, and short snippets. Never dump raw transcripts into the main context window — a single session file can be hundreds of kilobytes.

When returning results to the user, summarize what was found and offer to retrieve specific sessions on request.

## Find Sessions

```bash
# Look up a session by ID fragment
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search find "3f8a"

# Find by title/cwd keyword across all repos
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search find "database migration" --all-repos

# List sessions for a specific repo
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search list --repo my-service

# Restrict to one agent
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search find "webhook handler" --agent claude

# Sessions since a date
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search list --since 2026-04-01
```

## Grep Sessions

```bash
# Regex search across recent sessions (default: current repo)
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search grep "TODO|FIXME" --limit-sessions 25

# Search within a specific session by ID fragment
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search grep "import requests" --id 3f8a

# Case-insensitive search, wider output, capped matches
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search grep "config" -i --max-matches 20 --width 200

# Broader search across all repos
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search grep "pg_dump" --all-repos --limit-sessions 50
```

`--limit-sessions` controls how many session files are scanned. `--max-matches` controls output volume. Prefer lower values for exploratory searches; increase when a specific pattern is known to be rare.

## Scoped Search

If `rg` is needed for low-level transcript inspection, first use `find` or `list` to get candidate session file paths, then scope `rg` to those specific files. Never run an unscoped recursive grep from `~` or `/` — session stores can contain gigabytes of transcript data.

```bash
# Step 1: get candidate paths
PYTHONPATH=<skill-dir>/scripts uv run python -m session_search find "auth flow" --json | jq -r '.[].path'

# Step 2: grep only those files
rg "Bearer token" /path/to/session1.jsonl /path/to/session2.jsonl
```

## Common Flags

| Flag | Purpose |
|------|---------|
| `--agent {claude,codex,gemini,goose,amp}` | Restrict to one agent |
| `--all-repos` | Search beyond current repo |
| `--since YYYY-MM-DD` | Lower bound on session date |
| `--until YYYY-MM-DD` | Upper bound on session date |
| `--oldest` | Reverse sort (oldest first) |
| `--limit N` | Max sessions returned |
| `--json` | Machine-readable JSON output |
| `--cwd DIR` | Treat DIR as the working directory for ranking |
| `--repo NAME` | Filter by repo name |

## Ranking

Sessions are ranked in this order:

1. Exact current `cwd` match
2. Same git repository root
3. Same repository name
4. Recency (newest first by default)

Use `--all-repos` to include sessions from unrelated repositories.

## Agent Storage Notes

| Agent | Storage location |
|-------|----------------|
| Claude Code | `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl` |
| Codex CLI | `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<id>.jsonl` |
| Gemini CLI | `~/.gemini/tmp/<project-slug>/chats/session-*.jsonl` |
| Goose | `~/.local/share/goose/sessions/sessions.db` (SQLite) |
| Amp | `~/.local/share/amp/threads/T-<uuid>.json` |
