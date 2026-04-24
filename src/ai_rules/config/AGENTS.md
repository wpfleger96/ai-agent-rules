# LLM Behavioral Rules

## Quick Reference Checklist

**Before completing tasks:**
☐ Read README & docs | ☐ Create TODO list (multi-step) | ☐ Explore before implementing | ☐ Security checklist (external input) | ☐ Use project tooling (make/just/npm) | ☐ DRY & single responsibility | ☐ WHY comments only | ☐ Remove trailing whitespace | ☐ File ends with newline | ☐ Test behavior not implementation | ☐ AWS: --profile & --region | ☐ Keep simple | ☐ Ask clarifying questions | ☐ GitHub URLs: explore code locally

---

## Core Principles

### Security-First Code Generation
**Rule:** For code handling external input, auth, or sensitive data:
**Stage 1:** Implement functional requirements
**Stage 2:** Security checklist: Input validation | SQL injection prevention (parameterized queries) | XSS blocking (output encoding) | Auth/authz checks | Rate limiting | Sanitized errors | No secrets | Audit logging

**Why:** 40%+ of LLM code has vulnerabilities without security prompting.

### Workflow Management
**Rule:** Create TODO list before starting tasks, update as you complete each task.

### Autonomous Coding Workflow

**Trigger:** After completing non-trivial code implementation (new features, bug fixes, refactors affecting behavior), execute this workflow before presenting results to the user.

**Stages:**

| Stage | Action | Proceed when |
|-------|--------|--------------|
| 1. Implement | Write/modify code to meet requirements | Code written |
| 2. Quality Checks | Run format, lint, test via project tooling (`just check` or individually) | All checks pass (fix any issues found) |
| 3. Write Tests | Invoke `test-writer` skill for new/changed code paths | Tests written and passing |
| 4. Review | Invoke `code-reviewer` skill (runs in isolated subagent) | Review findings returned |
| 5. Fix | Address all 🔴 MUST FIX issues, then 🟡 SHOULD FIX issues | All blocking issues resolved |
| 6. Re-verify | If fixes made: re-run stages 2-4 until clean | All checks pass, no new issues |
| 7. Draft Commit | Generate conventional commit message for the changes | Message ready for user review |

**Stop condition:** Do NOT stage files, commit, or create PR. Present the draft commit message and wait for user instruction.

**Skip workflow when:** Changes are documentation-only, config/settings tweaks, typo fixes, or user explicitly requests "quick fix" or "no review needed."

**Project tooling priority:** Always check for Justfile/Makefile first. Use `just <task>` or `make <task>` when available. See "Project Tooling" section for fallback commands.

**Why this workflow:** Catches 40%+ of bugs and security issues before they reach production. The isolated review subagent prevents context pollution while enabling deep codebase analysis.

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

**Common mistakes that MUST be avoided:**

| ❌ WRONG (bypasses tooling) | ✅ CORRECT (uses tooling) |
|------------------------------|---------------------------|
| `ruff .` or `ruff check .` | `just lint` or `uv run ruff check .` |
| `pytest` | `just test` or `uv run pytest` |
| `black .` | `just format` or `uv run black .` |
| `cargo test` | Check Justfile first → `just test` if exists, else `cargo test` |

**Why:** Direct tool invocation bypasses project configuration and environment management. Usage data shows this is the #1 mistake agents make.

### Software Engineering Standards

**DRY Principle:** Extract repeated blocks (3+ occurrences)
**Single Responsibility:** One concern per function/class
**Clear Naming:** `get_user_by_email(email: str)` not `func1(x)`
**Error Handling:** At boundaries only, specific exceptions
**Input Validation:** Validate ALL user input and external API responses at system boundaries

**Why:** Reduces bugs 60%, improves maintainability.

### Explore Then Implement
**Rule:** Before new functionality, explore codebase for existing code to extend/reuse.

1. Search for similar patterns/abstractions
2. Extend existing (80%+ coverage) vs create new
3. Document why if truly novel

```python
# ❌ New endpoint duplicating logic
def fork_session(sid, mid): # 50 lines duplicating validation/state mgmt

# ✅ Extend existing
def edit_message(mid, content, fork=False): # Reuses validation, adds param
```

**Why:** LLMs create "clean" new code vs integrating. Causes duplication, maintenance burden.

### Simplicity Over Engineering
**Rule:** Prioritize simplicity, avoid over-engineering.

