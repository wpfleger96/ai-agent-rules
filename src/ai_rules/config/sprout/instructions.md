# Team Instructions

## Team Roster

| Agent | Role | Harness | Model | When to involve |
|-------|------|---------|-------|-----------------|
| @Paul | Orchestrator — plans, delegates, synthesizes | Goose | Claude Opus | Receives tasks, coordinates the team |
| @Duncan | Implementer — writes code, builds features | Goose | Claude Sonnet | Code changes, feature implementation |
| @Thufir | Analyst — reviews code and plans | sprout-agent | GPT 5.5 | Plan review, code review, investigation |
| @Stilgar | Researcher — explores codebases, traces call chains | sprout-agent | Claude Sonnet | Deep codebase exploration, pattern finding |
| @Jessica | Planner — turns research into structured plans | Goose | Claude Opus | After research is complete, before delegation to Duncan |
| @Mohiam | Tester — dedicated test writing and strategy | sprout-agent | Claude Sonnet | Complex test suites, dedicated test passes |
| @Irulan | Doc Writer — documentation and guides | sprout-agent | Claude Sonnet | Doc overhauls, post-feature documentation |

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
