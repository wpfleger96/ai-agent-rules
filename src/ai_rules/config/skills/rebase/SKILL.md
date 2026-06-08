---
name: rebase
version: 1.0.0
description: >
  Rebase a branch onto main (or a target). Squash-first strategy, semantic
  verification of auto-merged files, generated-file regeneration, and safe
  force-push. Use when rebasing PRs or branches that are behind their base.
allowed-tools: Agent, AskUserQuestion, Bash, Edit, Glob, Grep, Read, Write
model: opus
---

## Context

- Arguments: `${ARGS}`
- Project root: !`git rev-parse --show-toplevel 2>/dev/null || echo "NOT_IN_GIT_REPO"`
- Current branch: !`git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "NO_BRANCH"`
- Default base: !`sh -c 'ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed "s@^refs/remotes/origin/@@"); echo "${ref:-main}"'`
- Commits ahead: !`git rev-list --count HEAD --not --remotes 2>/dev/null || echo "unknown"`
- Ecosystem: !`sh -c 'e=""; [ -f Cargo.toml ] && e="${e:+$e,}rust"; [ -f package.json ] && e="${e:+$e,}node"; [ -f pyproject.toml ] && e="${e:+$e,}python"; [ -f go.mod ] && e="${e:+$e,}go"; echo "${e:-unknown}"'`
- Tooling: !`[ -f Justfile ] && echo "just" || { [ -f Makefile ] && echo "make" || echo "none"; }`

## Ecosystem Defaults

Use project tooling (Justfile/Makefile) first. Fall back to these only when no project recipe exists:

| Ecosystem | Build | Lint | Format | Test | Lock Regen |
|---|---|---|---|---|---|
| Rust | `cargo build --workspace` | `cargo clippy --workspace --all-targets -- -D warnings` | `cargo fmt --all` | `cargo test --workspace` | `cargo update` |
| Node | `npm run build` | `npm run lint` | `npm run format` or `npx prettier --write .` | `npm test` | `npm install` |
| Python | `uv build` or `python -m build` | `ruff check .` | `ruff format .` | `pytest` | `uv lock` |
| Go | `go build ./...` | `golangci-lint run` | `gofmt -w .` | `go test ./...` | `go mod tidy` |

**Shell variables** (`TARGET`, `MERGE_BASE`) do not persist across Bash tool calls. Re-derive from Context when needed.

# Rebase Skill

Expert git operator performing safe, semantically-correct rebases. The #1 failure mode in rebases is not merge conflicts — it is **silent semantic breakage after a "clean" auto-merge**. Your primary job is to prevent that.

## Phase 0: Pre-flight Validation

If "Project root" is "NOT_IN_GIT_REPO" or "Current branch" is "NO_BRANCH" or "HEAD" — stop and inform user.

**Resolve target branch from `${ARGS}`:**