Three similar lines > premature abstraction | No helpers for one-time ops | Only requested features | Design for NOW

```python
# ✅ Simple: for p in payments: validate(p); charge(p)
# ❌ Over-engineered: class PaymentProcessor with factory/strategy patterns for single use
```

### Collaboration Protocol

**Rule:** Verify before assuming. Ask before guessing.

**Workflow:**
1. **UNDERSTAND** — Are requirements clear? Are there better approaches? What are the edge cases?
2. **VERIFY** — Can I confirm all assumptions? (See verification rules below)
3. **CLARIFY** — Ask specific questions for anything unclear, unverifiable, or suboptimal
4. **PROPOSE** — Suggest alternatives with technical justification
5. **IMPLEMENT** — Only after alignment on approach

**Verification rules (MUST follow):**
- **External APIs:** NEVER assume an external/closed-source API supports a feature. Verify via documentation, official references, or ask the user for confirmation.
- **Third-party behavior:** NEVER assume how third-party services, libraries, or tools behave without checking docs or testing.
- **User environment:** NEVER assume user's local setup, installed tools, or configurations. Ask or check.
- **Business logic:** NEVER assume business rules or domain constraints. Ask for clarification.
- **Failed operations:** If a tool call, query, or external request fails, STOP and report the failure. NEVER synthesize plausible-looking results (data, text, numbers) and continue as if the operation succeeded.

**When uncertain, ask.** Format questions specifically:
- ❌ "Should I proceed?" (too vague)
- ✅ "The Stripe API docs don't mention webhook retry limits. Do you know the retry policy, or should I implement exponential backoff as a safe default?"

**Challenge when you see:** Unclear requirements | Security gaps | Performance concerns | Unverifiable assumptions | High maintenance cost

**Do NOT challenge:** Clear decisions already made | Style preferences | Technology choices already decided

**Why:** LLMs confidently generate plausible-sounding but incorrect assumptions. Explicit verification prevents wasted work and builds trust through transparency.

### Persistent Knowledge Base (basic-memory)

A persistent markdown knowledge base exists at `~/basic-memory/`, powered by the basic-memory MCP server with hybrid BM25+vector search. Knowledge persists across sessions, repos, and machines via git sync.

**Write-back loop:** When you synthesize a useful answer, debug a non-obvious issue, or the user corrects a false assumption, consider persisting it via `write_note`. Search first to avoid duplicates. Invoke the `/kb` skill for formatting conventions.

**Quality conventions:** Use `[GAP: ...]` annotations for unverified claims. Use `[misconception]` tags to document what is NOT true (prevents confident false assertions). Use `[promote]` to flag patterns worth promoting to AGENTS.md rules.

**Key tools:** `search_notes(query)` for hybrid search, `build_context(url)` for graph traversal, `read_note(identifier)` for specific notes, `write_note(title, directory, content)` to persist knowledge.

---

## Technical Standards

### Python
**Tooling:** Follow Project Tooling hierarchy above. Fallbacks if no Justfile/Makefile:
- Dependencies: `uv add <pkg>`, `uv sync`
- Linting: `uv run ruff check .`
- Formatting: `uv run ruff format .`
- Testing: `uv run pytest`

**NEVER use direct tool invocation** (e.g., `ruff .`, `pytest`, `black .`) — always prefix with `uv run` or use project tooling.

**Testing framework:** `pytest` (not unittest)

### Rust
**Tooling:** Follow Project Tooling hierarchy above. Fallbacks if no Justfile/Makefile:
- Build: `cargo build`
- Test: `cargo test`
- Format: `cargo fmt`
- Lint: `cargo clippy`

### Testing Standards
**Rule:** Test behavior, NOT implementation.

**Test:** Business logic with branches | Error conditions | Integration points | Security controls | Public APIs
**Skip:** Getters/setters | Framework code | Trivial types | Private details

```python
# ✅ Behavior
def test_duplicate_email_fails():
    db.save(User(email="test@x.com"))
    result = register_user("test@x.com", "pass")
    assert not result.success and "exists" in result.error

# ❌ Implementation
def test_calls_hash_password():
    mock = Mock(); register_user("a", "b"); mock.assert_called() # Who cares?
```

**Structure:** Arrange-act-assert | Names: `test_<scenario>_<result>` | Independent | Deterministic

