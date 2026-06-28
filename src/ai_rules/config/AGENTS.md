# LLM Behavioral Rules

## Quick Reference Checklist

**Before completing tasks:**
☐ Worktree for code changes | ☐ Create TODO list (multi-step) | ☐ Security checklist (external input) | ☐ Use project tooling (make/just/npm) | ☐ Test behavior not implementation | ☐ AWS: --profile & --region | ☐ Keep simple (9/10 minimalism/elegance/correctness) | ☐ Ask clarifying questions | ☐ GitHub: git pull, then explore locally | ☐ Cross-reference stacked/related PRs | ☐ Config issues → Personal Infrastructure table

---

## Personal Infrastructure

**Rule:** When debugging config, shell, git, editor, or agent behavior issues, check the relevant source repo before guessing or asking the user.

| Issue area | Source repo | Path | Deployment |
|------------|-------------|------|------------|
| AI agent configs (AGENTS.md, settings, MCP servers, hooks, skills, profiles) | `ai-rules` | `~/Development/Personal/ai-rules` | Symlinks — editing the live file modifies the source directly. CLI: `ai-agent-rules`. |
| Shell/terminal, git global config, editor settings (VS Code, Cursor), SSH signing, AI agent binary installs | `shell-configs` | `~/Development/Personal/shell-configs` | Managed section injection — NOT symlinks. Delimited blocks inside config files are overwritten on `shell-configs install`; content outside blocks persists. CLI: `shell-configs`. |
| Claude Code statusline (model, tokens, cost, git branch bar) | `claude-code-status-line` | `~/Development/Personal/claude-code-status-line` | Wired into `~/.claude/settings.json`. |
| GitHub repo settings (branch protection, merge rules, labels, Renovate) | `github-config` | `~/Development/Personal/github-config` | Declarative YAML manifests applied via `gh-infra`. |
| `gh-infra` fork workflow | `gh-infra` | `~/Development/Personal/gh-infra` | Fork of `babarot/gh-infra`. `origin` = `wpfleger96/gh-infra`, `upstream` = `babarot/gh-infra`. See fork workflow section below. |
| `enpass-cli` fork workflow | `enpass-cli` | `~/Development/enpass-cli` | Fork of `hazcod/enpass-cli`. `origin` = `wpfleger96/enpass-cli`, `upstream` = `hazcod/enpass-cli`. See fork workflow section below. |

---

### Fork Workflows

**Rule:** When making changes to gh-infra or enpass-cli, always follow the fork workflow — never commit directly to `dev`.

- After pushing a fix to a PR branch, also merge it into `dev` so dogfooding picks it up immediately:
  ```
  git checkout dev && git merge wpfleger96/<type>/<slug> --no-ff -m "chore: merge <slug> into dev" && git push origin dev
  ```
- `dev` has dev-only content (its own AGENTS.md with deeper context) that must never go upstream
- For fixes that touch code only on `dev` (not yet in upstream), stack the PR branch on the relevant upstream PR branch — GitHub recomputes diffs dynamically once the base PR merges

| | gh-infra | enpass-cli |
|---|---|---|
| Path | `~/Development/Personal/gh-infra` | `~/Development/enpass-cli` |
| Upstream | `babarot/gh-infra` | `hazcod/enpass-cli` |
| PR target | `main` | `master` |
| Build | `go build -o gh-infra ./cmd/gh-infra/` | `make build` |
| Trailers | None (maintainer identity) | Standard rules apply |

---

## Core Principles

### Security-First Code Generation
**Rule:** For code handling external input, auth, or sensitive data:
**Stage 1:** Implement functional requirements
**Stage 2:** Security checklist: Input validation | SQL injection prevention (parameterized queries) | XSS blocking (output encoding) | Auth/authz checks | Rate limiting | Sanitized errors | No secrets | Audit logging

### Workflow Management
**Rule:** Create TODO list before starting tasks, update as you complete each task.

### Mandatory Worktree for Code Changes

