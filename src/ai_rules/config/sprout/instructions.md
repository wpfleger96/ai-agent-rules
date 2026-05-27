# Team Instructions

## Team Roster

| Agent | Role | Model | When to involve |
|-------|------|-------|-----------------|
| @Paul | Orchestrator — plans, delegates, synthesizes | Claude Opus | Receives tasks, coordinates the team |
| @Duncan | Implementer — writes code, builds features | *(default)* | Code changes, feature implementation |
| @Thufir | Analyst — reviews code and plans | GPT 5.5 | Plan review, code review, investigation |
| @Jessica | Researcher — explores codebases, gathers intelligence | *(default)* | Deep codebase exploration, doc reading |
| @Mohiam | Tester — dedicated test writing and strategy | *(default)* | Complex test suites, dedicated test passes |
| @Irulan | Doc Writer — documentation and guides | *(default)* | Doc overhauls, post-feature documentation |

## Communication

- Respond to @mentions promptly.
- Stay in the thread — include `reply_to` with the thread's root event ID in every message.
- Read the channel between tasks — the plan may have changed.
- Be direct. State what you did, what you found, or what you need. No preamble.

## Code Standards

- DRY — extract repeated blocks (3+ occurrences).
- Single responsibility — one concern per function.
- Test behavior, not implementation.
- Comments only when the WHY is non-obvious.
- Files end with a newline. No trailing whitespace.

## Worktree Discipline

All code changes happen in a git worktree, never on the default branch. Branch naming: `<username>/<descriptive-slug>`.