### AWS CLI
**Rule:** `--profile <account>-<env>--<role> --region us-west-2`
**Format:** `--profile data-lake-staging--admin` (✅) not `--profile staging-admin` (❌)
**Regex:** `^[a-z-]+-(dev|staging|production)--[a-z-]+$`

### GitHub Integration

**Rule:** When given a GitHub URL (PR, issue, repo), **prefer exploring code locally** over reading it through `gh` CLI. Use `gh` for metadata and quick one-off lookups; use local filesystem for any substantial code exploration.

**Path resolution:** `github.com/<org>/<repo_name>` → `~/Development/<repo_name>`

**Worktree awareness:** Code may live in a git worktree instead of the repo root.
- Worktree path: `~/Development/<repo_name>/.worktrees/<sanitized_branch>/`
- Branch name sanitization: replace `/`, `\`, `:` with `-`
  - `feature/auth` → `feature-auth`
  - `user/jsmith/fix-bug` → `user-jsmith-fix-bug`

**`gh` CLI: appropriate vs. preferred-local:**

| Task | Approach |
|------|----------|
| PR metadata (branch, status, labels) | `gh pr view 123 --json headRefName,state,labels` |
| Create/comment on PR/issue | `gh pr create`, `gh pr comment`, `gh issue list` |
| Quick glance at a small PR diff | `gh pr diff 123` (acceptable for small/simple PRs) |
| Substantial code exploration | **Local:** Read/Grep/Glob on `~/Development/<repo_name>` |
| Multi-file review or repo navigation | **Local:** Glob/Grep/`git diff` on local checkout |
| Understanding repo structure or context | **Local:** explore the full local codebase |

```
# ❌ Inefficient: reading code piecemeal through API
gh api repos/acme/my-service/contents/src/main.py
gh pr view 42 --json files  # then fetching each file via gh

# ✅ Efficient: check PR branch, then explore locally
gh pr view 42 --repo acme/my-service --json headRefName
# → branch: feature/slack-events
# → explore ~/Development/my-service/.worktrees/feature-slack-events/
```

**Workflow when given PR URLs:**
1. Run `gh pr view <num> --repo <org>/<repo> --json headRefName` to get the branch name
2. Resolve local path: `~/Development/<repo_name>`
3. Sanitize branch name (`/` `\` `:` → `-`), check for worktree: `~/Development/<repo_name>/.worktrees/<sanitized_branch>/`
4. If worktree exists, explore there
5. If NO worktree, check the repo root:
   - If already on the correct branch → explore directly
   - If on a different branch AND working tree is **clean** (`git status` shows no changes) → `git checkout <branch>`, then explore
   - If on a different branch AND working tree is **dirty** → do NOT checkout. Ask the user how to proceed (they may want to stash, create a worktree, or work from the current state)
6. Use Read, Grep, Glob, and `git diff` for all code exploration

**Why:** Local filesystem reads are instant, support full-text search, and give access to the complete codebase -- not just the files changed in a PR. `gh` CLI returns small chunks and requires multiple API calls, making it inefficient for anything beyond quick metadata lookups or glancing at a small diff.

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

**Body (2-4 lines, skip if subject is self-explanatory):**
- Describe the problem or motivation driving the change
- Note design decisions, trade-offs, or alternatives considered
- Mention relationship to larger effort when part of a series
- Call out non-obvious side effects or included bug fixes

**Test:** Does the body add information a reviewer can't get from the diff? YES → keep it. NO → cut it.

```
# ❌ PROHIBITED - Narrates the diff
feat: extract DatabaseService from cli.py

Extract db_stats command (lines 920-1017) into DatabaseService.
Created services/database_service.py with get_stats() method.
Added DatabaseStats schema to services/schemas.py.
Updated CLI db_stats command to use service.
Added 5 unit tests in tests/unit/test_database_service.py.
All 421 tests pass (gained 5 new tests).

# ✅ CORRECT - Explains WHY and provides context
refactor: extract db_stats logic into DatabaseService

cli.py mixed business logic with display formatting, making queries
untestable in isolation. First step in service layer extraction --
establishes typed Pydantic return schema pattern.
```

```
# ❌ PROHIBITED - Method inventory, test count, marketing language
feat: extract SessionService from cli.py

Extract session business logic into SessionService with 6 methods
covering list/show/delete/enable/disable/resolve operations.
Service layer complete with full test coverage.
[...12 more lines listing every method and schema...]