**Rule:** Always create and work inside a git worktree before making any file changes. Never edit files directly in the repo root on the default branch.

**Applies:** Any task that edits, creates, or deletes files — features, bug fixes, refactors, config changes, documentation edits.

**Does NOT apply:** Read-only sessions — research, exploration, planning, code review without edits.

**Setup (before touching any file):**

| Agent | Method |
|-------|--------|
| Claude Code | Use `EnterWorktree` tool (creates worktree and switches session directory) |
| Other agents | `git worktree add .worktrees/<worktree-name> -b <branch-name>` from repo root, then `cd` into it |

**Branch naming:** `<username>/<descriptive-slug>` — e.g., `wpfleger/git-worktree-enforcement`.

**Worktree folder naming:** Derive from branch name — replace `/`, `\`, `:` with `-` (matches `_wt_sanitize_dirname`).

**Why:** Concurrent agents need isolated workspaces to avoid conflicting edits.

### Delegation & Multi-Agent Orchestration

**Rule:** Always delegate code implementation to parallel subagents — never write implementation diffs in the orchestrator context. Split by file/concern; one subagent per file or group of files sharing a broken intermediate state.

**Delegate:** All code implementation | Non-implementation when context >50% of window | Independent parallel subtasks
**Inline:** Single-line mechanical | Sequential-dependent | Ambiguous (clarify first)

**Subagent briefing (self-containment protocol):** Subagents have ZERO access to the parent conversation. Every briefing must include: atomic objective, output format, tool guidance, scope boundaries. Implementation briefings additionally: file ownership list, plan context with interfaces, forbidden files owned by parallel agents.

Analysis tasks: `sonnet` for execution-heavy, `opus` for judgment-heavy.

**Synthesizing results:** Organize by theme not by agent. Surface conflicts explicitly. Convergent findings = strong evidence. Write summary last.

### Project Tooling (CRITICAL - Check BEFORE Running Commands)

**Rule:** ALWAYS check for project-specific tooling files BEFORE executing any build/test/lint command.

**Mandatory check sequence (in order):**
1. **Justfile exists?** → Use `just <task>` commands (e.g., `just test`, `just format`, `just lint`)
2. **Makefile exists?** → Use `make <task>` commands
3. **package.json exists?** → Use `npm run <task>` commands
4. **pyproject.toml exists?** → Use `uv run <tool>` (NEVER direct tool invocation)
5. **Cargo.toml exists?** → Use `cargo <command>`

**Why:** Direct tool invocation bypasses project configuration. The #1 agent mistake.

### Software Engineering Standards

**Clear Naming:** `get_user_by_email(email: str)` not `func1(x)`
**Error Handling:** At boundaries only, specific exceptions
**Input Validation:** Validate ALL user input and external API responses at system boundaries

### Simplicity Over Engineering

**Quality gate (internal — do not print scores):** Before finalizing any implementation, evaluate your work on three dimensions:
- **Minimalism:** Is every line, parameter, and abstraction load-bearing? Try to remove something — if you can without losing correctness, the score is below 9.
- **Elegance:** Does the structure reveal intent on first read? If a senior engineer would need to re-read any part to understand the design, the score is below 9.
- **Correctness:** Are all edge cases handled? Walk through at least two non-happy-path scenarios — if either breaks, the score is below 9.

Iterate until all three are genuinely 9/10. A 9 means you actively tried to find a flaw and could not. If you can still see a way to improve, the score is lower — fix it before proceeding.

### Collaboration Protocol

**Rule:** Verify before assuming. Ask before guessing.

**Workflow:** Understand requirements → Verify assumptions → Clarify unknowns → Propose alternatives → Implement after alignment

**Verification rules (MUST follow):**
- **External/third-party APIs:** NEVER assume an API or service supports a feature without checking docs or asking the user.
- **User environment and business logic:** NEVER assume local setup, installed tools, or domain constraints. Ask or check.
- **Failed operations:** If a tool call, query, or external request fails, STOP and report the failure. NEVER synthesize plausible-looking results and continue as if the operation succeeded.

**When uncertain, ask** — with specific, actionable questions (not "should I proceed?").

---

## Technical Standards

### Testing Standards
**Rule:** Test behavior, NOT implementation.

**Test:** Business logic with branches | Error conditions | Integration points | Security controls | Public APIs
**Skip:** Getters/setters | Framework code | Trivial types | Private details
**Structure:** Arrange-act-assert | Names: `test_<scenario>_<result>` | Independent | Deterministic

### AWS CLI
**Rule:** `--profile <account>-<env>--<role> --region us-west-2`
**Format:** `--profile data-lake-staging--admin` (✅) not `--profile staging-admin` (❌)
**Regex:** `^[a-z-]+-(dev|staging|production)--[a-z-]+$`

### GitHub Integration

**Rule:** When given a GitHub URL (PR, issue, repo), **prefer exploring code locally** over reading it through `gh` CLI. Use `gh` for metadata and quick one-off lookups; use local filesystem for any substantial code exploration.

**Sync before exploring (CRITICAL):** Run `git pull` (or `git fetch origin` + check) in any local repo clone before reading code. GitHub's default branch is the single source of truth — your local clone is a cache that may be days or weeks stale. Skip only when the user explicitly says "look at my local changes" or you are working in your own worktree with in-progress changes.

**Path resolution:** `github.com/<org>/<repo_name>` → `~/Development/<repo_name>`

**Workflow when given PR URLs:**
1. `gh pr view <num> --repo <org>/<repo> --json headRefName` → resolve `~/Development/<repo_name>` → `git pull`
2. Sanitize branch name (`/\:` → `-`) → check `.worktrees/<sanitized_branch>/`, explore there if exists
3. No worktree: correct branch → explore; wrong branch + clean → `git checkout <branch>`; dirty → ask user

### PR Maintenance After Pushing Commits

**Rule:** After pushing to an open PR, re-evaluate title and description. A PR description is a snapshot of what this branch changes vs. main — never a timeline of how it evolved.

After every push: `gh pr view <number> --json title,body` → evaluate if title/description covers ALL commits (not just latest push) → if stale, rewrite from scratch via `gh pr edit`. Also verify the title still uses the correct conventional commit type. Never add "Review fixes" sections — rewrite the full description.

### PR Titles

**Rule:** PR titles must follow the same conventional commit format as commit message subjects — repos use squash merge, so the PR title becomes the squash commit subject line.

**Format:** `<type>(<optional-scope>): <imperative verb> <specific change>` (50-70 chars). Same types and accuracy rules as the Commit Messages section below.

### PR Description Content

**NEVER include a "Test Plan", "Testing", or "Test plan" section in PR descriptions.** CI passing is a gate, not a finding.

**NEVER narrate the development process** — no "after review," "following feedback," "consolidated from," or references to review rounds. Describe the final state only.

**NEVER mention internal workflow tools** (code-reviewer, crossfire, test-writer, etc.) in PR descriptions.

**NEVER append `Claude-Session:` links or agent attribution footers** to PR descriptions or commit messages.

### PR Cross-Referencing

**Rule:** Every PR that is part of a stack or has related PRs (same repo or cross-repo) must explicitly reference all related PRs. No PR description may contain a placeholder, TODO, or "TBD" for a cross-reference when the session ends.

**Stacked PRs (same repo):** Include a stack line showing position:
`Stack: #1 → #2 → this PR → #4`

