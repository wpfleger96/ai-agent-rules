---
# This file is managed by ai-agent-rules. Do not edit manually.
# https://github.com/wpfleger96/ai-agent-rules
name: pr-creator
version: 1.2.0
description: Create a GitHub pull request (draft by default) with a concise description derived from the branch's commits and diff. Use when the user asks to open a PR or a pushed branch is ready for review; pass `open` for a non-draft PR.
allowed-tools: AskUserQuestion, Bash, Glob, Grep, Read, TodoWrite
model: sonnet
---

## Context

- Project: !`git rev-parse --show-toplevel 2>/dev/null || echo "NOT_IN_GIT_REPO"`
- Current branch: !`git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "NO_BRANCH"`
- Base branch: !`git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main"`
- Uncommitted changes: !`git status --porcelain 2>/dev/null | wc -l | xargs`
- Remote status: !`git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "NOT_PUSHED"`
- Commits ahead: !`git rev-list --count @{u}..HEAD 2>/dev/null || echo "0"`

# Create GitHub Pull Request

**Usage:** `/pr-creator` - Create draft PR (default) | `/pr-creator open` - Create regular PR

## Pre-flight Checks

**Validate environment:**
1. Check "Project" - if "NOT_IN_GIT_REPO", stop and inform user
2. Check "Current branch" - if "NO_BRANCH", stop and inform user
3. Check "Uncommitted changes" - if > 0, warn user and ask to continue

## Stage 1: Analyze & Generate Draft

### Step 1: Detect Mode

Check `$1` equals "open" → regular PR, else draft PR.

### Step 2: Gather Information

**Inspect changes:**
```bash
git log origin/{base}..HEAD
git diff origin/{base}...HEAD --stat
git diff origin/{base}...HEAD
gh issue list --limit 20  # Search for related open issues
```

**Look for:** External reference IDs in commits/branch name (GitHub issues, Jira tickets, Sentry issues, PagerDuty incidents) | Related open issues via `gh issue list` | Breaking changes | New dependencies | Security changes (auth, validation) | Performance implications

### Step 3: Generate Draft Description

Base the description on the actual diff, not only the commit messages. Verify that referenced issues exist, and derive URLs for external references from context. See `references/templates.md` for the optional shape, issue-reference keywords and an example.

- The PR-description and markdown rules in AGENTS.md apply
- Tone and shape: if the PR goes out under Will's name and `writing-as-will` is installed, follow it. Otherwise, write plain, factual prose scaled to the change
- Specific technical terms, no marketing language
- Plain bullets (`-`), no headers in the body, bold only for the optional review-section labels; issue refs at the end, after a blank line

### Step 4: Verify & Create

**Check for PLAN files:**
```bash
git log origin/{base}..HEAD --name-only --pretty=format: | grep -q "^PLAN" || git ls-files | grep -q "^PLAN"
```

If found: **STOP** - PLAN files are dev docs that shouldn't be in PRs. Provide remediation: Remove PLAN files and amend/rebase OR Create clean branch without PLAN files

**Ensure branch pushed:**
```bash
# If Remote status = "NOT_PUSHED":
git push -u origin HEAD
```

### Create PR

**Title:** conventional commit format, per the PR Titles rule in AGENTS.md. Confirm the base branch is correct.

**Create** (use HEREDOC for formatting):

**Draft (default):**
```bash
gh pr create --title "Title" --base {base} --draft --body "$(cat <<'EOF'
[Full description]
EOF
)"
```

**Regular (`open` override):**
```bash
gh pr create --title "Title" --base {base} --body "$(cat <<'EOF'
[Full description]
EOF
)"
```

**Display PR URL** upon success.

This skill covers PR creation only. After pushing more commits to an existing PR, follow the PR Maintenance rule in AGENTS.md.
