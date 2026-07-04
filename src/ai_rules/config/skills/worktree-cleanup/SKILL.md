---
name: worktree-cleanup
version: 1.1.0
description: >-
  Clean up stale git worktrees to reclaim disk space. Detects merged branches,
  deleted remotes, and abandoned worktrees. Rust-aware (reports target/ sizes
  separately). Use for worktree cleanup or disk reclamation.
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

4. Detect `gh` CLI availability and authentication. Run once; store result for use in check 4:

```bash
gh auth status 2>/dev/null && echo "GH_AVAILABLE" || echo "GH_UNAVAILABLE"
```

Extract the repo slug for later use (skip if `gh` is unavailable):

```bash
git remote get-url origin 2>/dev/null \
  | sed 's/.*github\.com[:/]\(.*\)\.git$/\1/; s/.*github\.com[:/]\(.*\)$/\1/'
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
- Corrupted worktrees (directory exists but git link is broken) are detected in Phase 2 check 3

## Phase 2: Analysis

For each non-main worktree, run the classification decision tree. Short-circuit on the first match — do not run expensive checks (merge-base, lsof) if an earlier check already classified the worktree.

### Classification Decision Tree

Run checks in this order:

```
 1. Locked? (porcelain output shows "locked")                              → LOCKED
 2. Directory missing? (porcelain shows "prunable")                        → PRUNABLE
 3. Corrupted? (directory exists but git rev-parse --git-dir fails)        → CORRUPTED
 4. GitHub PR merged? (skip if gh unavailable or detached HEAD)            → SAFE
    GitHub PR closed?                                                       → LIKELY_SAFE
 5. Dirty state?                                                           → ACTIVE
 6. Unpushed commits?                                                      → ACTIVE
 7. Active process using directory?                                        → ACTIVE
 8. Branch merged to default branch?                                       → SAFE
 9. Branch squash-merged to default branch?                                → SAFE
10. Remote tracking branch deleted?                                        → LIKELY_SAFE
11. Last commit older than 30 days?                                        → STALE
12. Otherwise                                                              → ACTIVE
```

**Why check 4 runs before dirty/unpushed:** A merged PR is the authoritative signal
that work is safely upstream. Dirty state on a merged-PR branch is abandoned artifacts,
not in-progress work — blocking removal on it would be a false positive. See Phase 4
for how dirty SAFE worktrees are handled at removal time.

### Check Commands

Use `git --no-optional-locks -C <worktree-path>` for all checks to avoid lock contention with active processes. Always quote worktree paths in shell commands (e.g., `"<path>"`) to handle paths containing spaces.

**Check 3 — Corrupted:**
```bash
git --no-optional-locks -C <path> rev-parse --git-dir 2>/dev/null
```
Non-zero exit code when the directory exists on disk = corrupted worktree (`.git` file missing or broken link back to main repo). Report in the table as CORRUPTED and require individual approval for removal.

**Check 4 — GitHub PR status:**

Skip this check if: `gh` is unavailable/unauthenticated (from Phase 0 detection), the
worktree is in detached HEAD state (no branch name to query), or the repo slug could
not be determined.

```bash
gh pr list --repo <slug> --state all --head <branch-name> --limit 1 \
  --json state --jq '.[0].state // "NONE"' 2>/dev/null
```

- `MERGED` → **SAFE**. Note in Status column if the worktree is also dirty: `PR #N merged ⚠ dirty`.
- `CLOSED` → **LIKELY_SAFE**. Note if dirty: `PR #N closed ⚠ dirty`.
- `OPEN` → ACTIVE confirmed — continue to check 5.
- `NONE` (empty output) or command failure → continue to check 5.

**Check 5 — Dirty state:**
```bash
git --no-optional-locks -C <path> status --porcelain 2>/dev/null
```
Non-empty output = dirty (uncommitted changes, staged changes, or untracked files).

