---
name: dev-docs
version: 1.0.1
description: Creates or updates PLAN.md based on session - auto-detects create vs update mode
allowed-tools: AskUserQuestion, Bash, Edit, Glob, Grep, Read, TodoWrite, Write
model: sonnet
---

## Context

- Main repo root: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && dirname "$COMMON" || echo "NOT_IN_GIT_REPO"'`
- Project root: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); if [ -z "$COMMON" ]; then echo "NOT_IN_GIT_REPO"; exit 0; fi; MAIN_ROOT=$(dirname "$COMMON"); WT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); CWD_PATH=$(pwd); REL="${CWD_PATH#"$WT_ROOT"}"; REL="${REL#/}"; if [ -z "$REL" ]; then echo "$MAIN_ROOT"; else echo "$MAIN_ROOT/$REL"; fi'`
- PLAN files: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); if [ -z "$COMMON" ]; then echo "NOT_IN_GIT_REPO"; exit 0; fi; MAIN_ROOT=$(dirname "$COMMON"); WT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); CWD_PATH=$(pwd); REL="${CWD_PATH#"$WT_ROOT"}"; REL="${REL#/}"; if [ -z "$REL" ]; then PROJECT_ROOT="$MAIN_ROOT"; else PROJECT_ROOT="$MAIN_ROOT/$REL"; fi; found=""; cd "$PROJECT_ROOT" && for f in PLAN__*.md; do [ -f "$f" ] && echo "$f" && found=1; done; if [ -z "$found" ]; then [ -f PLAN.md ] && echo "LEGACY_PLAN" || echo "NO_PLAN_FILES"; fi' 2>/dev/null | sed 's/PLAN__//;s/\.md$//' | paste -sd ',' -`
- Worktree/CWD: !`pwd`
- Last commit: !`git log -1 --format="%h %ai %s" 2>/dev/null || echo "NO_COMMITS"`

# Create or Update Development Documentation

Automatically creates task-specific PLAN files (`PLAN__<TASK>.md`) or updates existing ones by analyzing session activity to track implementation progress.

## Task-Specific PLAN Files

**Purpose:** Single source of truth for plans and progress across sessions. A new agent must be able to resume work using ONLY the PLAN file -- no prior session context, no codebase re-exploration for decisions already made.

**Naming Convention:**
- Format: `PLAN__<TASK>.md` (always `PLAN__` with two underscores)
- Task identifier: 1-2 words, uppercase letters only, single underscores between words
- Valid: ✓ `AUTH_FLOW`, ✓ `API_MIGRATION`, ✓ `SLACK_FORMATTING`
- Invalid: ✗ `auth_flow` (lowercase), ✗ `AUTH__FLOW` (double underscore)

## CRITICAL: File Location

