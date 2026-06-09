---
name: worktree-cleanup
version: 1.0.0
description: >
  Clean up stale git worktrees to reclaim disk space. Detects merged branches,
  deleted remotes, and abandoned worktrees. Rust-aware — reports target/ sizes
  separately. Use when asked to clean up worktrees, reclaim disk space, remove
  stale worktrees, or manage worktree sprawl.
allowed-tools: AskUserQuestion, Bash, Read
model: sonnet
---

## Context

- Arguments: `${ARGS}`
- Main repo root: !`sh -c 'COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) && dirname "$COMMON" || echo "NOT_IN_GIT_REPO"'`
- Default branch: !`sh -c 'ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed "s@^refs/remotes/origin/@@"); echo "${ref:-main}"'`
- Worktree count: !`git worktree list 2>/dev/null | wc -l | xargs`
- Platform: !`uname -s`

**Shell variables** do not persist across Bash tool calls. Re-derive from Context when needed.

# Worktree Cleanup

You analyze git worktrees in the current repo, classify them by safety tier, report disk usage, and interactively clean up stale worktrees. Especially useful for large Rust repos where each worktree has its own `target/` directory (often 1-15 GB).

## Argument Parsing

| Args | Behavior |
|------|----------|
| Empty | Analyze worktrees in the current repo |
| `--dry-run` | Report only, no removals |

If "Main repo root" is "NOT_IN_GIT_REPO" — stop and inform the user.

## Phase 0: Pre-flight

1. Validate the repo context from "Main repo root"
2. Parse `${ARGS}` for `--dry-run` flag
3. Fetch and prune remote tracking refs:

```bash
git fetch --prune origin 2>&1
```

## Phase 1: Discovery

List all worktrees using porcelain format for machine parsing:

```bash
git worktree list --porcelain
```

Parse each record (separated by blank lines) into: `worktree` (path), `HEAD` (sha), `branch` (ref), and optional `locked`/`prunable` flags. The first record is always the main worktree — skip it (it can never be removed).

Handle edge cases:
- `prunable` flag means the directory was already deleted — these need `git worktree prune`
- `detached` means detached HEAD — treat branch as the HEAD sha for display
- If a worktree directory exists but `git -C <path> status` fails, mark it as corrupted

## Phase 2: Analysis

For each non-main worktree, run the classification decision tree. Short-circuit on the first match — do not run expensive checks (merge-base, lsof) if an earlier check already classified the worktree.

### Classification Decision Tree

Run checks in this order:

```
 1. Locked? (porcelain output shows "locked")         → LOCKED
 2. Directory missing? (porcelain shows "prunable")    → PRUNABLE
 3. Dirty state?                                       → ACTIVE
 4. Unpushed commits?                                  → ACTIVE
 5. Active process using directory?                    → ACTIVE
 6. Branch merged to default branch?                   → SAFE
 7. Branch squash-merged to default branch?            → SAFE
 8. Remote tracking branch deleted?                    → LIKELY_SAFE
 9. Last commit older than 30 days?                    → STALE
10. Otherwise                                          → ACTIVE
```

### Check Commands

Use `git --no-optional-locks -C <worktree-path>` for all checks to avoid lock contention with active processes.

**Check 3 — Dirty state:**
```bash
git --no-optional-locks -C <path> status --porcelain 2>/dev/null
```
Non-empty output = dirty. Also check stashes:
```bash
git --no-optional-locks -C <path> stash list 2>/dev/null
```
Non-empty = has stashes (would be lost on removal).

**Check 4 — Unpushed commits:**
```bash
git --no-optional-locks -C <path> log @{upstream}..HEAD --oneline 2>/dev/null
```
Non-empty = unpushed commits. If no upstream is set (command fails), try:
```bash
git --no-optional-locks -C <path> log origin/<default-branch>..HEAD --oneline 2>/dev/null
```

**Check 5 — Active process:**

On macOS (Platform = "Darwin"):
```bash
lsof +d <path> 2>/dev/null | head -5
```
On Linux:
```bash
fuser <path> 2>/dev/null
```
Any output = directory in use. Use `+d` (non-recursive) not `+D` to avoid slow scans of large `target/` directories.

**Check 6 — Branch merged:**

Extract the branch name from the porcelain `branch` field (strip `refs/heads/` prefix):
```bash
git merge-base --is-ancestor <branch-tip> origin/<default-branch>
```
Exit code 0 = merged.

**Check 7 — Squash-merged:**

Only run this if check 6 says NOT merged. Many GitHub workflows use squash-merge, which creates new commits that are not ancestors:
```bash
git cherry origin/<default-branch> <branch-name> 2>/dev/null
```
If ALL output lines are prefixed with `-`, the branch content is upstream (squash-merged). If any line starts with `+`, there are commits not yet upstream.

