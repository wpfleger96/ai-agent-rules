# PR Description Templates

## Standard Structure (6-12 lines)

```markdown
[Opening: 1-2 sentences]
This PR [enables/adds/fixes/updates]... [State what changed and value delivered]

[Context: 1-3 sentences]
[Explain problem or "before this" state - help reviewers understand WHY]

[Implementation: 2-4 bullets]
- [What changed and WHY - focus on significant changes only]
- [Include concrete names: functions, classes, fields]
- [One line per bullet]

[Issue reference at end, preceded by blank line]
Resolves #123
```

## Opening Patterns

**Feature:**
- "This PR adds X to enable Y"
- "This PR implements X for Y use case"
- "This PR introduces X to support Y"

**Fix:**
- "This PR fixes X that was causing Y"
- "This PR resolves X issue with Y"
- "This PR patches X to prevent Y"

**Refactor:**
- "This PR refactors X to improve Y"
- "This PR restructures X for better Y"
- "This PR simplifies X by Y"

**Docs/Test/Chore:**
- "This PR updates X documentation to reflect Y"
- "This PR adds tests for X"
- "This PR upgrades X to version Y"

## Context Patterns

**Problem statement:**
- "Previously, X was causing Y"
- "The current implementation had X limitation"
- "Without this change, users couldn't X"

**Motivation:**
- "To support X feature, we needed Y"
- "As part of X initiative, this enables Y"
- "This unblocks X by implementing Y"

## Implementation Bullets

**Good bullets (specific, actionable):**
- "Add `UserService.validate_email()` to check format and domain"
- "Update `POST /users` to return 409 on duplicate email"
- "Refactor `calculateTotal()` to use BigDecimal for precision"
- "Migrate database schema to add `email_verified` column"

**Bad bullets (vague, obvious):**
- "Add validation" (too vague - what validation?)
- "Fix bug" (what bug? how?)
- "Update code" (obvious, no value)
- "Improve performance" (by how? what changed?)

## Formatting Standards

**Inline code:** Wrap all code identifiers in backticks in every section -- opening, context, and bullets. Scope: env vars, function/class/method names, file paths, CLI flags, API endpoints, config keys.

```
# ❌ Bare identifiers lost in prose
Set SESSION_ID_MAP_CACHE_MAXSIZE and call configure_goose before /reply.

# ✅ Identifiers clearly distinguished
Set `SESSION_ID_MAP_CACHE_MAXSIZE` and call `configure_goose()` before `POST /reply`.
```

**External references:** Format all external reference IDs as clickable links. Derive URLs from context -- never hardcode base URLs. If URL cannot be determined confidently, keep the bare ID.

| Reference type | Format |
|----------------|--------|
| Same-repo GitHub issue/PR | `#123` (GitHub auto-links) |
| Cross-repo GitHub issue/PR | `[repo-name#123](https://github.com/org/repo/pull/123)` |
| All other refs (Jira, Sentry, PagerDuty, etc.) | `[ID](url)` |

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

**Line wrapping:** Never hard-wrap prose paragraphs. GitHub reflows text automatically -- hard wraps produce narrow paragraphs that fill only half the viewport. Applies to opening and context sections. Does NOT apply to bullet items, code blocks, or tables.

## Optional Review Sections

Only include when non-obvious:

**Breaking Changes:**
```
**Breaking Changes:**
- Renamed `oldMethod()` to `newMethod()` - callers must update
```

**Security Notes:**
```
**Security:**
- Adds input validation to prevent XSS on user-provided names
```

**Performance Impact:**
```
**Performance:**
- Query now uses index on `user_id` (10x faster for large datasets)
```

**Testing Instructions (only if non-trivial setup):**
```
**Testing:**
1. Set `FEATURE_FLAG=true` in .env
2. Run `npm run seed` to populate test data
3. Navigate to /users page
```

## Complete Examples

### Feature PR

```
This PR adds email verification to user registration, preventing fake accounts and improving trust.

Currently, users can register with any email without verification. This allows spam accounts and reduces data quality.

- Add `email_verified` field to User model
- Implement `POST /verify-email` endpoint with token validation
- Send verification email via SendGrid on registration
- Block login for unverified users (returns 403)

Resolves #234
```

### Bug Fix PR