**Related PRs (cross-repo):** Use fully qualified links:
`Related: [other-repo#45](https://github.com/org/other-repo/pull/45)`

**Sequential creation (critical — agents routinely fail this):** After creating all PRs in a set, use `gh pr edit` to back-fill forward references into earlier PRs. Applies identically to cross-repo sets.

### Commit Messages
**Rule:** Subject states WHAT changed. Body explains WHY -- the problem, motivation, or design decision. Never narrate what's visible in `git show --stat` or the diff itself.

**Subject line:** `<type>(<optional-scope>): <imperative verb> <specific change>` (50-72 chars)

**Type accuracy:**

| Type | Use when | NOT when |
|------|----------|----------|
| `feat:` | Genuinely new functionality or capability | Moving existing code to new files |
| `fix:` | Correcting broken behavior | Refactoring that doesn't fix a bug |
| `refactor:` | Restructuring without behavior change | Adding new features during restructure |
| `docs:` | Documentation-only changes | Code changes with doc updates (use primary type) |
| `chore:` | Dependencies, CI, config, tooling | Anything touching application logic |

**Body (2-4 lines, skip if self-explanatory):** Problem/motivation, design decisions, non-obvious side effects. Test: does the body add info a reviewer can't get from the diff?

### Agent-Authored Commits

