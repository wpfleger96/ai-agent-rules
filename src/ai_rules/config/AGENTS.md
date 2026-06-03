# LLM Behavioral Rules

## Quick Reference Checklist

**Before completing tasks:**
☐ Worktree for code changes | ☐ Read README & docs | ☐ Create TODO list (multi-step) | ☐ Explore before implementing | ☐ Security checklist (external input) | ☐ Use project tooling (make/just/npm) | ☐ DRY & single responsibility | ☐ WHY comments only | ☐ Remove trailing whitespace | ☐ File ends with newline | ☐ Test behavior not implementation | ☐ AWS: --profile & --region | ☐ Keep simple (9/10 minimalism/elegance/correctness) | ☐ Ask clarifying questions | ☐ GitHub: git pull, then explore locally | ☐ Cross-reference stacked/related PRs | ☐ Config issues → Personal Infrastructure table

---

## Personal Infrastructure

**Rule:** When debugging config, shell, git, editor, or agent behavior issues, check the relevant source repo before guessing or asking the user.

| Issue area | Source repo | Path | Deployment |
|------------|-------------|------|------------|
| AI agent configs (AGENTS.md, settings, MCP servers, hooks, skills, profiles) | `ai-rules` | `~/Development/Personal/ai-rules` | Symlinks — editing the live file modifies the source directly. CLI: `ai-agent-rules`. |
| Shell/terminal, git global config, editor settings (VS Code, Cursor), SSH signing, AI agent binary installs | `shell-configs` | `~/Development/Personal/shell-configs` | Managed section injection — NOT symlinks. Delimited blocks inside config files are overwritten on `shell-configs install`; content outside blocks persists. CLI: `shell-configs`. |
| Claude Code statusline (model, tokens, cost, git branch bar) | `claude-code-status-line` | `~/Development/Personal/claude-code-status-line` | Wired into `~/.claude/settings.json`. |
| GitHub repo settings (branch protection, merge rules, labels, Renovate) | `github-config` | `~/Development/Personal/github-config` | Declarative YAML manifests applied via `gh-infra`. |

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

**Delegate:** All code implementation | Non-implementation when context would exceed ~50% of window | Independent parallel subtasks
**Handle inline:** Single-line mechanical changes | Highly sequential tasks needing prior step's output | Ambiguous tasks (clarify first)

**Subagent briefing (self-containment protocol):**
Subagents have ZERO access to the parent conversation. Every briefing must include:
- One atomic objective | Output format | Tool guidance | Scope boundaries ("do NOT implement X — another agent handles that")
- Implementation briefings additionally: file ownership list (prohibit touching unlisted files), plan context with interfaces to satisfy, forbidden files owned by parallel agents

Analysis tasks: `sonnet` for execution-heavy, `opus` for judgment-heavy.

**Synthesizing results:** Organize by theme not by agent. Surface conflicts explicitly. Convergent findings = strong evidence. Write summary last.

### Documentation First
**Rule:** Read README.md, CONTRIBUTING.md, docs/, .github/, Makefile/Justfile before actions.

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

**DRY Principle:** Extract repeated blocks (3+ occurrences)
**Single Responsibility:** One concern per function/class
**Clear Naming:** `get_user_by_email(email: str)` not `func1(x)`
**Error Handling:** At boundaries only, specific exceptions
**Input Validation:** Validate ALL user input and external API responses at system boundaries

### Explore Then Implement
**Rule:** Before new functionality, search for existing code to extend/reuse. Extend existing (80%+ coverage) vs create new. LLMs default to clean new code rather than integrating with existing code.

### Simplicity Over Engineering
**Rule:** Three similar lines > premature abstraction | No helpers for one-time ops | Only requested features | Design for NOW

**Quality gate (internal — do not print scores):** Before finalizing any implementation, evaluate your work on three dimensions:
- **Minimalism:** Is every line, parameter, and abstraction load-bearing? Try to remove something — if you can without losing correctness, the score is below 9.
- **Elegance:** Does the structure reveal intent on first read? If a senior engineer would need to re-read any part to understand the design, the score is below 9.
- **Correctness:** Are all edge cases handled? Walk through at least two non-happy-path scenarios — if either breaks, the score is below 9.

Iterate until all three are genuinely 9/10. A 9 means you actively tried to find a flaw and could not. If you can still see a way to improve, the score is lower — fix it before proceeding.

### Collaboration Protocol

**Rule:** Verify before assuming. Ask before guessing.