```
This PR fixes duplicate notifications being sent when users comment on their own posts.

The notification service was checking post ownership after queuing notifications, causing self-notifications.

- Move ownership check before notification queue in `CommentService.create()`
- Add unit test for self-comment scenario

Resolves #456
```

### Refactor PR

```
This PR refactors authentication middleware to use dependency injection, improving testability and reducing coupling.

The current middleware directly instantiates `TokenValidator`, making it hard to test and tightly coupled to implementation details.

- Extract `ITokenValidator` interface
- Update `authMiddleware()` to accept validator via constructor
- Simplify tests by mocking validator instead of token generation

Relates to #789
```

### Documentation PR

```
This PR updates API documentation to reflect the new pagination format introduced in v2.3.

- Add pagination examples to `/users` and `/posts` endpoints
- Document `page`, `limit`, and `total` response fields
- Add migration guide from v2.2 pagination format
```

### Breaking Change PR

```
This PR migrates to async database queries, improving performance but requiring callers to use await.

Synchronous queries were blocking the event loop, causing timeouts under load.

- Convert `UserRepository` methods to async/await
- Update all controllers to await repository calls
- Add database connection pooling

**Breaking Changes:**
- All `UserRepository` methods now return Promises - callers must `await`

Resolves #567
```

### Cross-System References PR

```
This PR adds `ensure_provider_configured()` to detect and recover from goosed LRU session eviction, preventing "Provider not set" errors.

`AgentManager` uses an LRU cache of 20-45 slots while the slackbot's session cache held 500 entries. When goosed evicted a session, the slackbot skipped `configure_goose()` entirely, sending `POST /reply` to a provider-less agent.

- Add `ensure_provider_configured()`: checks provider via `GET /sessions/{id}` before `/reply`; re-applies `update_provider()` if missing, invalidates local cache on 404
- Add `_sessions_being_configured` set to block concurrent callers from seeing half-configured sessions

Resolves [PROJ-234](https://myorg.atlassian.net/browse/PROJ-234)
Pair with [cache-service#89](https://github.com/myorg/cache-service/pull/89)
```

## Anti-Patterns to Avoid

❌ **Marketing language:**
```
This PR introduces a revolutionary new approach to user authentication
that leverages cutting-edge technology...
```

✅ **Technical language:**
```
This PR adds OAuth2 support to enable Google/GitHub login.
```

---

❌ **Obvious details:**
```
This PR fixes the user login bug.

I noticed the login wasn't working, so I debugged it and found the issue.
I fixed the bug by updating the code to work correctly.

- Updated login.js
- Fixed the validation
- Made it work
```

✅ **Specific details:**
```
This PR fixes login failures when email contains uppercase characters.

The validation was case-sensitive, rejecting valid emails like User@Example.com.

- Normalize email to lowercase in `POST /login` before validation

Resolves #123
```

---

❌ **Implementation internals:**
```
- Refactored UserService class
- Moved code from lines 45-67 to a new method
- Changed variable names for clarity
- Added comments explaining the logic
```

✅ **What and why:**
```
- Extract `validateUserInput()` to reuse validation in registration and updates
- Add rate limiting to prevent brute force attacks (max 5 attempts/minute)
```

---

❌ **No context:**
```
Add feature

- Add new function
- Update config
```

✅ **With context:**
```
This PR adds automatic retry for failed webhook deliveries, improving reliability.

Currently, webhook failures are silently dropped, causing data sync issues for integrations.

- Implement exponential backoff retry (3 attempts)
- Store failed webhooks in `webhook_failures` table
```

## Brevity Principles

1. **Every word must earn its place** - Reviewers skim descriptions
2. **Omit details visible in the diff** - Don't describe code line by line
3. **Skip obvious implementation details** - "Converted to async" only if async is the key change
4. **No metrics or line counts** - "Changed 50 lines" adds no value
5. **Focus on WHAT and WHY** - Not HOW it works internally

## Title Guidelines

**Length:** 50-70 characters

**Format:** Start with verb, be specific

**Good titles:**
- "Add email verification to user registration"
- "Fix duplicate notifications on self-comments"
- "Refactor auth middleware for dependency injection"
- "Update API docs for new pagination format"

**Bad titles:**
- "Feature" (too vague)
- "Fix bug" (what bug?)
- "Update" (update what?)
- "This PR adds a comprehensive email verification system with token generation, expiry, and email sending capabilities" (too long)