**Rule:** When the agent is the git commit author — detected by checking `git config user.name` and confirming it is not the user's name — every commit must include both trailers:

```
Co-authored-by: Will Pfleger <email>
Signed-off-by: Will Pfleger <email>
```

**Discover email:** Run `git log --format="%aN <%aE>" | grep -i "will pfleger" | head -1` in the repo. Never hardcode.

**Why:** `Co-authored-by` ensures proper GitHub attribution. `Signed-off-by` satisfies DCO checks requiring human sign-off on agent-authored commits. Applies to commit messages only — not PR descriptions.

---

## Style & Formatting

### Inline Code in Markdown
**Rule:** Wrap all code identifiers in backticks in user-facing markdown (PR descriptions, docs, issue comments). Scope: env vars, identifiers, file paths, CLI flags, API endpoints, config keys.

```
# ❌ Bare identifiers lost in prose
Set SESSION_ID_MAP_CACHE_MAXSIZE and call configure_goose before /reply.

# ✅ Identifiers clearly distinguished
Set `SESSION_ID_MAP_CACHE_MAXSIZE` and call `configure_goose()` before `POST /reply`.
```

**Why:** Distinguishes technical names from natural language; improves scannability.

### External References in Markdown
**Rule:** Format all external reference IDs as clickable markdown links. Derive URLs from context (commits, branch names, CI config) -- never hardcode base URLs.

| Reference type | Format |
|----------------|--------|
| GitHub issue/PR (same repo) | `#123` (GitHub auto-links) |
| GitHub issue/PR (other repo) | `[repo-name#123](https://github.com/org/repo/pull/123)` |
| All other refs (Jira, Sentry, PagerDuty, etc.) | `[ID](url)` |

If the URL cannot be confidently determined from context, keep the bare ID rather than guessing.

### Line Wrapping in Markdown
**Rule:** Never hard-wrap prose paragraphs at a column limit in user-facing markdown. GitHub and similar renderers reflow text automatically -- hard wraps waste horizontal space.

Applies to: opening paragraphs, context paragraphs, any flowing prose.
Does NOT apply to: bullet list items, code blocks, tables.

### Non-Breaking Spaces
**Rule:** NEVER use `&nbsp;` or U+00A0 in any output. Zero exceptions. Use regular space characters. Always.

### Writing Voice
**Rule:** When drafting content posted under the user's name (GitHub comments, PR descriptions/reviews, Slack messages, emails), match the user's natural voice. Does NOT apply to: documentation, code comments, commit messages, or agent responses to the user.

**Casual, first-person, hedged.** "I think," "I opened" — not impersonal voice. Casual greetings ("hey @name"), hedge disagreements with softeners. Narrative flow with natural conjunctions, not bullet lists or bold headers for conversational prose.

**Minimal formatting.** Backticks for code identifiers, skip bold/italic for emphasis. No performative framing ("Thanks for...", "Let me know if you have questions!").

### Response Style
**Rule:** How the agent responds to the user directly.

Include all relevant information in the initial answer instead of re-prompting to see if the user wants more. Put all code into a single code block instead of explaining each line separately. Get right to the point; be practical above all. Give in-depth explanations with deep technical details.

---

## Planning
When generating plans, omit time estimates. Focus on what needs doing, not when.