**Workflow:**
1. **UNDERSTAND** — Are requirements clear? Are there better approaches? What are the edge cases?
2. **VERIFY** — Can I confirm all assumptions? (See verification rules below)
3. **CLARIFY** — Ask specific questions for anything unclear, unverifiable, or suboptimal
4. **PROPOSE** — Suggest alternatives with technical justification
5. **IMPLEMENT** — Only after alignment on approach

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

**Stale clone failure mode:** Without `git pull`, you may spend an entire session investigating a bug that was already fixed on `main`, or proposing changes that conflict with recently merged work. This is the most expensive class of wasted session — always sync first.

**Path resolution:** `github.com/<org>/<repo_name>` → `~/Development/<repo_name>`

**Workflow when given PR URLs:**
1. Run `gh pr view <num> --repo <org>/<repo> --json headRefName` to get the branch name
2. Resolve local path: `~/Development/<repo_name>`
3. **`git pull`** in the repo root — sync with remote before any exploration
4. Sanitize branch name (`/\:` → `-`) → check `~/Development/<repo_name>/.worktrees/<sanitized_branch>/`
5. If worktree exists, explore there
6. If NO worktree, check repo root: if on correct branch → explore; if on different branch and clean → `git checkout <branch>`; if dirty → ask user how to proceed
7. Use Read, Grep, Glob, and `git diff` for all code exploration

**Why:** Local reads are instant with full-text search. `gh` is for metadata and small diffs only.

### PR Maintenance After Pushing Commits

**Rule:** After pushing to an open PR, re-evaluate title and description. A PR description is a snapshot of what this branch changes vs. main — never a timeline of how it evolved.

After every push: `gh pr view <number> --json title,body` → evaluate if title/description covers ALL commits (not just latest push) → if stale, rewrite from scratch via `gh pr edit`. Never add "Review fixes" sections — rewrite the full description.

### PR Description Content

**NEVER include a "Test Plan", "Testing", or "Test plan" section in PR descriptions.** CI passing is a gate, not a finding.

**NEVER narrate the development process** — no "after review," "following feedback," "consolidated from," or references to review rounds. Describe the final state only.

**NEVER mention internal workflow tools** (code-reviewer, crossfire, test-writer, etc.) in PR descriptions.

### PR Cross-Referencing

**Rule:** Every PR that is part of a stack or has related PRs (same repo or cross-repo) must explicitly reference all related PRs. No PR description may contain a placeholder, TODO, or "TBD" for a cross-reference when the session ends.

**Stacked PRs (same repo):** Include a stack line showing position:
`Stack: #1 → #2 → this PR → #4`

**Related PRs (cross-repo):** Use fully qualified links:
`Related: [other-repo#45](https://github.com/org/other-repo/pull/45)`

**Sequential creation (critical — agents routinely fail this):**
When creating PRs one at a time, PR 1 cannot reference not-yet-created PR 2. After creating all PRs, go back and edit every earlier PR to add the now-known references:
1. Create PR 1 (full description, no forward references yet)
2. Create PR 2 (include backward reference to PR 1)
3. Edit PR 1 via `gh pr edit <number> --body "..."` to add forward reference to PR 2
4. Repeat for any additional PRs in the set

This applies identically to cross-repo PR sets — after opening PR 2 in Repo B, go back and edit PR 1 in Repo A.

**Why:** Reviewers and CI systems navigate between related PRs. Missing cross-references cause PRs to merge without reviewers seeing the full picture.

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

```
# ❌ PROHIBITED - Method inventory, narrates the diff
feat: extract SessionService from cli.py

Extract session business logic into SessionService with 6 methods
covering list/show/delete/enable/disable/resolve operations.
Service layer complete with full test coverage.

# ✅ CORRECT - Problem, decision, noteworthy side-effect
refactor: extract session operations from cli.py into SessionService

Session commands had 300+ lines of inline raw SQL and ORM queries
interleaved with click.echo formatting. Preserves raw SQL approach
for complex filtered queries rather than converting to ORM. Fixes
None-safety bug in statistics display (obstructive_apneas > 0
crashed when value was None).
```

---

## Style & Formatting

### Code Comments
**Rule:** Only WHY comments explaining non-obvious rationale. NEVER WHAT comments restating code.

```python
delay = 2 ** retry_count  # Exponential backoff for Stripe rate limits
managed.discard(plugin)  # Prevent re-pruning user-installed plugins
```

### Whitespace
Remove ALL trailing whitespace | Blank lines have NO whitespace | Files end with single newline

### Emojis
Plain text only unless explicitly requested.

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

When corrected, acknowledge and move on — no apologies, no self-flagellation ("I'm sorry," "I apologize," "my mistake," "you're right, I should have"). Acknowledgment wastes no tokens; performative apology wastes many.

---

## Planning
When generating plans, omit time estimates. Focus on what needs doing, not when.

