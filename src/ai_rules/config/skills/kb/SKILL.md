---
name: kb
description: >-
  This skill should be used when the user asks to "save to knowledge base",
  "write a note", "persist this", "remember this pattern", "update the KB",
  or when the Stop hook instructs the agent to persist session knowledge.
  Also use when asking "search knowledge base", "what do we know about",
  or needing cross-project context from basic-memory.
---

# Knowledge Base (basic-memory)

A persistent markdown knowledge base at `~/basic-memory/` powered by the basic-memory MCP server. Knowledge persists across sessions, repos, and machines via git sync. Searchable with hybrid BM25 + vector search.

## Workflow

1. **Search first** to avoid duplicates: `search_notes(query="topic")`
2. **Read existing** if a related note exists: `read_note(identifier="note-title")`
3. **Write or update**: `write_note(title="...", directory="...", content="...")`
4. **Connect related notes** using `[[wikilinks]]` in the Relations section

## Directory Guide

| Directory | Use for | Example titles |
|-----------|---------|----------------|
| `repos/` | Per-repo commands, gotchas, patterns | "ai-rules", "goosed-slackbot" |
| `patterns/` | Reusable technical knowledge | "uv-run-not-direct-invocation" |
| `decisions/` | ADRs -- why something was chosen | "raw-sql-over-sqlalchemy" |
| `preferences/` | User working style, conventions | "test-docstring-conventions" |
| `references/` | External knowledge, company info | "block-ci-cd-pipeline" |
| `references/block/` | Block/Square-specific knowledge | "service-registry-conventions" |
| `people/` | Teammates, communication context | "tyler-sprout-expert" |
| `feedback/` | Corrections, lessons from mistakes | "no-assertions-without-verification" |
| `projects/` | Multi-repo initiative context | "slackbot-kotlin-migration" |

## Note Format

Every note uses YAML frontmatter + structured observations + relations:

```markdown
---
title: Note Title
type: note
tags: [tag1, tag2]
---

# Note Title

## Observations
- [fact] Concrete, verified information
- [tip] Practical advice for future use
- [method] How to do something specific
- [preference] User's stated preference or convention
- [decision] A choice that was made and why

## Relations
- related_to [[other-note-title]]
- depends_on [[prerequisite-note]]
```

### Observation Categories

- **`[fact]`** -- verified, objective information (e.g., "Uses Gradle wrapper, not Maven")
- **`[tip]`** -- practical guidance (e.g., "Check Justfile before guessing build commands")
- **`[method]`** -- how to do something (e.g., "Run `just check-all` for full validation")
- **`[preference]`** -- user's stated preference (e.g., "Never add docstrings to test functions")
- **`[decision]`** -- a choice with rationale (e.g., "Chose raw SQL for performance over ORM convenience")
- **`[misconception]`** -- something commonly assumed but false (e.g., "basic-memory does NOT require a running database -- it uses plain markdown files")

### GAP Annotations

When writing notes with uncertain or unverified information, mark the uncertainty explicitly:

```
- [fact] basic-memory uses hybrid BM25 + vector search [GAP: retrieval quality vs alternatives not benchmarked]
- [fact] uv tool install respects XDG_DATA_HOME [GAP: behavior on Windows not verified]
```

`[GAP: ...]` makes knowledge base weaknesses machine-readable. Agents can grep for `[GAP:` to find notes needing verification. Include: what information is missing and how to verify it.

### Tags

Use lowercase, hyphenated tags in frontmatter. Common tags: `python`, `kotlin`, `rust`, `block`, `testing`, `ci-cd`, `architecture`, `gotcha`.

### Wikilinks

Connect related notes with `[[note-title]]` in the Relations section. Use typed relations:
- `related_to [[note]]` -- general connection
- `depends_on [[note]]` -- prerequisite
- `supersedes [[note]]` -- replaces older knowledge
- `contradicts [[note]]` -- conflicting information (flag for review)

## When to Write vs Search

**Write a note when:**
- A decision was made about architecture or approach
- A repo-specific gotcha or non-obvious command was discovered
- Company-specific knowledge was learned (Block internals, service names, team conventions)
- The user corrected a previous assumption
- A reusable pattern was identified

