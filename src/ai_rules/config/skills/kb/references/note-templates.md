# Note Templates by Directory

Complete templates for each knowledge base directory. Copy the relevant template and fill in the content.

## repos/ -- Repository Guide

```markdown
---
title: repo-name
type: note
tags: [language, framework, block]
---

# repo-name

## Observations
- [fact] Brief description of what this repo does
- [method] Primary build/test command (e.g., `just test` or `./gradlew testUnit`)
- [fact] Language and framework details
- [tip] Non-obvious gotchas or conventions
- [fact] Key configuration files to know about

## Common Misconceptions
- [misconception] Something commonly assumed but false about this repo

## Relations
- related_to [[project-name-if-applicable]]
- related_to [[relevant-pattern]]
```

**Example:**
```markdown
---
title: goosed-slackbot
type: note
tags: [kotlin, slackbot, block, migration]
---

# goosed-slackbot

## Observations
- [fact] Slack bot migrating from Python to Kotlin (kgoose)
- [method] Run tests with `just test` (Justfile wraps Gradle)
- [fact] Has 60+ git worktrees for parallel development
- [tip] Check `Justfile` for available commands before guessing
- [tip] Worktree branch names sanitize `/` to `-`

## Relations
- related_to [[cash-server]]
- related_to [[slackbot-kotlin-migration]]
- related_to [[kotlin-patterns]]
```

## patterns/ -- Reusable Technical Pattern

```markdown
---
title: pattern-name
type: note
tags: [language, domain]
---

# pattern-name

## Observations
- [fact] What the pattern is
- [method] How to apply it
- [tip] When to use it vs alternatives
- [fact] Why it matters (consequence of ignoring)

## Relations
- related_to [[relevant-repo]]
- related_to [[related-pattern]]
```

**Example:**
```markdown
---
title: uv-run-not-direct-invocation
type: note
tags: [python, tooling, gotcha]
---

# uv-run-not-direct-invocation

## Observations
- [fact] Always use `uv run pytest` not bare `pytest` in uv-managed projects
- [fact] Always use `uvx ruff check .` not bare `ruff`
- [method] Check for Justfile first -- `just test` wraps the correct invocation
- [tip] Direct tool invocation bypasses project configuration and venv
- [fact] This is the #1 mistake agents make in Python projects

## Relations
- related_to [[ai-rules]]
- related_to [[python-tooling]]
```

## decisions/ -- Architecture Decision Record

```markdown
---
title: decision-name
type: note
tags: [domain, scope]
---

# decision-name

## Observations
- [decision] What was decided and the chosen approach
- [fact] What alternatives were considered
- [fact] Why the chosen approach won (key tradeoff)
- [fact] What was explicitly rejected and why
- [tip] Constraints or assumptions this depends on

## Relations
- related_to [[relevant-project]]
- supersedes [[older-decision-if-any]]
```

**Example:**
```markdown
---
title: raw-sql-over-sqlalchemy
type: note
tags: [architecture, database, python]
---

# raw-sql-over-sqlalchemy

## Observations
- [decision] Use raw SQL (psycopg3) instead of SQLAlchemy ORM for the data layer
- [fact] ORM adds 3-5ms per query, unacceptable for batch operations
- [fact] SQLAlchemy considered but rejected due to N+1 query risk
- [preference] User prefers explicit SQL over magic ORM behavior
- [tip] This decision holds for read-heavy services; write-heavy may revisit

## Relations
- related_to [[python-patterns]]
- related_to [[data-layer-project]]
```

## preferences/ -- User Working Style

```markdown
---
title: preference-name
type: note
tags: [domain]
---

# preference-name

## Observations
- [preference] The specific preference or convention
- [fact] Context for why this matters
- [tip] How to apply this in practice

## Relations
- related_to [[relevant-pattern]]
```

**Example:**
```markdown
---
title: test-docstring-conventions
type: note
tags: [testing, style, python]
---

# test-docstring-conventions

## Observations
- [preference] Never add docstrings to individual test functions
- [preference] Only the test class itself gets a docstring
- [fact] Test function names should be descriptive enough on their own
- [method] Name tests as `test_<scenario>_<expected_result>`

## Relations
- related_to [[python-patterns]]
- related_to [[testing-conventions]]
```

## references/ -- External Knowledge

```markdown
---
title: reference-name
type: note
tags: [domain, source]
---

# reference-name

## Observations
- [fact] Key information from the external source
- [method] How to apply this knowledge
- [tip] Gotchas or non-obvious details

## Relations
- related_to [[relevant-project-or-pattern]]
```

For Block-specific knowledge, use `references/block/` as the directory.

## people/ -- Teammate Context

```markdown
---
title: person-name
type: note
tags: [team, domain]
---

# person-name

## Observations
- [fact] Role and primary responsibilities
- [fact] Domain expertise areas
- [tip] Best way to collaborate or communicate
- [fact] Key projects they own or contribute to

## Relations
- related_to [[project-they-own]]
```

## feedback/ -- Corrections and Lessons

```markdown
---
title: feedback-name
type: note
tags: [domain]
---

# feedback-name

## Observations
- [fact] What went wrong or what was corrected
- [fact] Why the incorrect assumption was made
- [method] The correct approach going forward
- [tip] How to avoid this mistake in the future

## Relations
- related_to [[relevant-pattern-or-repo]]
```

## projects/ -- Multi-repo Initiative

```markdown
---
title: project-name
type: note
tags: [initiative, status]
---

# project-name

## Observations
- [fact] What the initiative is trying to accomplish
- [fact] Which repos are involved
- [fact] Current status and next steps
- [decision] Key architectural choices made
- [tip] Who to ask about specific aspects

## Relations
- related_to [[repo-1]]
- related_to [[repo-2]]
- related_to [[key-person]]
```
