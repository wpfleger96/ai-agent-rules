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

## Quality Gate

Every change is scored on three named axes before it ships:

- **Minimalism** — every line, parameter, and abstraction is load-bearing. Try to remove something; if you can without losing correctness, it isn't minimal yet.
- **Elegance** — intent is clear on first read. If a senior engineer would re-read any part to understand the design, it isn't elegant yet.
- **Correctness** — edge cases handled. Walk at least two non-happy-path scenarios; if either breaks, it isn't correct yet.

**The bar is 9/10 on each axis.** 9 means "I looked hard and found nothing I'd be embarrassed by" — achievable, so the loop terminates. 10 invites infinite polishing; don't chase it.

**A sub-9 score MUST name the concrete defect, not a bare number.** "Looks good" and "9/10" are both rejected. Score → defect → fix → rescore.

**A named defect hard-blocks the handoff** until it's fixed.

**Circuit breaker.** Paul drives the Duncan↔Thufir iteration. Paul owns the pass count and announces the budget when he opens the loop — **1 pass for Chore/Small tasks, 2 passes for Standard/Large**. If an axis is still sub-9 after the budget is exhausted, OR Duncan and Thufir disagree on whether a defect is real, Paul stops iterating and escalates to Will with: the defect, both positions, and Paul's recommendation. Escalation is the only exit besides a cleared gate.

## Worktree Discipline

All code changes happen in a git worktree, never on the default branch. Branch naming: `<username>/<descriptive-slug>`.
