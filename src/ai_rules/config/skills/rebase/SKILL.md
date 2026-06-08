---
name: rebase
version: 1.0.0
description: >
  Rebase a branch onto main (or a target). Squash-first strategy, semantic
  verification of auto-merged files, generated-file regeneration, and safe
  force-push. Use when rebasing PRs or branches that are behind their base.
allowed-tools: Agent, AskUserQuestion, Bash, Edit, Read, Write
model: opus
---

## Context

- Arguments: `${ARGS}`
- Project root: !`git rev-parse --show-toplevel 2>/dev/null || echo "NOT_IN_GIT_REPO"`
- Current branch: !`git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "NO_BRANCH"`
- Default base: !`git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main"`
- Commits ahead: !`git rev-list --count HEAD --not --remotes 2>/dev/null || echo "unknown"`
- Ecosystem: !`[ -f Cargo.toml ] && echo "rust" || { [ -f package.json ] && echo "node" || { [ -f pyproject.toml ] && echo "python" || { [ -f go.mod ] && echo "go" || echo "unknown"; }; }; }`
- Tooling: !`[ -f Justfile ] && echo "just" || { [ -f Makefile ] && echo "make" || echo "none"; }`

# Rebase Skill

Expert git operator performing safe, semantically-correct rebases. The #1 failure mode in rebases is not merge conflicts — it is **silent semantic breakage after a "clean" auto-merge**. Your primary job is to prevent that.

## Phase 0: Pre-flight Validation

If "Project root" is "NOT_IN_GIT_REPO" or "Current branch" is "NO_BRANCH" or "HEAD" — stop and inform user.

**Resolve target branch from `${ARGS}`:**

| Args | Action |
|---|---|
| Empty | Rebase onto the default base from Context |
| Branch name (e.g. `main`, `upstream/main`) | Rebase onto that branch |
| PR URL (`https://github.com/.../pull/123`) | `gh pr view <number> --json baseRefName` to extract base, rebase onto `origin/<base>` |

Set `TARGET` to the resolved target ref. Run `git fetch origin` to ensure it's current.

**Check working tree:**
```bash
git status --porcelain
```
If non-empty — ask user: stash, or abort. Do not proceed with uncommitted changes.

## Phase 1: Pre-flight Analysis

### 1a. Compute divergence

```bash
MERGE_BASE=$(git merge-base HEAD $TARGET)
git log --oneline $MERGE_BASE..HEAD          # Our commits
git log --oneline $MERGE_BASE..$TARGET       # Commits to rebase over
git diff --name-only $MERGE_BASE..HEAD       # Files WE changed
git diff --name-only $MERGE_BASE..$TARGET    # Files THEY changed
```

Compute: `COMMIT_COUNT` (our commits), `BEHIND_COUNT` (their commits), `OVERLAP_FILES` (files both sides touched).

### 1b. Classify overlapping files

For each file in `OVERLAP_FILES`:

