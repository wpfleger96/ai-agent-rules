---
name: agents-md
version: 1.0.0
description: Create or update AGENTS.md with repo-specific patterns, conventions, commands, and gotchas for LLM coding agents. Use after implementing features that introduce new patterns worth documenting.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, TodoWrite
model: sonnet
---

# AGENTS.md Skill

Create or update AGENTS.md to help LLM coding agents work effectively in this repository.

## Purpose

AGENTS.md is repository-specific guidance for LLM agents. Unlike README (for humans), AGENTS.md focuses on:
- Exact commands with flags (`pytest -v` not "run tests")
- Common gotchas with specifics ("Mock HOME needs both environ and Path.home patches")
- Task-to-file mapping ("Add CLI command → src/cli.py")
- Patterns with ✅/❌ code examples

**Target audience:** LLM agents starting fresh
**Quality:** Under 100 lines, actionable, specific
**Location:** Repository root only

## Workflow

### Step 1: Determine Mode

Check if `AGENTS.md` exists at repository root:
- **CREATE:** Generate new AGENTS.md from scratch
- **UPDATE:** Read existing file, add/update sections preserving user customizations

### Step 2: Invoke prompt-engineer Skill

**REQUIRED:** Use Skill tool to invoke `prompt-engineer` skill.

**Why:** AGENTS.md is for LLM agents. Apply prompt engineering principles: explicit instructions, important info first (primacy bias), specific over vague, examples over explanations.

### Step 3: Systematic Exploration

Explore repository to gather content for AGENTS.md sections:

**PRIORITY 1: Commands (document first)**
- Check Makefile (`make help`), Justfile (`just --list`), package.json (scripts)
- Read README.md Getting Started section
- Check CI config (.github/workflows/) for canonical commands
- Document: setup, build, run, test (full + file), lint, format

**PRIORITY 2: Common Gotchas (high value)**
- Search for comments with "NOTE:", "WARNING:", "FIXME:", "HACK:"
- Read existing AGENTS.md/CLAUDE.md if present
- Complex setup requirements (env vars, external services)
- Version-specific issues

**Additional discovery:**
- Project identity: name, description, type (library/CLI/webapp)
- Project structure: source, tests, config directories
- Tech stack: language+version, framework+version, key libraries
- Key patterns: architecture (MVC/components), naming conventions
- Testing: framework, locations, commands
- Key files by task: map tasks to specific files

### Step 4: Write or Update AGENTS.md

Generate AGENTS.md using this structure (see `references/templates.md` for full template):

**Sections (in order):**
1. **Quick Commands** - Most important, goes first
2. **Project Structure** - Directory tree with annotations
3. **Tech Stack** - Versions and key libraries
4. **Key Patterns** - ✅/❌ code examples required
5. **Testing** - Commands and structure
6. **Common Gotchas** - Specific, numbered list
7. **Key Files by Task** - Task-to-file mapping table

**Quality standards:**
- Under 100 lines (60 ideal, complex repos up to 100)
- Specific: Include versions ("React 18"), exact commands, actual paths
- Examples over prose
- Commands first (most used)
- No sensitive info (no API keys, credentials, tokens)

### Step 5: File Operations

**CREATE mode:**
1. Generate complete AGENTS.md
2. Write to `{git_root}/AGENTS.md`
3. Validate: <100 lines, commands first, all sections, no secrets
4. Report: path, line count, key sections

**UPDATE mode:**
1. Compare existing vs new findings
2. Preserve user customizations
3. Add new findings, update outdated info
4. Use Edit tool for precise changes
5. Report: what was added/updated

## Post-Implementation Checklist

After implementing features, check if AGENTS.md needs updating:

**Add when:**
- [ ] New commands added (make/just targets, npm scripts)
- [ ] New patterns established (new base class, convention)
- [ ] Gotcha discovered (environment setup, mocking, timing)
- [ ] Task-to-file mapping changed (new entry points)
- [ ] Tech stack updated (new framework version, library added)

**Examples:**
- Implement new CLI command → Add to "Quick Commands" + "Key Files by Task"
- Discover HOME mocking issue → Add to "Common Gotchas"
- Establish naming convention → Add to "Key Patterns" with ✅/❌ examples
- Add new test fixture pattern → Update "Testing" section

## Boundaries

**✅ Always:**
- Read actual files (don't guess)
- Run commands to verify (`make help`, `just --list`)
- Include ✅/❌ code examples for patterns
- Preserve user customizations in UPDATE mode

**⚠️ Ask first:**
- Major restructuring of existing AGENTS.md
- Removing user-added content

**🚫 Never:**
- Include sensitive info (API keys, credentials, tokens)
- Write AGENTS.md to subdirectories (root only)
- Duplicate content already in README
- Add generic advice ("write good code")

## Tips

- **Commands most important** - Put first, use exact syntax with flags
- **Gotchas are high-value** - Specific details beat vague warnings
- **Examples beat prose** - `user_email = get_email()` not "get the email"
- **Focus on what's NOT in README** - Assume agents read README first
- **Update mode: merge, don't replace** - Preserve user customizations

See `references/templates.md` for the complete AGENTS.md structure template.