| Args | Action |
|---|---|
| Empty | Rebase onto the default base from Context |
| Branch name (e.g. `main`, `upstream/main`) | Rebase onto `origin/<branch>` (fetch ensures it's current) |
| PR URL (`https://github.com/.../pull/123`) | `gh pr view <number> --json baseRefName` to extract base, rebase onto `origin/<base>` |

**Important:** Always rebase onto the remote tracking ref (`origin/<branch>`), not the local branch — `git fetch origin` updates remote refs but not local branches.

For PR URLs, this extracts the PR's base branch (the branch it merges into). To rebase onto another PR's head branch for stacking, provide the branch name directly.

Set `TARGET` to the resolved target ref. Run `git fetch origin` to ensure it's current.

**Pre-flight checks:**
1. `git status --porcelain` — if non-empty, ask user: stash (`git stash push -m "rebase-skill: pre-rebase stash"`) or abort
2. `ls .git/rebase-merge .git/rebase-apply 2>/dev/null` — if either exists, ask user to `git rebase --abort` first
3. `git config rerere.enabled` — if true, warn user: git may silently auto-apply prior conflict resolutions, bypassing Phase 3 review

## Phase 1: Pre-flight Analysis

### 1a. Compute divergence

```bash
MERGE_BASE=$(git merge-base HEAD $TARGET)
git log --oneline $MERGE_BASE..HEAD          # Our commits
git log --oneline $MERGE_BASE..$TARGET       # Commits to rebase over
git diff --name-only $MERGE_BASE..HEAD       # Files WE changed
git diff --name-only $MERGE_BASE..$TARGET    # Files THEY changed
```

Compute: `COMMIT_COUNT` (our commits), `BEHIND_COUNT` (their commits), `OUR_BRANCH_FILES` (files we changed), `THEIR_FILES` (files they changed), `OVERLAP_FILES` (intersection of both).

### 1a-fast. Fast path for simple rebases

If `OVERLAP_FILES` is empty and `BEHIND_COUNT` is small (< 20): skip Phase 1c (structural risk analysis) and Phase 4b (verification subagents). Proceed with a direct rebase followed by build/test verification only.

### 1b. Classify overlapping files

For each file in `OVERLAP_FILES`:

**Generated files** (never manually merge — accept TARGET's version, regenerate after):
- Lock files: `Cargo.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `uv.lock`, `go.sum`
- Schema files: `*.schema.json`, `openapi.json`, `openapi.yaml`, `acp-schema.json`, `acp-meta.json`
- Codegen output: files containing `// This file is auto-generated`, `// DO NOT EDIT`, `/* auto-generated */`, or living in directories named `generated/`
- Protobuf/gRPC: `*.pb.rs`, `*.pb.go`, `*_grpc.rs`
- Heuristic fallback: any file whose first 5 lines contain `auto-generated`, `DO NOT EDIT`, or `@generated`; any `*.lock*` file; any file in a directory named `generated/`, `dist/`, or `build/`

**Hand-written files** — everything else.

### 1c. Detect structural risks on TARGET

Launch ONE Explore subagent to analyze commits from MERGE_BASE to TARGET (substitute actual SHA/ref values — subagents cannot access shell variables):

```
Analyze commits from <MERGE_BASE_SHA> to <TARGET_REF> in <project root>.
Focus on commits touching OUR_BRANCH_FILES or structural files (Cargo.toml, package.json, tsconfig.json, mod.rs, __init__.py, index.ts, lib.rs).

Check for: file renames/moves (--diff-filter=R), file→directory transitions, crate/package renames or splits, type/API renames, namespace changes, function signature changes.

Output a RISK MATRIX:
  FILE | RISK_TYPE | WHAT_CHANGED | IMPACT_ON_OUR_CODE | CONFIDENCE
```

### 1d. Present pre-flight summary

Present to user: TARGET, commit counts, overlapping files (generated vs hand-written), structural risks from the risk matrix. Ask to confirm before proceeding.

**Persist the risk matrix** in full — it's referenced in Phases 3 and 4.

## Phase 2: Squash & Rebase

### 2a. Squash if multiple commits (HARD RULE — no exceptions)

Always squash when `COMMIT_COUNT > 1`. **If `COMMIT_COUNT` is 1, skip to Phase 2b.**

Compute `MERGE_BASE=$(git merge-base HEAD $TARGET)`. Read the branch's commit messages (`git log --reverse --format="%s%n%b" $MERGE_BASE..HEAD`), compose a single commit message following the repo's conventions (check `git log -5 --oneline` for style). Write to a temp file for shell safety.

```bash
git reset --soft $MERGE_BASE
git commit -F <message-file>
```

### 2b. Rebase

Run `git rebase $TARGET`.

## Phase 3: Conflict Resolution

Check `git status` for conflicts after each rebase step.

**Generated files** — accept TARGET's version: `git checkout $TARGET -- <file>` then `git add <file>`.

**Hand-written files** — read conflict markers, consult the risk matrix, use TARGET's new names/paths for renamed types or moved modules, preserve both sides' functional changes.

**When ambiguous** — ask the user. Never guess on conflicts you can't resolve with certainty.

After resolving all files: `git add <resolved files> && git rebase --continue`

Use `GIT_EDITOR=true git rebase --continue` to prevent editor prompts in the agent context.

If another conflict round occurs, repeat. If rebase aborts unexpectedly: `git rebase --abort`, explain, ask user.

## Phase 4: Semantic Verification

**A clean rebase is NOT a correct rebase.** This is the critical differentiator.

### 4a. Identify all branch files

Run `git diff --name-only $TARGET..HEAD`. Every one of these files must be verified — not just the ones that conflicted.

### 4b. Launch parallel verification subagents

Only launch agents for risk categories from the Phase 1 risk matrix. Load the briefing from `references/semantic-verification-template.md` **in this skill's directory**. Launch all applicable agents in a single response:

- **Stale Imports** — if RENAME/MOVE/SPLIT risks
- **Stale API References** — if TYPE/API/NAMESPACE risks
- **Signature Compatibility** — if SIGNATURE risks

Skip if risk matrix was empty.

### 4c. Fix all reported issues

For each finding: read the file, apply the correction, `git add`.

### 4d. Build

Use project tooling. Check Justfile/Makefile first for a build target. Fall back to the Ecosystem Defaults table above.

If build fails: read error, fix, re-run. Repeat until clean.

## Phase 5: Regeneration

### 5a. Regenerate lockfiles

If any lockfile was accepted from TARGET in Phase 3, regenerate it using the package manager (see Ecosystem Defaults table — Lock Regen column). This restores the branch's dependencies that were lost when accepting TARGET's lockfile.

### 5b. Discover and run generators

Check project tooling (just/make/package.json scripts/CI workflows) for targets containing: generate, gen, schema, codegen, or types. Run each using project tooling recipes, not bare commands — recipes often add required feature flags or environment variables.

After each generator: `git add` the regenerated files.

### 5c. Format

Use project tooling or Ecosystem Defaults table above.

### 5d. Amend commit

Stage only regenerated/formatted/fixed files (not `git add -A`). Runs unconditionally to capture Phase 4c changes.

```bash
git add <changed-files>
git commit --amend --no-edit
```

## Phase 6: Final Verification & Push

### 6a. Build

Run build using project tooling or Ecosystem Defaults. This catches compile errors from regeneration before running tests.

### 6b. Tests

Run via project tooling, fall back to ecosystem default (`cargo test`, `npm test`, `pytest`, `go test ./...`).

Build, tests, and lint are independent and can be launched as parallel Bash calls for speed.

If tests fail: determine if it's a regression from our rebase (fix it) or pre-existing (note it, don't fix). Fix regressions, amend, re-test.

### 6c. Final lint pass

One more lint run after regeneration and amendments.

Notable Rust pattern: `needless_borrow` after rebase often means a function changed from returning `T` to `&T`. Our `&var` creates `&&T` — remove the extra `&`.

Fix all lint errors.

### 6d. Summary & push

Present completion summary: branch, target, files changed, verification results (build/lint/tests/semantic checks/regenerated files). Wait for explicit push confirmation, then `git push --force-with-lease origin HEAD`. Never `--force`. If lease fails, report and ask — do NOT retry with `--force`.

If stash was created in Phase 0: `git stash pop` to restore working changes.

## Rules (Never Violate)

1. **Squash before rebase** when branch has >1 commit. No exceptions.
2. **Never manually merge generated files.** Accept TARGET, regenerate.
3. **Always use project tooling** (just/make) over bare commands. Feature flags matter.
4. **Run semantic verification** before declaring success. Clean rebase != correct rebase.
5. **Build must pass** before committing. Never push broken code.
6. **`--force-with-lease`**, never `--force`. Prevents clobbering others' pushes.
7. **Ask before force-pushing.** Always get explicit user confirmation.

## Abort & Cleanup

On abort: `git rebase --abort` if in progress, `git stash pop` the named stash if created in Phase 0, report phase reached and repo state.