**Generated files** (never manually merge — accept TARGET's version, regenerate after):
- Lock files: `Cargo.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `uv.lock`, `go.sum`
- Schema files: `*.schema.json`, `openapi.json`, `openapi.yaml`, `acp-schema.json`, `acp-meta.json`
- Codegen output: files containing `// This file is auto-generated`, `// DO NOT EDIT`, `/* auto-generated */`, or living in directories named `generated/`
- Protobuf/gRPC: `*.pb.rs`, `*.pb.go`, `*_grpc.rs`

**Hand-written files** — everything else.

### 1c. Detect structural risks on TARGET

This is the most critical intelligence-gathering step. Launch ONE Explore subagent:

```
Analyze commits from $MERGE_BASE to $TARGET in <project root>.
Focus ONLY on commits touching files in OUR_BRANCH_FILES or structural files
(Cargo.toml, package.json, tsconfig.json, mod.rs, __init__.py, index.ts, lib.rs).

For each relevant commit, check for:

1. FILE RENAMES/MOVES
   git log $MERGE_BASE..$TARGET --diff-filter=R --name-status --find-renames
   
2. FILE → DIRECTORY TRANSITIONS
   Deletion of foo.rs + creation of foo/mod.rs

3. CRATE/PACKAGE RENAMES OR SPLITS
   Cargo.toml [package] name changes, new crates created from old ones,
   re-export patterns (pub use new_crate::module)

4. TYPE/API RENAMES
   pub struct/fn/const/type renamed in files we also touch

5. NAMESPACE CHANGES
   Route prefixes, module path restructuring

6. SIGNATURE CHANGES
   Functions we call that changed return type, borrow semantics, or parameters

Output a RISK MATRIX:
  FILE | RISK_TYPE | WHAT_CHANGED | IMPACT_ON_OUR_CODE | CONFIDENCE
```

### 1d. Present pre-flight summary

```
## Rebase Pre-flight

Target: <TARGET>
Our commits: <N> | Behind: <M>
Overlapping files: <count> (generated: <n>, hand-written: <m>)

Structural risks:
  <risk matrix entries, or "None detected">

Strategy: squash to 1 commit, then rebase
```

Ask user to confirm before proceeding.

## Phase 2: Squash & Rebase

### 2a. Squash if multiple commits (HARD RULE — no exceptions)

Resolving a conflict once on 1 commit is strictly better than resolving it N times across N commits. Always squash when `COMMIT_COUNT > 1`.

```bash
MERGE_BASE=$(git merge-base HEAD $TARGET)
```

Read the branch's commit messages (`git log --reverse --format="%s%n%b" $MERGE_BASE..HEAD`), compose a single commit message following the repo's conventions (check `git log -5 --oneline` for style).

```bash
git reset --soft $MERGE_BASE
git commit -s -m "<composed message>"
```

### 2b. Rebase

```bash
git rebase $TARGET
```

## Phase 3: Conflict Resolution

Check `git status` for conflicts after each rebase step.

**Generated files** — accept TARGET's version:
```bash
git checkout $TARGET -- <file>
git add <file>
```

**Hand-written files** — intelligent merge:
1. Read conflict markers (both sides + base)
2. Consult the risk matrix for this file
3. If TARGET renamed a type/module our code uses → use the NEW name
4. If TARGET moved a module → update our import paths to the new location
5. Preserve BOTH sides' functional changes

**When ambiguous** — ask the user. Never guess on conflicts you can't resolve with certainty.

After resolving all files: `git add <resolved files> && git rebase --continue`

If another conflict round occurs, repeat. If rebase aborts unexpectedly: `git rebase --abort`, explain, ask user.

## Phase 4: Semantic Verification

**This phase runs after a "successful" rebase. A clean rebase is NOT a correct rebase.** This is the critical differentiator.

### 4a. Identify all branch files

```bash
git diff --name-only $TARGET..HEAD
```

Every one of these files must be verified — not just the ones that conflicted.

### 4b. Launch parallel verification subagents

Only launch agents for risk categories that appeared in the Phase 1 risk matrix. Load the briefing approach from `references/semantic-verification-template.md`. Launch all applicable agents in a single response for parallelism.

**Agent: Stale Imports** (if risk matrix has RENAME/MOVE/SPLIT entries)
Check every branch file for import/use paths referencing old crate names, old module paths, or old file locations. For Rust: `use old_crate::`, Cargo.toml deps. For Node: `import from 'old/path'`. For Python: `from old.module import`.

**Agent: Stale API References** (if risk matrix has TYPE/API/NAMESPACE entries)
Grep branch files for old type/function/constant names from the risk matrix. Report each stale usage with file, line, old reference, and correct replacement.

**Agent: Signature Compatibility** (if risk matrix has SIGNATURE entries)
For each changed function signature, find our call sites and verify they match the new signature (borrow semantics, argument count, field names).

If the risk matrix was empty (no structural risks detected), skip subagents — proceed directly to the build check.

### 4c. Fix all reported issues

For each finding: read the file, apply the correction, `git add`.

### 4d. Build

Use project tooling. Check Justfile/Makefile first for a build target. Fall back to ecosystem default:

| Ecosystem | Fallback |
|---|---|
| Rust | `cargo build --workspace` |
| Node | `npm run build` |
| Python | `uv build` or `python -m build` |
| Go | `go build ./...` |

If build fails: read error, fix, re-run. Repeat until clean.

### 4e. Lint

| Ecosystem | Fallback |
|---|---|
| Rust | `cargo clippy --workspace --all-targets -- -D warnings` |
| Node | `npm run lint` |
| Python | `ruff check .` |
| Go | `golangci-lint run` |

Notable Rust pattern: `needless_borrow` after rebase often means a function changed from returning `T` to `&T`. Our `&var` creates `&&T` — remove the extra `&`.

Fix all lint errors.

## Phase 5: Regeneration

### 5a. Discover generators

1. `just --list 2>/dev/null` — targets containing: generate, gen, schema, openapi, codegen, types
2. `grep -E '^[a-zA-Z_-]+:' Makefile 2>/dev/null` — same keywords
3. Read `package.json` scripts for: generate, codegen, schema, build:types
4. Check `.github/workflows/*.yml` for generation steps — these reveal canonical commands with correct flags

### 5b. Regenerate

Run each discovered generator using project tooling (Justfile/Makefile recipe, not bare commands). **Never substitute a bare compiler command for a project recipe** — recipes often add required feature flags, environment variables, or pre/post steps that change the output.

After each generator: `git add` the regenerated files.

### 5c. Format

| Ecosystem | Fallback |
|---|---|
| Rust | `cargo fmt --all` |
| Node | `npm run format` or `npx prettier --write .` |
| Python | `ruff format .` |
| Go | `gofmt -w .` |

### 5d. Amend commit

```bash
git add -A
git commit --amend --no-edit
```

## Phase 6: Final Verification & Push

### 6a. Tests

Run via project tooling, fall back to ecosystem default (`cargo test`, `npm test`, `pytest`, `go test ./...`).

If tests fail: determine if it's a regression from our rebase (fix it) or pre-existing (note it, don't fix). Fix regressions, amend, re-test.

### 6b. Final lint pass

One more lint run after regeneration and amendments.

### 6c. Summary & push

Present to user:
```
## Rebase Complete

Branch: <branch> onto <TARGET>
Commits: 1 (squashed from <N>)
Files changed: <count>

Verification:
  Build: passed
  Lint: passed
  Tests: passed (or "N pre-existing failures noted")
  Semantic checks: <N issues fixed | clean>
  Regenerated: <list of generators run>

Ready to force-push.
```

Wait for explicit confirmation. Then:
```bash
git push --force-with-lease origin HEAD
```

Use `--force-with-lease`, never `--force`. If lease fails (someone else pushed), report it and ask — do NOT retry with `--force`.

If stash was created in Phase 0: `git stash pop` after push.

## Rules (Never Violate)

1. **Squash before rebase** when branch has >1 commit. No exceptions.
2. **Never manually merge generated files.** Accept TARGET, regenerate.
3. **Always use project tooling** (just/make) over bare commands. Feature flags matter.
4. **Run semantic verification** before declaring success. Clean rebase != correct rebase.
5. **Build must pass** before committing. Never push broken code.
6. **`--force-with-lease`**, never `--force`. Prevents clobbering others' pushes.
7. **Ask before force-pushing.** Always get explicit user confirmation.
