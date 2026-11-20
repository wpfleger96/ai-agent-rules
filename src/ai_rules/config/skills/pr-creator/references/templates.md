# PR Description Templates

## Optional Structure

These are optional shapes, not required templates. A small PR can be one sentence.

```markdown
[Opening: 1-2 sentences — what changed and what it delivers]

[Context: 1-3 sentences — the problem or before-state, so reviewers understand WHY]

[Implementation: 2-4 bullets]
- [What changed and why — significant changes only, with concrete names: functions, classes, fields]

[Issue reference at end, preceded by blank line]
Resolves #123
```

Bullets name the concrete change ("Update `POST /users` to return 409 on duplicate email"), not a vague one ("Add validation", "Fix bug"). Omit details visible in the diff, line counts and internal mechanics that aren't the point of the change.

## Issue References

**Auto-close (PR fully resolves):**
```
Resolves #123
Resolves [PROJ-456](https://myorg.atlassian.net/browse/PROJ-456)
```

**Related (PR partially addresses):**
```
Relates to [PROJ-789](https://myorg.atlassian.net/browse/PROJ-789)
Relates to [other-repo#45](https://github.com/myorg/other-repo/pull/45)
```

## Optional Review Sections

Only include when non-obvious:

```
**Breaking Changes:**
- Renamed `oldMethod()` to `newMethod()` - callers must update

**Security:**
- Adds input validation to prevent XSS on user-provided names

**Performance:**
- Query now uses index on `user_id` (10x faster for large datasets)
```

## Example (illustrative — match the shape, not the wording)

```
Detect and recover from goosed LRU session eviction with `ensure_provider_configured()`, which prevents "Provider not set" errors.

`AgentManager` uses an LRU cache of 20-45 slots while the slackbot's session cache held 500 entries. When goosed evicted a session, the slackbot skipped `configure_goose()` entirely, sending `POST /reply` to a provider-less agent.

- Add `ensure_provider_configured()`: checks provider via `GET /sessions/{id}` before `/reply`; re-applies `update_provider()` if missing, invalidates local cache on 404
- Add `_sessions_being_configured` set to block concurrent callers from seeing half-configured sessions

Resolves [PROJ-234](https://myorg.atlassian.net/browse/PROJ-234)
Related: [cache-service#89](https://github.com/myorg/cache-service/pull/89)
```
