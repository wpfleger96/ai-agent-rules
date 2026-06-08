# Semantic Verification Subagent Briefing

Use this template to construct briefings for Phase 4 subagents. Subagents have NO conversation context — every briefing must be fully self-contained.

## Briefing Template

```
You are a focused semantic verification agent. Your scope is narrow — verify exactly what is assigned.

REPO: [absolute path to repository root]
ECOSYSTEM: [rust|node|python|go|unknown]

ASSIGNMENT: [STALE_IMPORTS | STALE_API | SIGNATURE_COMPAT]

RISK MATRIX ENTRIES:
[paste relevant entries from Phase 1c — one per line, format: FILE | RISK_TYPE | WHAT_CHANGED]

OUR BRANCH FILES:
[one file path per line — all files the branch touches, from git diff --name-only TARGET..HEAD]

TASK:
[copy the assignment-specific instructions below verbatim]

OUTPUT FORMAT:

## Findings: [Assignment]

### Issues
For each issue:
- **File**: `<path>:<line>`
  **Stale**: `<old reference>`
  **Correct**: `<new reference>`
  **Confidence**: HIGH / MEDIUM / LOW

### Ambiguous Cases
[cases where correctness cannot be determined with certainty]

RULES:
- Read FULL file contents for files with suspected issues — grep line numbers alone miss context
- List every file checked, even if clean
- Do NOT fix issues — only report. The orchestrator handles fixes.
- If a reference was already corrected by the rebase, mark it "already correct"
```

## Assignment-Specific Instructions

### STALE_IMPORTS

Check every file in OUR BRANCH FILES for import/use paths that reference names or paths that no longer exist after TARGET's refactoring.

**Rust:**
- `use <old_crate_name>::` where crate was renamed or split (check Cargo.toml [dependencies] for the correct crate name)
- `use crate::<old_module>::` where a module was moved (e.g., `mod.rs` relocated)
- `use super::<name>` where a sibling module was deleted or merged

**TypeScript/JavaScript:**
- `import ... from '<old_path>'` where file was moved or renamed
- `require('<old_path>')` — same
- Barrel file re-exports (`export * from '<old_path>'`)

**Python:**
- `from <old_module> import` where module was renamed or reorganized
- `import <old_module>` — same

**Go:**
- `import "<old_package_path>"` where package was moved

For each risk matrix entry of type RENAME/MOVE/SPLIT, grep OUR BRANCH FILES for the old name.

### STALE_API

For each renamed type, function, constant, or method in the risk matrix:
1. Identify the OLD name and the NEW name
2. Grep OUR BRANCH FILES for usages of the OLD name
3. For each hit, verify it's actually a usage (not a definition or comment)

Common patterns:
- `pub struct OldName` → `pub struct NewName` — grep for `OldName` in type positions
- Method rename — grep for `.old_method(` calls
- Constant rename — grep for `OLD_CONST` usages
- Route/namespace prefix change (e.g., `_goose/foo` → `_goose/unstable/foo`) — grep for the old prefix in string literals

### SIGNATURE_COMPAT

For each function/method with a changed signature in the risk matrix:
1. Read the NEW signature from TARGET's version of the file
2. Find all call sites in OUR BRANCH FILES
3. Verify each call site matches the new signature:

**Rust-specific checks:**
- Ownership/borrow: `fn foo(x: Config)` → `fn foo(x: &Config)` — callers passing `&x` now create `&&Config`
- Return type: `fn bar() -> Config` → `fn bar() -> &Config` — callers doing `&bar()` create `&&Config`
- Added parameters — callers missing the new argument
- Changed generics — callers using old concrete type

**TypeScript-specific checks:**
- Optional → required parameter
- Type narrowing changes
- Return type changes (Promise wrapping, union changes)
