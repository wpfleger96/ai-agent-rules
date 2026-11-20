# PLAN File Template

## Standard PLAN__TASK Structure

```markdown
# PLAN__TASK_NAME

## Overview

[1-2 paragraph summary of what this plan accomplishes, the architectural approach chosen, and key design decisions with reasoning. This section must provide enough context for a new agent to understand the plan without exploring the codebase.]

## Scope

**Features:**
- [Feature 1]
- [Feature 2]

**Components:**
- [Component 1 modified/created]
- [Component 2 modified/created]

**Files Modified/Created:**
- `path/to/file1.py` - [Role: what this file does in context of the plan]
- `path/to/file2.ts` - [Role: what this file does in context of the plan]

**Integrations:**
- [External system integration 1]
- [External system integration 2]

## Purpose

**Problem:**
[Describe the problem being solved]

**Value:**
[What value this provides]

**Requirements:**
- [Requirement 1]
- [Requirement 2]

**Context:**
[Additional context that helps understand the plan -- include architectural decisions, rejected alternatives with reasoning, and any constraints or assumptions a new agent would need to know]

## Implementation Details

### Phase 1: Setup & Foundation
   [DONE] Task 1 description
   [DONE] Task 2 description
      [DONE] Subtask 2.1
      [IN PROGRESS] Subtask 2.2
   [TODO] Task 3 description -- include approach, target files, and any dependencies on prior tasks

### Phase 2: Core Implementation (depends on: Phase 1)
   [IN PROGRESS] Task 1 description
   [TODO] Task 2 description -- include approach and target files

### Phase 3: Testing & Verification
   [TODO] Test suite for feature X
   [TODO] Integration tests

## Gotchas & Issues Encountered

Capture any pitfalls, constraints, or non-obvious behaviors discovered during implementation. A new agent should not have to re-discover these.

### Issue 1: [Title]
**Problem:** [Description of issue]
**Solution:** [How it was resolved]
**Impact:** [What breaks or goes wrong if this is ignored]
**File:** `path/to/file.py:123`

## Verification

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing complete
- [ ] Documentation updated

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `path/to/file1.py` | Modify | Added feature X |
| `path/to/file2.ts` | Create | New component for Y |

## Status

- Phase 1: [2/3] Complete
- Phase 2: [1/2] In Progress
- Phase 3: [0/2] Not Started

**Overall:** [3/7] Tasks Complete

## Plan Updates

### 2025-01-15 14:30
- Added Phase 3 after discovering need for integration tests
- Cancelled old approach for Task 2.2, using new pattern instead

### 2025-01-14 09:00
- Initial plan created
```
