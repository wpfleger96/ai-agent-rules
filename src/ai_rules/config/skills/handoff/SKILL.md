---
name: handoff
version: 1.0.0
description: Generates a portable handoff document summarizing the current session (task, discussion, decisions, research, work done, current state, next steps) as a single copy-pasteable markdown block, so another agent can resume the work on a different device or terminal.
disable-model-invocation: true
allowed-tools: Bash, Glob, Grep, Read
model: opus
---

## Context

- Arguments: `${ARGS}` (optional: a focus/scope hint, e.g. "focus on the auth refactor")
- Current branch: !`git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "NO_BRANCH"`
- Main repo root: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && dirname "$COMMON" || echo "NOT_IN_GIT_REPO"'`
- Git status: !`git status --porcelain 2>/dev/null | head -40 || echo "NOT_IN_GIT"`
- Recent commits: !`git log --oneline -10 2>/dev/null || echo "NO_COMMITS"`
- Unstaged diff stat: !`git diff --stat 2>/dev/null | tail -30 || echo "NONE"`
- Staged diff stat: !`git diff --cached --stat 2>/dev/null | tail -30 || echo "NONE"`
- Unpushed commits: !`git log --oneline @{u}.. 2>/dev/null || echo "NO_UPSTREAM_OR_NONE"`
- PLAN/TODO files: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); PROJECT_ROOT=$(dirname "$COMMON" 2>/dev/null); if [ -n "$PROJECT_ROOT" ] && [ "$PROJECT_ROOT" != "." ]; then ls "$PROJECT_ROOT"/PLAN__*.md "$PROJECT_ROOT"/TODO.md 2>/dev/null || echo "No PLAN/TODO files found"; else ls PLAN__*.md TODO.md 2>/dev/null || echo "No PLAN/TODO files found"; fi'`

# Generate Session Handoff

Produce a **single, self-contained markdown block** that captures everything another agent
needs to resume this work on a different device or in a fresh terminal. This is like compaction,
except the result is a portable document for a *new* agent rather than an in-place summary.

**Do not write any file to disk.** Render the handoff directly into the chat as one code block
that the user can select and copy in a single action.

## What to capture

Mine the **entire conversation so far** plus the pre-executed Context above. Cover:

- The user's original and intended task — quote their words verbatim where the exact phrasing
  matters to intent.
- How the discussion and approach evolved (including course corrections).
- Planning and the agreed strategy.
- Research results and findings: key facts, file/API discoveries, gotchas — with paths/links.
- Decisions made, with rationale; note rejected alternatives and *why* they were rejected.
- Implementation work done so far: concrete changes, each with file paths (use `path:line` when
  it helps locate the change).
- Current repository state (branch, staged/unstaged files, recent and unpushed commits,
  build/test status) from the Context section.
- What remains, and any blockers or open questions.

Be faithful. Do not invent progress or results. If something is uncertain or unverified, say so
explicitly. If `${ARGS}` provides a focus hint, weight the handoff toward that area (but still
include enough global context to resume safely).

## Document structure

The handoff document must contain these sections, in order:

1. `# Session Handoff` — followed by a one-line statement of the objective.
2. **Resume instructions** — a short preamble addressed to the receiving agent: read this whole
   document, restore the context, verify the current state against the actual repo before acting,
   and continue from "Next Steps" without redoing completed work.
3. **Task / Intent** — what the user wants, in their words where it matters.
4. **Background & Discussion** — relevant context and how the approach evolved.
5. **Decisions** — choices made, with rationale; rejected options noted.
6. **Research & Findings** — key facts, discoveries, and gotchas, with paths/links.
7. **Plan / Approach** — the agreed strategy.
8. **Work Completed** — concrete changes so far, each with file paths.
9. **Current State** — branch, staged/unstaged files, recent + unpushed commits, build/test status.
10. **Next Steps** — ordered, actionable remaining work.
11. **Open Questions / Blockers** — anything needing user input or still unresolved.
12. **Key Files & References** — a quick index of the important paths.

Omit a section only if it is genuinely empty (e.g. no blockers); never pad with filler.

## Output rules (important)

- Emit the **entire** handoff as ONE fenced code block so the user can copy it in a single
  selection. After the block, add at most one short line (e.g. "Copy the block above into a fresh
  agent to resume.") — nothing else of substance.
- The handoff body itself contains markdown, including triple-backtick code blocks. To keep it as
  a single copyable block, wrap the whole thing in a **four-backtick fence** (` ```` `) so inner
  ` ``` ` blocks do not terminate it early. Example shape:

````
```` 
# Session Handoff
> Objective: <one line>

## Resume instructions
You are picking up an in-progress session. Read this entire document, restore the
context, verify the current state against the repo, then continue from "Next Steps".
Do not redo work listed under "Work Completed".

## Task / Intent
...

## Work Completed
- Added `src/foo/bar.py:42` — handles X. Example:

  ```python
  def bar():
      ...
  ```

## Current State
- Branch: `feature/x`
- Uncommitted: `src/foo/bar.py`
...

## Next Steps
1. ...
````
````

- The block must be **self-contained**: no references to "see above", "as discussed", or chat
  scrollback — the receiving agent has none of that context.
- Use the Context section's git data verbatim for the "Current State" section; flag any value
  that came back as a fallback (e.g. `NOT_IN_GIT`, `NO_UPSTREAM_OR_NONE`).

## Examples

- `/handoff` — summarize the full session into a portable handoff block.
- `/handoff focus on the database migration work` — emphasize that area while still capturing
  enough global context to resume safely.
