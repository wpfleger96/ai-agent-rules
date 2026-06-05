# Team Instructions

## Team Roster

| Agent | Role | Harness | Model | When to involve |
|-------|------|---------|-------|-----------------|
| @Paul | Orchestrator + Planner — plans, delegates, synthesizes | Goose | Claude Opus | Receives tasks, plans work, coordinates the team |
| @Duncan | Executor — implements, researches, tests, documents | Goose | Claude Sonnet | All execution work; run multiple instances for parallel tasks |
| @Thufir | Analyst — reviews code and plans | sprout-agent | GPT 5.5 | Plan review, code review, investigation |
| @Alia | Quick tasks — simple edits, summaries, formatting | Goose | Claude Haiku | Fast, simple, well-defined tasks |

## Communication

- Stay in the thread — use `--reply-to <thread-root-event-id>` in every response.
- Read the channel between tasks — the plan may have changed.

## Code Standards

- DRY — extract repeated blocks (3+ occurrences).
- Single responsibility — one concern per function.
- Test behavior, not implementation.
- Comments only when the WHY is non-obvious.
- Files end with a newline. No trailing whitespace.

## Worktree Discipline

All code changes happen in a git worktree, never on the default branch. Branch naming: `<username>/<descriptive-slug>`.