**Check 8 — Remote branch deleted:**
```bash
git rev-parse --verify refs/remotes/origin/<branch-name> 2>/dev/null
```
Non-zero exit = remote branch no longer exists (was deleted after `git fetch --prune`).

**Check 9 — Staleness:**
```bash
git --no-optional-locks -C <path> log -1 --format=%ct 2>/dev/null
```
Compare the Unix timestamp to current time. Older than 30 days = stale.

### Disk Usage

For each worktree that has a directory on disk, measure size. Run these in a single Bash call to minimize round-trips:

```bash
du -sh <path> 2>/dev/null
du -sh <path>/target 2>/dev/null        # Rust
du -sh <path>/node_modules 2>/dev/null   # Node
du -sh <path>/build 2>/dev/null          # Generic build dir
```

## Phase 3: Report

Present a structured report. Group worktrees by classification tier (SAFE first, then LIKELY_SAFE, PRUNABLE, STALE, ACTIVE, LOCKED).

### Report Format

```
## Worktree Cleanup Report

**Repo:** <main repo root>
**Worktrees:** <count> (excluding main)
**Default branch:** <default branch>

| # | Branch | Class | Total | Build Artifacts | Age | Status |
|---|--------|-------|-------|-----------------|-----|--------|
| 1 | wpfleger/old-feat | SAFE | 3.2 GB | target/: 1.1 GB | 45d | merged |
| 2 | wpfleger/closed-pr | LIKELY_SAFE | 2.8 GB | target/: 940 MB | 30d | remote gone |
| ... | | | | | | |

### Summary

  SAFE:        N worktrees (X GB) — removable with confirmation
  LIKELY_SAFE: N worktrees (X GB) — removable with confirmation
  PRUNABLE:    N worktrees (0 B)  — metadata cleanup only
  STALE:       N worktrees (X GB) — require individual approval
  ACTIVE:      N worktrees (X GB) — will not be removed
  LOCKED:      N worktrees (X GB) — will not be removed

  Total reclaimable (SAFE + LIKELY_SAFE + PRUNABLE): X GB
```

If `--dry-run` is set, output the report and stop: "Dry run complete. No worktrees were removed."

## Phase 4: Cleanup

Skip entirely if `--dry-run` or if there are no SAFE/LIKELY_SAFE/PRUNABLE/STALE worktrees.

### Step 1: PRUNABLE worktrees

These have no directory on disk — only stale git metadata. Clean unconditionally:
```bash
git worktree prune -v
```

### Step 2: SAFE and LIKELY_SAFE batch

If there are SAFE or LIKELY_SAFE worktrees, present them as a batch using `AskUserQuestion`:
- Option 1: "Remove all N (X GB)"
- Option 2: "Select individually"
- Option 3: "Skip"

If "Select individually", present each one and let the user choose.

### Step 3: STALE worktrees

Present each STALE worktree individually using `AskUserQuestion`:
- "Remove `<branch>` (not merged, N days old, X GB)?"
- Option 1: "Remove"
- Option 2: "Skip"

### Step 4: Per-worktree removal

For each worktree approved for removal:

1. Remove the worktree:
```bash
git worktree remove <path>
```
If this fails (git's built-in dirty check catches something the analysis missed), report the failure and skip to the next worktree. Do NOT use `--force`.

2. Delete the local branch. For branches classified as SAFE via ancestor check (check 6):
```bash
git branch -d <branch-name>
```
For branches classified as SAFE via squash-merge detection (check 7), `-d` will fail because git doesn't recognize squash merges as proper merges:
```bash
git branch -D <branch-name>
```
For LIKELY_SAFE and STALE branches, also use `-D` (the remote is already gone or the user explicitly approved).

3. If branch deletion fails, report it but continue — the worktree removal is the important part.

### Step 5: Final cleanup and summary

Run a final prune to clean any remaining metadata:
```bash
git worktree prune -v
```

Present the final summary:
```
## Cleanup Complete

Worktrees removed: N
Branches deleted: N
Space reclaimed: ~X GB
Remaining worktrees: N
```

## Rules

1. **Never remove the main worktree** — skip it in all phases
2. **Never auto-remove with dirty state** — unpushed commits, uncommitted changes, untracked files, or stashes block automatic removal
3. **Never remove locked worktrees** — report them but do not offer removal
4. **Always show the report before any removal** — the user must see the full picture first
5. **Always confirm via AskUserQuestion** — no destructive actions without explicit user approval
6. **Use `git worktree remove`, never `rm -rf`** — ensures git metadata is cleaned atomically
7. **Never use `--force` on `git worktree remove`** — if git's built-in safety check fails, respect it
8. **Batch parallel Bash calls** where possible — run multiple `du`, `git status`, `git log` checks in a single Bash invocation to minimize round-trips

## Examples

- `/worktree-cleanup` — analyze and clean up worktrees in the current repo
- `/worktree-cleanup --dry-run` — report worktree status and disk usage without removing anything
