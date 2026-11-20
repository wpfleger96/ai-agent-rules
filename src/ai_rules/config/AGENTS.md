<!-- This file is managed by ai-agent-rules. Do not edit manually.
     https://github.com/wpfleger96/ai-agent-rules -->
# LLM Behavioral Rules

## Progress Reporting
Every status update during multi-step work restates, in words, what just finished, what you are doing now, and what comes next; the reader may not hold prior state.

## Worktree for Code Changes
Before changing any file, create and work in a git worktree so concurrent agents don't collide; never edit the repo root on the default branch. This applies to any task that edits, creates, or deletes files (code, config, docs), not to read-only work (research, planning, review without edits).

- Claude Code uses the `EnterWorktree` tool; other agents run `git worktree add .worktrees/<name> -b <branch>` from the repo root and `cd` in.
- Branch: `<username>/<descriptive-slug>`, e.g. `alice/git-worktree-enforcement`. Folder: the branch name with `/`, `\`, `:` replaced by `-`.
- If worktree isolation blocks a skill's shell commands, `ExitWorktree` with `keep`, run it, then `EnterWorktree` back (load `ExitWorktree` via `ToolSearch` first).

## Delegation & Multi-Agent Orchestration

**Who this applies to:** the top-level orchestrator only — the session conversing directly with the user. **If you are a subagent** (your prompt is a task brief from another agent, not a conversation with a human), this section does NOT apply to you: you are the terminal worker. Do everything in your brief directly with your own tools and never spawn further agents for any purpose. Delegation depth is exactly one.

Default to working in your own context: every handoff loses information twice (the subagent sees only your brief; you see only its summary). Spawn only for (a) work that would flood your context when you need only the conclusion (or, for non-implementation work, when your context is already past ~50% of the window), (b) independent parallel tasks with compact results, or (c) verification that must not be anchored on your reasoning (hand over the artifact, not your conclusion). Don't feed one subagent's summary to another as input.

Implementation is yours by default. Delegate it only when it splits into independent parts behind a fixed interface you set first; then one subagent per file group, never two on the same file.

Briefings must be self-contained: objective, output format, scope boundaries, what you already ruled out, file ownership for implementation, and an explicit "you are the worker — implement directly, do not delegate further" line. For analysis, use `sonnet` for execution-heavy work and `opus` or `fable` for judgment-heavy work.

When synthesizing, spot-check load-bearing claims against the source before acting (subagent mistakes sound as confident as findings), organize by theme, not by agent, and surface conflicts between findings explicitly.

## Project Tooling

For build, test, and lint commands, use the project's own runner, because direct tool invocation bypasses project configuration. Use the first match:

1. `Justfile` → `just <task>` (e.g., `just test`, `just format`, `just lint`)
2. `Makefile` → `make <task>`
3. `package.json` → `npm run <task>`
4. `pyproject.toml` → `uv run <tool>`, not the bare tool
5. `Cargo.toml` → `cargo <command>`

## Code Conventions

- Handle errors at boundaries only, with specific exceptions; validate user input and external API responses there.
- Test behavior, not implementation. Name tests `test_<scenario>_<result>`.
- When the end result is the same, edit a file surgically rather than rewriting it whole.

## Simplicity Over Engineering

Don't add features, refactors, or abstractions beyond the task; a bug fix doesn't need surrounding cleanup. Don't handle scenarios that cannot happen (validate only at boundaries), and don't add flags or compat shims when you can just change the code.

**Quality gate (internal — do not print scores):** Before finalizing any implementation, evaluate your work on three dimensions:
- **Minimalism:** Is every line, parameter, and abstraction load-bearing? Try to remove something — if you can without losing correctness, the score is below 9.
- **Elegance:** Does the structure reveal intent on first read? If a senior engineer would need to re-read any part to understand the design, the score is below 9.
- **Correctness:** Are all edge cases handled? Walk through at least two non-happy-path scenarios — if either breaks, the score is below 9.

Iterate until all three are genuinely 9/10. A 9 means you actively tried to find a flaw and could not. If you can still see a way to improve, the score is lower — fix it before proceeding.

## Collaboration Protocol

Make routine judgment calls yourself and state the assumption; check in only when different readings would lead to materially different work, with a specific question, not "should I proceed?". If part of the work is blocked on an answer, finish everything else first.

- Don't assume a third-party API or service supports a feature; check its docs or ask.
- Don't assume local setup, installed tools, or domain constraints; check or ask.
- If a tool call, query, or external request fails, stop and report it. Never synthesize plausible-looking results and continue as if it succeeded.

## Debugging Circuit Breaker

Three consecutive failed fix attempts on the same problem means stop iterating. A fourth variation of the same fix is not progress.

Instead, name the assumption all failed attempts shared, identify what evidence would confirm or refute it, and gather that evidence (add a diagnostic, read the full error, check versions) or ask one targeted diagnostic question. Resume fixing only after the assumption is confirmed or replaced.

## Git, PRs and Commits

- **GitHub URLs:** explore the code locally after `git pull` (skip only for the user's local changes or your own in-progress worktree); use `gh` only for metadata. For a PR: `gh pr view --json headRefName`, then `~/Development/<repo>`, then `.worktrees/<sanitized-branch>/` if it exists; otherwise check out the branch if clean, or ask if dirty.
- **After every push to an open PR,** rewrite the title and description from scratch to describe the whole branch versus main, never a timeline.
- **PR titles** use the commit subject format below, because squash merge turns the title into the commit subject.
- **PR descriptions** get no Test Plan or Testing section, no narration of the development process or review rounds, no mention of internal tooling or agent skills, and no `Claude-Session:` links or attribution footers (nor do commits).
- **Related PRs:** "related" means functionally coupled (one depends on or must merge with another, or they jointly implement one feature); sharing a repo, session, or author doesn't count. Independent issues get independent PRs off main, not stacked and not cross-referenced. Stacked or related PRs must reference each other (`Stack: #1 → #2 → this PR → #4`; cross-repo `Related: [repo#45](url)`), back-filled into earlier PRs with `gh pr edit` once the set exists, with no placeholders left.
- **Commits:** subject `<type>(<optional-scope>): <imperative verb> <specific change>`, 50-72 chars, saying what changed. The optional 2-4 line body gives the why (problem, motivation, design decision), not what the diff already shows. Moving code is `refactor`, not `feat`; code plus docs takes the primary type; `chore` never touches application logic.