**Check 6 — Unpushed commits:**
```bash
git --no-optional-locks -C <path> log @{upstream}..HEAD --oneline 2>/dev/null
```
Non-empty = unpushed commits → ACTIVE. If this command fails (no upstream set), try the fallback:
```bash
git --no-optional-locks -C <path> log origin/<default-branch>..HEAD --oneline 2>/dev/null
```
Check the **exit code** of the fallback: if non-zero (default branch ref doesn't exist or other failure), treat as "unpushed status unknown" → classify ACTIVE. If exit code is zero and output is empty, the branch has no unpushed commits — continue to check 7. This ordering is intentionally conservative: unknown status defaults to ACTIVE.

**Check 7 — Active process:**

On macOS (Platform = "Darwin"):
```bash
lsof +d <path> 2>/dev/null | head -5
lsof +d <path>/.git 2>/dev/null | head -5
```
On Linux:
```bash
fuser <path> 2>/dev/null
```
Any output = directory in use. `+d` checks only the specified directory, not subdirectories — processes with files open deeper in the tree are not detected. This is a deliberate tradeoff: `+D` (recursive) is prohibitively slow on worktrees with large `target/` directories. The `.git` check catches git lock files held by active agent sessions. The `git worktree remove` safety check in Phase 4 (without `--force`) is the true safety net for dirty state.

**Check 8 — Branch merged:**

Extract the branch name from the porcelain `branch` field (strip `refs/heads/` prefix). For detached HEAD worktrees, use the HEAD sha from porcelain output:
```bash
git merge-base --is-ancestor <branch-tip> origin/<default-branch>
```
Exit code 0 = merged.

**Check 9 — Squash-merged:**

Only run this if check 8 says NOT merged. For detached HEAD worktrees (no branch name), skip this check — fall through to check 10. Many GitHub workflows use squash-merge, which creates new commits that are not ancestors:
```bash
git cherry origin/<default-branch> <branch-name> 2>/dev/null
```
**`<branch-name>` is the LOCAL branch name (strip `refs/heads/` prefix from the
porcelain `branch` field) — NOT `origin/<branch-name>`.** Using `origin/<branch-name>`
silently errors when the remote has been deleted, causing a false fall-through to ACTIVE.

If output is **empty**, this check is inconclusive — fall through to check 10. If ALL non-empty output lines are prefixed with `-`, the branch content is upstream (squash-merged). If any line starts with `+`, there are commits not yet upstream.

**Check 10 — Remote branch deleted:**

For detached HEAD worktrees (no branch name), skip this check — fall through to check 11.
```bash
git rev-parse --verify refs/remotes/origin/<branch-name> 2>/dev/null
```
Non-zero exit = remote branch no longer exists (was deleted after `git fetch --prune`).

**Check 11 — Staleness:**
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
**GitHub PR checks:** enabled | disabled (gh not available)

| # | Branch | Class | Total | Build Artifacts | Age | PR | Status |
|---|--------|-------|-------|-----------------|-----|----|--------|
| 1 | alice/old-feat | SAFE | 3.2 GB | target/: 1.1 GB | 45d | #42 MERGED | merged |
| 2 | alice/dirty-merged | SAFE | 1.4 GB | N/A | 3d | #51 MERGED | PR merged ⚠ dirty |
| 3 | alice/closed-pr | LIKELY_SAFE | 2.8 GB | target/: 940 MB | 30d | #38 CLOSED | remote gone |
| 4 | alice/no-pr | LIKELY_SAFE | 400 MB | N/A | 35d | — | remote gone |
| ... | | | | | | | |

For PRUNABLE worktrees (directory already deleted), show N/A for Total and Build Artifacts columns.
For the PR column, show "—" when no PR was found or gh is unavailable.

### Summary

  SAFE:        N worktrees (X GB) — removable with confirmation
  LIKELY_SAFE: N worktrees (X GB) — removable with confirmation
  PRUNABLE:    N worktrees (0 B)  — metadata cleanup only
  CORRUPTED:   N worktrees (X GB) — require individual approval
  STALE:       N worktrees (X GB) — require individual approval
  ACTIVE:      N worktrees (X GB) — will not be removed
  LOCKED:      N worktrees (X GB) — will not be removed

  Auto-reclaimable (SAFE + LIKELY_SAFE + PRUNABLE): X GB
  Reclaimable with individual approval (STALE + CORRUPTED): X GB
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

### Step 3: STALE and CORRUPTED worktrees

Present each STALE or CORRUPTED worktree individually using `AskUserQuestion`:
- "Remove `<branch>` (not merged, N days old, X GB)?" for STALE
- "Remove `<path>` (corrupted worktree, X GB)?" for CORRUPTED
- Option 1: "Remove"
- Option 2: "Skip"

### Step 4: Per-worktree removal

For each worktree approved for removal:

1. Remove the worktree. The command depends on whether the worktree has dirty state:

   **Clean worktrees** (normal case):
   ```bash
   git worktree remove <path>
   ```
   If this fails (git's built-in dirty check catches something the analysis missed), report the failure and skip to the next worktree. Do NOT use `--force`.

   **Dirty SAFE worktrees** (classified SAFE via merged-PR check, check 4):
   ```bash
   git worktree remove --force <path>
   ```
   Use `--force` only when the worktree was explicitly classified SAFE because its PR is confirmed merged — these uncommitted changes are abandoned artifacts on a merged branch. Never use `--force` for STALE, CORRUPTED, or LIKELY_SAFE worktrees.

2. Delete the local branch. If the worktree was in detached HEAD state, skip branch deletion — there is no branch to delete. For branches classified as SAFE via ancestor check (check 8):
```bash
git branch -d <branch-name>
```
For branches classified as SAFE via squash-merge detection (check 9) or GitHub PR (check 4), `-d` will fail because git doesn't recognize squash merges as proper merges:
```bash
git branch -D <branch-name>
```
For LIKELY_SAFE, STALE, and CORRUPTED branches, also use `-D` (the remote is already gone or the user explicitly approved).

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
2. **Never auto-remove ACTIVE worktrees** — open PRs, unpushed commits, or uncommitted changes that reached check 5 (i.e., not overridden by a merged PR in check 4) block automatic removal
3. **Never remove locked worktrees** — report them but do not offer removal
4. **Always show the report before any removal** — the user must see the full picture first
5. **Always confirm via AskUserQuestion** — no destructive actions without explicit user approval
6. **Use `git worktree remove`, never `rm -rf`** — ensures git metadata is cleaned atomically
7. **`--force` only for merged-PR dirty worktrees** — use `git worktree remove --force` only when a worktree is classified SAFE via check 4 (confirmed-merged GitHub PR) and has dirty state; never use `--force` for any other classification
8. **Batch parallel Bash calls** where possible — run multiple `du`, `git status`, `git log` checks in a single Bash invocation to minimize round-trips

## Abort & Recovery

If the user cancels mid-cleanup or an unexpected error occurs:
1. Run `git worktree prune -v` to clean any orphaned metadata
2. Report: how many worktrees were successfully removed, which removals were skipped, and that the repo is in a consistent state
3. The repo is always safe — `git worktree remove` (without `--force`) either completes atomically or fails without side effects

## Examples

- `/worktree-cleanup` — analyze and clean up worktrees in the current repo
- `/worktree-cleanup --dry-run` — report worktree status and disk usage without removing anything
