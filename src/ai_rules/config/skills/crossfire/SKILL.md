---
name: crossfire
description: Get multi-model perspectives (Codex + Gemini) on any work product. Use at any development stage — planning, design, implementation, testing — to catch blind spots the primary agent might miss.
allowed-tools: Agent, AskUserQuestion, Bash, Glob, Grep, Read
model: sonnet
metadata:
  trigger-keywords: "crossfire, second opinion, blind spots, cross-model review, multi-model review"
---

## Context

- Arguments: `${ARGS}` (optional: artifact type, file path, or review focus question)
- Main repo root: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && dirname "$COMMON" || echo "NOT_IN_GIT_REPO"'`
- Current branch: !`git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "NO_BRANCH"`
- Uncommitted changes: !`git status --porcelain 2>/dev/null | wc -l | xargs`
- PLAN files: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); if [ -z "$COMMON" ]; then exit 0; fi; PROJECT_ROOT=$(dirname "$COMMON"); cd "$PROJECT_ROOT" && for f in PLAN__*.md; do [ -f "$f" ] && echo "$f"; done' 2>/dev/null | head -5`

You are a crossfire review coordinator. Your job is to identify the artifact the user wants reviewed, then delegate to the crossfire agent for multi-model analysis.

## Artifact Detection

Parse `${ARGS}` to determine what to review. Check in this order:

### 1. Explicit Artifact Type

If args contain a recognized keyword, use that:

| Keyword | Artifact | How to gather |
|---------|----------|---------------|
| `plan` | Most recent PLAN file | Read the newest `PLAN__*.md` file from the main repo root |
| `diff` | Current code changes | `git diff` (unstaged), then `git diff --cached` (staged), then `git diff origin/$(git symbolic-ref --short HEAD)..HEAD` (unpushed) — use first non-empty |
| `tests` | Test files | Identify recently modified test files via `git diff --name-only` filtered to test patterns |

### 2. Explicit File Path

If args contain a file path (starts with `/`, `./`, or `~`), read that file as the artifact.

### 3. Review Focus Question

If args are a quoted string or natural language question (e.g., `"is this architecture sound?"`), treat it as the review focus. Gather the most relevant artifact from context:
- If there are uncommitted changes → use the diff
- If PLAN files exist → use the most recent one
- Otherwise, ask the user what to review

### 4. No Args

If no args provided:
- If uncommitted changes exist → review the diff
- If PLAN files exist → review the most recent one
- Otherwise, ask the user: "What would you like me to get a crossfire review on?"

## Execution

Once you have the artifact (and optional review focus):

1. Spawn the **crossfire agent** using the Agent tool with:
   - The artifact content
   - The review focus (if any)
   - Brief context about what the artifact is (e.g., "This is a PLAN file for implementing auth flow" or "This is a git diff of uncommitted changes")

2. Present the crossfire agent's findings to the user exactly as returned — do not filter or summarize.

## Examples

- `/crossfire` — auto-detects artifact (diff or plan), sends to crossfire agent
- `/crossfire plan` — reviews the most recent PLAN file
- `/crossfire diff` — reviews current code changes
- `/crossfire "is this the right approach for caching?"` — reviews recent context with that focus question
- `/crossfire src/auth/middleware.py` — reviews a specific file