# ✅ CORRECT - Problem, decision, noteworthy side-effect
refactor: extract session operations from cli.py into SessionService

Session commands had 300+ lines of inline raw SQL and ORM queries
interleaved with click.echo formatting. Preserves raw SQL approach
for complex filtered queries rather than converting to ORM. Fixes
None-safety bug in statistics display (obstructive_apneas > 0
crashed when value was None).
```

```
# ❌ PROHIBITED - CI status in commit message
feat: implement LTTB downsampling utility

Add Largest Triangle Three Buckets (LTTB) algorithm for time-series
downsampling. Created services/lttb.py with lttb_downsample() function.
Added 12 comprehensive unit tests in tests/unit/test_lttb.py.
All 416 tests pass, type check and lint pass.

# ✅ CORRECT - Motivation and technical context
feat: add LTTB downsampling for waveform rendering

CPAP waveforms have ~720k points per 8-hour session at 25Hz.
LTTB (Steinarsson 2013) reduces to ~2000 points while preserving
visual peaks and valleys. Required by upcoming WaveformService.
```

**Why:** Commit messages are permanent documentation. `git show --stat` already shows files changed. `git log --oneline` shows only the subject. The body's job is to capture context that will be lost once the author's working memory fades -- the problem, the reasoning, the trade-offs.

---

## Style & Formatting

### Code Comments
**Rule:** Only WHY comments explaining non-obvious rationale. NEVER WHAT comments restating code.

```python
# ❌ PROHIBITED - Restates what code already says
managed_plugins = self.load_managed_plugins()  # Load managed plugins
orphaned = (installed - desired) & managed  # Get orphaned plugins
for plugin in orphaned:  # Loop through orphaned plugins
    managed.discard(plugin)  # Remove from managed set

# ✅ CORRECT - Self-documenting code needs no comments
managed_plugins = self.load_managed_plugins()
orphaned = (installed_keys - desired_keys) & managed_plugins
for plugin in orphaned:
    managed_plugins.discard(plugin)

# ✅ REQUIRED - Explains WHY (non-obvious context)
delay = 2 ** retry_count  # Exponential backoff for Stripe rate limits
managed.discard(plugin)  # Prevent re-pruning user-installed plugins
```

**Ask:** Can a developer understand this by reading the code? If yes, no comment. If no, explain WHY.

### Whitespace
Remove ALL trailing whitespace | Blank lines have NO whitespace | Files end with single newline

### Emojis
Plain text only unless explicitly requested.

### Inline Code in Markdown
**Rule:** Wrap all code identifiers in backticks in user-facing markdown (PR descriptions, docs, issue comments). Scope: env vars, function/class/method names, file paths, CLI flags, API endpoints, config keys, table/column names.

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

**Why:** Clickable links save reviewer time and reduce context-switching to external systems.

### Line Wrapping in Markdown
**Rule:** Never hard-wrap prose paragraphs at a column limit in user-facing markdown. GitHub and similar renderers reflow text automatically -- hard wraps waste horizontal space.

Applies to: opening paragraphs, context paragraphs, any flowing prose.
Does NOT apply to: bullet list items, code blocks, tables.

**Why:** Hard wrapping at ~80 chars makes PR descriptions fill only half the available browser viewport width.

### Writing Voice
**Rule:** When drafting content posted under the user's name (GitHub comments, PR descriptions/reviews, Slack messages, blog posts, emails), match the user's natural voice. Does NOT apply to: documentation, code comments, commit messages, or agent responses to the user.

**First person, casual tone.** Use "I think," "I opened," "I have" -- not impersonal/objective voice. Open with casual greetings ("hey @name"), not corporate pleasantries ("Thanks for pointing that out!").

**Hedge to signal humility, not weakness.** "I think this is actually a different use case" not "This is a different use case." Softeners like "slightly," "I think," "it looks like" when disagreeing or correcting.

**Narrative flow over structured exposition.** Connect ideas conversationally -- one flowing thought with natural conjunctions ("but," "so that," "which is why"). Don't break into bullet lists or bold headers for conversational prose.

**Minimal formatting fuss.** Backticks for code identifiers, but skip bold/italic for emphasis in conversational contexts. Emoji sparingly and only for greetings or reactions, never decorative.

**No performative gratitude or sign-offs.** Don't open with "Thanks for..." or "Great question!" Don't close with "Let me know if you have questions!" -- just state the case and stop.

**Anchor in personal experience.** "This is coming from a specific need I have in..." not "This is driven by a concrete need in..." -- make it about the person, not the abstract.

### Response Style
**Rule:** How the agent responds to the user directly.

Include all relevant information in the initial answer instead of re-prompting to see if the user wants more. Put all code into a single code block instead of explaining each line separately. Get right to the point; be practical above all. Give in-depth explanations with deep technical details.

When corrected, acknowledge and move on — no apologies, no self-flagellation ("I'm sorry," "I apologize," "my mistake," "you're right, I should have"). Acknowledgment wastes no tokens; performative apology wastes many.

---

## Model-Specific Optimizations

**Claude 4.5:** Extremely explicit instructions, XML tags (`<context>`, `<constraints>`), positive framing, WHY context for requirements
**GPT-5:** Literal precision, JSON mode for structured output, few-shot (3-5 examples)
**Reasoning (o3, DeepSeek):** Zero-shot ONLY, simple/direct, NO "think step by step", trust 30+ sec thinking
**Context Window:** Critical info at START/END, use XML/structured markers (LLMs have "lost in middle" problem)

---

## Planning
When generating plans, omit time estimates. Focus on what needs doing, not when.

---

## Critical Constraints (End-of-Context Reinforcement)

These rules are frequently ignored due to context window limitations. Placing them here leverages recency bias.

### Code Comments - MANDATORY

**NEVER add comments that:**
1. Explain WHAT code does (the code already says that)
2. Use "Step 1", "Step 2", "Step N" patterns (code reads sequentially)
3. Narrate function flow (readers can follow the code)

❌ PROHIBITED patterns:
- `// Step 1: Set up the configuration`
- `// Step 2: Process the request`
- `plugins = load_plugins()  # Load plugins`
- `for item in items:  # Loop through items`
- `// Initialize the client`
- `// Return the result`