**Search instead when:**
- Starting work in an unfamiliar repo -- `search_notes(query="repo-name")`
- Encountering a pattern already seen -- `search_notes(query="topic")`
- Needing cross-project context -- `build_context(url="memory://note-title")`

**Do NOT write:**
- Session-specific ephemeral context (what files were edited this session)
- Information obvious from the codebase (README content, import paths)
- Speculative or unverified information (unless marked with `[GAP:]`)

## Write-Back Loop

After any session where you synthesized a useful answer, consider what's worth persisting:

**When to trigger a write-back:**
- You answered a question by combining knowledge from multiple sources
- You discovered a non-obvious pattern, workaround, or gotcha not in the codebase docs
- You corrected a previous false assumption (write the correction, tag `[misconception]` for the old belief)
- The user explicitly says "remember this" or "save this"

**The write-back workflow:**
1. Search first: `search_notes(query="<topic>")` to avoid duplicating existing knowledge
2. If note exists: use `edit_note()` to add the new insight rather than rewriting
3. If new: pick the appropriate directory, use the template from `references/note-templates.md`
4. Connect with wikilinks to related notes
5. The `PostToolUse` hook auto-commits and pushes after each `write_note` call

**Schema promotion:** When a pattern repeats across 3+ notes, it may be worth promoting to `AGENTS.md` as a standing rule. Flag candidate patterns with a `[promote]` tag in the observation.

## Eval-First Methodology

Don't pre-populate the knowledge base speculatively. Let real usage reveal what's missing:

1. **Collect failing questions** -- track queries where agents struggled or gave wrong answers
2. **Test without KB** -- establish baseline: what does the agent get wrong cold?
3. **Write targeted notes** -- one note per knowledge gap, no more
4. **Re-test** -- verify the note actually fixes the failure case
5. **Repeat** -- iterate on real failures, not hypothetical ones

This prevents "note sprawl" -- a KB full of notes that never get queried because they weren't driven by actual agent failure patterns.

## KB Lint (Health Check)

Periodically audit the knowledge base for quality issues. Run manually or when the KB feels cluttered.

**Lint checks:**
1. **Stale GAPs** -- notes with `[GAP:]` annotations older than 90 days that haven't been verified
2. **Orphan notes** -- notes with no wikilinks in or out (`list_directory()` + `build_context()`)
3. **Contradictions** -- notes with `contradicts [[...]]` relations that haven't been resolved
4. **Version drift** -- notes referencing specific version numbers that may be outdated
5. **Common misconceptions** -- verify `[misconception]` entries are still accurate

**Running a lint pass:**
1. `recent_activity(depth=50)` -- find recently modified notes
2. `search_notes(query="[GAP:")` -- find unverified gaps
3. `search_notes(query="contradicts")` -- find conflicting notes
4. `list_directory()` -- browse for orphan directories

**What to do with findings:**
- Stale `[GAP:]`: verify and update, or add `[fact] Unable to verify as of <date>`
- Orphans: add wikilinks to connect them, or delete if truly obsolete
- Contradictions: reconcile, update the winner, mark the loser with `supersedes`
- Version drift: update or add `[GAP: version not verified as of <date>]`

## MCP Tools Quick Reference

| Tool | Purpose |
|------|---------|
| `search_notes(query, tags?, note_types?)` | Hybrid search across all notes |
| `build_context(url)` | Graph traversal from a note via wikilinks |
| `read_note(identifier)` | Read a specific note by title or permalink |
| `write_note(title, directory, content)` | Create or update a note |
| `edit_note(identifier, find, replace?)` | Partial edit without full rewrite |
| `delete_note(identifier)` | Delete a note (ask user first) |
| `recent_activity(depth?)` | Recently modified notes |
| `list_directory(dir_name?, depth?)` | Browse the folder structure |

## Additional Resources

### Reference Files

For complete note templates with realistic examples for each directory type:
- **`references/note-templates.md`** -- Full templates for repos/, patterns/, decisions/, preferences/, references/, people/, feedback/, projects/
