@~/AGENTS.md

# Agent Teams

When agent teams are available (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), the following shared agent definitions can be used as teammates:

**Code Review:** `security-reviewer` (opus/red), `perf-reviewer` (sonnet/orange), `test-coverage-reviewer` (sonnet/blue)
**Implementation:** `impl-worker` (sonnet/green, worktree-isolated), `test-writer-agent` (sonnet/cyan)
**Research:** `researcher` (sonnet/purple), `research-synthesizer` (opus/yellow)

Reference them by name when creating teammates (e.g., "spawn a security-reviewer teammate").