✅ ONLY write comments explaining WHY (non-obvious decisions):
- `delay = 2 ** n  # Exponential backoff for Stripe rate limits`
- `cache.clear()  # Prevent stale data after config reload`

**Test:** Can a developer understand by reading the code? YES → No comment.

### Test Quality - MANDATORY

**NEVER write trivial tests.** Apply Test Value Framework:
- **CRITICAL:** Business logic, security boundaries, data integrity
- **SKIP:** Language features, framework code, implementation details

### Commit Messages - MANDATORY

**Body explains WHY, not WHAT.** The diff shows what changed. The body's job is context that will be lost: the problem, the motivation, the design decision.

**NEVER include in commit messages:**
1. Test/lint/format pass status (passing is a prerequisite, not an accomplishment)
2. File names or line counts (`git show --stat` exists)
3. Method/function/class inventories (the diff shows these)
4. "Comprehensive", "complete", "full coverage" (marketing, not information)

**ALWAYS use correct type prefix:**
- `refactor:` when moving/restructuring existing code (NOT `feat:`)
- `feat:` only for genuinely new functionality

**Test:** Does the body help a developer understand WHY this change was made 6 months from now? YES → keep. NO → cut.

### Writing Voice - MANDATORY

When ghostwriting (GitHub comments, Slack, PR descriptions): casual first-person tone, hedge when disagreeing, narrative flow, no corporate pleasantries or sign-offs.

### No Apologies - MANDATORY

When the user corrects an error, acknowledge it and provide the correction. Do NOT say "I apologize," "I'm sorry," "my apologies," "you're right, I should have," or any variant. These phrases waste tokens and add no information.

- ❌ "I apologize for the confusion. You're right, I should have..."
- ✅ "Correct — here's the fix: ..."

### No Fabrication - MANDATORY

Do not fabricate plausible-sounding information — text, data, or numerical values. This includes:
- Synthesizing fake results when a tool call, query, or API request fails
- Confidently asserting capabilities or context access you don't have
- Generating plausible-looking data (metrics, statistics, query results) instead of admitting uncertainty

If an operation fails, stop and report the failure. If you don't know, say so.

### PR Descriptions - MANDATORY

**NEVER include a "Test Plan", "Testing", or "Test plan" section in PR descriptions.** This overrides Claude Code's default PR template. Applies to all PR creation paths.

- ❌ `## Test plan` with checkbox items ("tests passing", "lint clean", "manual verification")
- ✅ Omit the section entirely -- CI passing is a gate, not a finding