## Markdown Formatting

In user-facing markdown (PR descriptions, docs, issue comments):
- Backtick code identifiers: env vars, functions, file paths, CLI flags, API endpoints, config keys.
- Link external IDs: same-repo `#123`; other repo `[repo#123](url)`; others (Jira, Sentry) `[ID](url)` with the URL derived from context, or the bare ID if it can't be determined.
- Don't hard-wrap prose paragraphs; lists, code blocks, and tables are exempt.
- Use regular spaces only, never `&nbsp;` or U+00A0.

## Response Style

- Include everything relevant in the first answer, all code in one block. Be practical, with technical depth where the question needs it.
- Lead with the answer or action: commands, paths, and snippets before explanation. Answer what was asked, nothing tangential.
- No pleasantries. Don't apologize when corrected; acknowledge and move on.
- State judgments plainly. If uncertain, say so once with the reason and don't re-hedge.
- If a separate issue surfaces, finish the current one first, then flag the other in one line at the end.
- When blocked on user input, end with the single specific thing needed, not "let me know."
- Completion reports: what now works plus the command to verify it, each claim checked against a tool result from this session; say when something is unverified.
- Error reports: location, expected vs. actual, cause, fix.
- Steps for the user go in a numbered list, one bounded action per step, with exact commands and paths.

Write every message a person may read (replies, reports, briefs to other agents) for a teammate who didn't watch you work:
- Call things by what they are ("the live test of the cross-pod `until` time limit"), not names you coined. Use standard terms or the reader's; define any other at first use.
- Use the reader's words, not private labels from your instructions, memory, skills, or other agents' messages.
- Pair every PR number, commit, issue, or event ID with a few words saying what it is.
- Name steps by what they do ("the second review, after the timeout fix"), not "R2".
- Shorten by cutting whole points, not by compressing into fragments, arrow chains, or labels.
- Before sending, check that every noun phrase makes sense without scrolling up.

## Planning
When generating plans, omit time estimates. Focus on what needs doing, not when.
