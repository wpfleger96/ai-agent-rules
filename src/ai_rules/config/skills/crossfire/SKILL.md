---
name: crossfire
description: Get multi-model perspectives (Codex + Gemini) on any work product. Use at any development stage — planning, design, implementation, testing — to catch blind spots the primary agent might miss.
allowed-tools: AskUserQuestion, Bash, Glob, Grep, Read
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

You are a crossfire review coordinator. Your job is to identify the artifact the user wants reviewed, then run independent reviews via Codex (GPT) and Gemini CLIs in parallel, and synthesize a consensus report.

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

---

After determining the artifact (and optional review focus), proceed to **Orchestration**.

## Orchestration

### Step 1: Check CLI Availability

```bash
CODEX_AVAILABLE=$(command -v codex >/dev/null 2>&1 && [ -f ~/.env/openai.key ] && echo "yes" || echo "no")
GEMINI_AVAILABLE=$(command -v gemini >/dev/null 2>&1 && [ -f ~/.env/gemini_cli.key ] && echo "yes" || echo "no")
```

If neither CLI is available, inform the user and stop:

```
## Crossfire Review

Crossfire unavailable: neither `codex` nor `gemini` CLI found.
```

If only one is available, proceed with that single CLI — its findings become single-model observations by default.

### Step 2: Build the Review Prompt

Construct a prompt for the external CLI agents. The prompt must include these sections in order:

1. **Preamble:**
```
You are reviewing the following artifact. Analyze it critically from your perspective as an independent reviewer. The primary AI agent has already produced this work — your job is to catch what it missed.
```

2. **Review focus** (if one was determined from artifact detection):
```
REVIEW FOCUS: <the focus question>
```

3. **Review instructions:**
```
For each concern you identify, categorize it as:
- CRITICAL: Fundamental flaw, security risk, data loss potential, or incorrect approach
- IMPORTANT: Significant gap, missing consideration, or maintainability concern
- MINOR: Nice-to-have improvement, style issue, or alternative worth considering

Structure your response as:

## Concerns

### [CRITICAL/IMPORTANT/MINOR]: <title>
<explanation of the concern and why it matters>

### [CRITICAL/IMPORTANT/MINOR]: <title>
<explanation>

## What's Done Well
<acknowledge strengths — what should NOT be changed>

## Alternative Approaches
<if you would have taken a fundamentally different approach, describe it briefly>
```

4. **Artifact** appended at the end:
```
--- ARTIFACT ---
<artifact content>
```

### Step 3: Write Prompt and Launch CLIs

Write the full prompt to a temp file. Do NOT pass it as a command-line argument — large artifacts (diffs, plans) exceed the OS `ARG_MAX` limit (~256KB on macOS). By writing to a file and giving the CLI a short instruction to read it, the command line stays small.