**ALWAYS write PLAN files to the project root, NEVER to a worktree path or ~/.claude/plans/**

- Target path: `{project_root}/PLAN__<TASK>.md`
- `{project_root}` is the "Project root" value from the Context section above

**How project root is resolved:**

The project root combines `--git-common-dir` (main repo root, worktree-safe) with `--show-toplevel` (current working tree root) to compute the correct target:

1. Find the relative path from CWD to the working tree root (`--show-toplevel`)
2. Apply that relative path to the main repo root (`--git-common-dir`)

This handles worktrees (CWD may be inside `<repo>/.worktrees/<name>/`) and monorepos (CWD may be a subdirectory like `<repo>/<app>/`) correctly — including both at once.

| Situation | Main repo root | Worktree/CWD | Project root |
|---|---|---|---|
| Standard repo | `/repos/myapp` | `/repos/myapp` | `/repos/myapp` |
| Worktree | `/repos/myapp` | `/repos/myapp/.worktrees/feat` | `/repos/myapp` |
| Monorepo | `/repos/mono` | `/repos/mono/builderbot-slack` | `/repos/mono/builderbot-slack` |
| Worktree + monorepo | `/repos/mono` | `/repos/mono/.worktrees/feat/builderbot-slack` | `/repos/mono/builderbot-slack` |

**Never use:**
- A worktree path (e.g., `<repo>/.worktrees/<name>/`) as the PLAN file location
- `~/.claude/plans/` — this is Claude Code's internal storage, unrelated to this skill
- The monorepo root when CWD is an app subdirectory within it

## Phase 1: Determine Mode

Use pre-executed context:

**Check "PLAN files":**
- `NO_PLAN_FILES` → **Create mode**: Extract plan from ExitPlanMode
- `LEGACY_PLAN` → **Legacy migration**: Rename PLAN.md to PLAN__<TASK>.md
- Single task → **Update mode**: Work with that file
- Multiple tasks → **Disambiguate**: Determine which task or create new

## Phase 2: Extract Plan & Evidence

### For Create Mode

⚠️ **ANTI-RECENCY BIAS**: Recent work dominates attention. The FIRST ExitPlanMode has the complete vision. Document ALL work (completed, current, AND future).

**Extract plans:**
1. Find ALL ExitPlanMode calls in session
2. Extract each in chronological order
3. **CRITICAL**: Read FIRST call for complete vision
4. **PRESERVE original structure** - match original organization
5. Synthesize complete plan ensuring ALL items captured
6. Generate task name from main theme

**Search for implementation evidence:**
1. Review activity after last ExitPlanMode
2. Find: Write/Edit/Bash/TodoWrite calls, completion phrases
3. Map tasks to evidence via file paths and keywords

**Assign statuses:**
- Strong evidence → [DONE]
- Medium evidence → [IN PROGRESS]
- Weak/no evidence → [TODO]

### For Update Mode

1. Read `PLAN__<TASK>.md`, parse task hierarchy with statuses
2. Search recent activity for implementation evidence
3. Match tasks to evidence, assign status updates
4. Check for plan evolution: ExitPlanMode newer than PLAN file

## Phase 3: Write or Update File

See `references/templates.md` for PLAN.md structure.

### Create Mode

Generate PLAN__<TASK>.md with:
- Overview: 1-2 paragraph summary including architectural approach and key design decisions (with reasoning)
- Scope: Features, components, files with role descriptions (what each file does in context of this plan)
- Purpose: Problem, value, requirements, and relevant constraints or limitations discovered
- Implementation Details: Hierarchical tasks with [STATUS], each containing enough detail for a new agent to implement without re-exploring the codebase (include HOW, not just WHAT)

Write to `{project_root}/PLAN__<TASK>.md` and **validate**:
- Compare structure to FIRST ExitPlanMode
- Count items: original N items should match generated
- Future work documented as [TODO], not omitted
- Task name format valid

### Update Mode

Update `PLAN__<TASK>.md`:
- Use Edit tool for each status change
- Match exact old_string with indentation
- Preserve hierarchy and formatting

Handle plan evolution if detected:
- Add new areas to existing structure
- Mark deprecated as `[CANCELLED - plan changed]`
- Update Scope/Purpose if changed

## Cold-Start Resumption Requirement

Every PLAN file must be self-contained enough for a new agent to resume work without prior session context. When writing or updating, verify:

- **Architectural context**: Key design decisions and WHY they were made (not just what was chosen, but what was rejected and why)
- **Task detail**: Each [TODO] task describes HOW to implement, not just WHAT to implement -- include approach, relevant patterns, and target file paths
- **Dependencies**: Tasks that must be completed in order are explicitly noted (e.g., "depends on Phase 1 completing" or "must run after database migration")
- **Gotchas**: Any pitfalls, constraints, or non-obvious behaviors discovered during implementation are captured in the Gotchas section with enough detail to avoid re-discovery
- **File roles**: The Scope section explains what each file does in the context of this plan, not just that it was modified
- **Design narrative**: The plan tells a coherent story — WHY this work exists, what research informed the approach, what alternatives were rejected and why. A new agent should understand the human intent behind the work, not just the task list. Implementation details without motivating context produce shallow, misguided code.

## Content Preservation Rules

PLAN files accumulate institutional knowledge. The design narrative — the WHY behind decisions — is more valuable than the task tracking. Agents naturally focus on WHAT to change and forget WHY, which leads to incomplete or misguided implementations when they lack the human semantic intent behind the work.

**Design narrative (NEVER remove — only annotate or add forward pointers):**
- Goals, motivations, and the problem being solved
- Research findings (what was learned about external systems, APIs, constraints)
- Architecture decisions, rejected alternatives, and trade-off analysis
- Reference tables (config mappings, routing tables, compatibility matrices)
- Gotchas and issues encountered
- Any content explaining WHY a decision was made

**Tracking artifacts (CAN be relocated between PLAN files):**
- Task checklists with [TODO]/[DONE] statuses
- Dependency graphs and blocker lists
- Verification checklists

**The test:** If removing content would force a future reader to re-discover a decision, re-research an external system, or lose understanding of the human intent behind the work — that content must stay.

When restructuring (moving sections to a new PLAN file, consolidating, or splitting): keep all design narrative in the original location, add forward pointers for tracking, and duplicate design context into the new file for cold-start self-containment. Intentional overlap between files is correct.

## Status Transitions & Evidence Strength

**Evidence Strength:**
- Strong: Multiple indicators → [DONE]
- Medium: Single indicator → [IN PROGRESS]
- Weak/None → [TODO]

**Valid Status Labels:**
- [TODO] → Not started
- [IN PROGRESS] → Started not finished
- [DONE] → Completed
- [BLOCKED] → Cannot proceed (include reason)
- [CANCELLED - plan changed] → No longer relevant

## Critical Requirements

**All Modes:**
- Analyze session activity for evidence
- Match ALL tasks to evidence, assign statuses intelligently
- Include evidence-free tasks as [TODO] - never skip planned work
- Use 3-space indentation, preserve hierarchy
- Verify PLAN file passes cold-start test: could a new agent resume work using only this file?
- NEVER remove design narrative (goals, research, architecture decisions, reference tables) — see Content Preservation Rules

**Create Mode:**
- **PREVENT RECENCY BIAS**: Prioritize FIRST ExitPlanMode
- **PRESERVE STRUCTURE**: Match original organization exactly
- Document entire plan regardless of progress
- Generate valid task name, create in project root (NEVER in worktree path or ~/.claude/plans/)

**Update Mode:**
- Use Edit tool with exact matching
- Handle evolution: add new, mark deprecated as cancelled

See `references/templates.md` for detailed PLAN.md structure and examples.