```bash
PROMPT_DIR=$(mktemp -d /tmp/crossfire-prompt-XXXXXX)
PROMPT_FILE="$PROMPT_DIR/prompt.txt"
# Write the constructed prompt from Step 2 to $PROMPT_FILE

CODEX_OUT=$(mktemp)
CODEX_ERR=$(mktemp)
GEMINI_OUT=$(mktemp)
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
# Gemini's ImportProcessor resolves @-refs relative to cwd — ENOENT errors from subdirs
cd "$REPO_ROOT"

# Clean up all temp files when shell exits (normal or interrupt)
trap 'rm -rf "$PROMPT_DIR" "$CODEX_OUT" "$CODEX_ERR" "$GEMINI_OUT"' EXIT INT TERM

# Codex (background) — only if available
if [ "$CODEX_AVAILABLE" = "yes" ]; then
  OPENAI_API_KEY=$(cat ~/.env/openai.key) timeout 300 codex exec -C "$REPO_ROOT" \
    --dangerously-bypass-approvals-and-sandbox \
    "Follow the review instructions below." \
    < "$PROMPT_FILE" \
    > "$CODEX_OUT" 2>"$CODEX_ERR" &
  CODEX_PID=$!
fi

# Gemini (background) — only if available
if [ "$GEMINI_AVAILABLE" = "yes" ]; then
  GEMINI_API_KEY=$(cat ~/.env/gemini_cli.key) timeout 300 gemini --yolo \
    --include-directories "$PROMPT_DIR" \
    -p "Read the file at $PROMPT_FILE and follow the review instructions inside it." \
    > "$GEMINI_OUT" 2>&1 &
  GEMINI_PID=$!
fi

# Wait for both
[ -n "$CODEX_PID" ] && { wait $CODEX_PID; CODEX_EXIT=$?; }
[ -n "$GEMINI_PID" ] && { wait $GEMINI_PID; GEMINI_EXIT=$?; }

# Output results inline (parsed in Step 4 — no temp files need to persist)
echo "===CODEX_EXIT=${CODEX_EXIT:--1}==="
echo "===CODEX_OUTPUT_START==="
cat "$CODEX_OUT" 2>/dev/null || true
echo ""
echo "===CODEX_OUTPUT_END==="
echo "===CODEX_STDERR_START==="
cat "$CODEX_ERR" 2>/dev/null || true
echo ""
echo "===CODEX_STDERR_END==="
echo "===GEMINI_EXIT=${GEMINI_EXIT:--1}==="
echo "===GEMINI_OUTPUT_START==="
cat "$GEMINI_OUT" 2>/dev/null || true
echo ""
echo "===GEMINI_OUTPUT_END==="
```

### Step 4: Parse and Validate Outputs

Parse the delimited output from Step 3. Extract each model's output from the `===..._START===` / `===..._END===` markers, and read the exit codes from the `===..._EXIT=N===` lines.

Validate each model's output:
- Empty output (0 lines between markers) → mark as "Unavailable: no output produced"
- Non-empty output (>10 lines) with non-zero exit code → use the output and prepend a warning: "(Warning: CLI exited with code N — output may be partial. Stderr: [content from CODEX_STDERR section if applicable])"
- Non-zero exit code AND output is ≤10 lines → mark as "Unavailable: CLI exited with error (exit code N)"
- If Codex stderr contains only shell-init warnings (nvm, rvm, etc.) and stdout has substantive content, treat as a successful run with a warning note

Temp files are cleaned up automatically by the EXIT trap in Step 3. No manual cleanup is needed.

### Step 5: Synthesize Consensus

Apply these rules to produce the final report:

**Cross-model consensus:**
- Concern flagged by both Codex and Gemini = **agreed** (high confidence)
- Concern flagged by only one model = **potential blind spot** (note which model flagged it)

**Severity resolution:**
- If models disagree on severity for the same concern, use the highest severity (CRITICAL > IMPORTANT > MINOR)

## Output Format

Present your findings in this structure:

```
## Crossfire Review

### Codex (GPT)
[Paste Codex structured output, or "Unavailable: [reason]"]

### Gemini
[Paste Gemini structured output, or "Unavailable: [reason]"]

### Cross-Model Consensus

**Agreed concerns (2+ models flagged):**
- [CRITICAL/IMPORTANT/MINOR] [Concern]: flagged by [which models]

**Single-model concerns (potential blind spots):**
- [CRITICAL/IMPORTANT/MINOR] [Concern]: only [model] flagged this

### Strengths Confirmed
[Items that multiple models agreed are done well]

### Summary
[2-3 sentence synthesis: overall confidence level, key action items, and whether the artifact needs revision]
```

## Key Requirements

- Launch CLIs in parallel, not sequentially
- Do NOT modify the artifact — only review it
- Do NOT skip concerns because they seem minor — surface everything and let severity classification do the prioritization
- Temp files are cleaned up automatically via the EXIT trap — do not add manual cleanup
- If only one CLI is available, still run the review with that single model

## Examples

- `/crossfire` — auto-detects artifact (diff or plan), runs orchestration
- `/crossfire plan` — reviews the most recent PLAN file
- `/crossfire diff` — reviews current code changes
- `/crossfire "is this the right approach for caching?"` — reviews recent context with that focus question
- `/crossfire src/auth/middleware.py` — reviews a specific file
