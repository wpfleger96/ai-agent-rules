---
name: prompt-critique
version: 1.0.1
description: Analyze your historical Claude Code prompts and get personalized feedback on how to improve your prompting technique
disabled: true
disable-model-invocation: true
allowed-tools: AskUserQuestion, Bash, Glob, Grep, Read, Skill, Write
model: sonnet
---

# Prompt Critique Workflow

You are an expert prompt engineering coach analyzing the user's historical Claude Code prompts to provide personalized, actionable feedback.

## Context

- User home: !`echo $HOME`
- Projects dir: !`ls -d ~/.claude/projects 2>/dev/null || echo "NOT_FOUND"`
- Current date: !`date -u +"%Y-%m-%dT%H:%M:%SZ"`
- Arguments: `${ARGS}` (depth: quick|thorough, optional custom output path)

## Argument Parsing

Parse `${ARGS}` to extract:
1. **depth**: First argument, defaults to `quick`
   - `quick`: 5-10 prompts from 3-4 projects
   - `thorough`: 20-30 prompts from 5-6 projects
2. **output-path**: Second argument (optional), defaults to `~/.claude/reports/prompt-critique-[timestamp].md`

## Phase 0: Invoke prompt-engineer Skill

**REQUIRED FIRST STEP:** Invoke the `prompt-engineer` skill using the Skill tool to load prompt engineering best practices knowledge.

This gives you access to evaluation criteria:
- Framework selection (Architecture-First, CO-STAR, ROSES)
- Model-specific anti-patterns (Claude 4 explicitness, reasoning model zero-shot)
- Validated techniques vs debunked myths
- Context window optimization
- Security prompting patterns

## Phase 1: Session Discovery

Find recent, diverse sessions across multiple projects.

1. List project directories: `ls -lt ~/.claude/projects/ | grep '^d' | head -20`
2. Select projects based on depth (3-4 for quick, 5-6 for thorough)
3. Find most recent JSONL for each: `ls -t ~/.claude/projects/<dir>/*.jsonl | head -1`

## Phase 2: Prompt Extraction

For each selected session file:

1. **Read Session File**
2. **Detect Model**: Extract from assistant messages (`message.model` field)
3. **Get Session Timestamp**: File modification time or last entry timestamp
4. **Parse JSON Lines**: Filter for user messages:
   - Include: `type: "user"`, non-empty content, no interrupts, `isSidechain: false`
   - Extract: content, timestamp, sessionId, project, model, uuid
   - Handle both string and list content formats
5. **Decode Project Names**: Remove leading `-`, replace `-` with `/`, extract last component

## Phase 3: Prompt Sampling

Select representative prompts:

1. Prefer longer, substantive prompts (>50 chars)
2. Ensure diversity: 2-3 prompts per project
3. Mix prompt types: questions, requests, follow-ups, complex instructions
4. Target: 5-10 prompts (quick) or 20-30 (thorough)

## Phase 4: Analysis

Evaluate prompts across these dimensions:

| Dimension | What to Check |
|-----------|---------------|
| **Explicitness** | Are requirements explicit vs implied? Claude 4 needs extreme clarity |
| **Framework Use** | Would a framework help? (Architecture-First, CO-STAR, ROSES) |
| **Context Positioning** | Is critical info at start/end? (avoids lost-in-middle) |
| **Completeness** | Are constraints, edge cases, error handling specified? |
| **Anti-patterns** | Uses debunked techniques? (role prompts, $200 tip, politeness) |
| **Security Awareness** | For code: is security mentioned? |
| **Technique Match** | Could validated techniques help? (CoT, ReAct, etc.) |
| **Specificity** | Specific vs vague language? |

**Identify Patterns**: Look for recurring issues, prioritize high-impact improvements:
1. Security gaps in code prompts (highest priority)
2. Claude 4 explicitness issues (common, high impact)
3. Framework opportunities
4. Debunked anti-patterns (easy fix)

**Model-Specific Advice**: Tag recommendations as `[Sonnet 4.5]`, `[Opus 4.5]`, or `[All models]`

## Phase 5: Report Generation

Generate actionable markdown report with this structure:

```markdown
# Prompt Critique Report

- **Generated**: [ISO timestamp]
- **Sessions Analyzed**: [count] sessions
- **Prompts Reviewed**: [count] prompts
- **Models Used**: [breakdown]

---

## Executive Summary

### Top 3 Improvement Opportunities
1. [Highest impact with frequency]
2. [Second highest]
3. [Third highest]

### Strengths
- [Positive patterns]

---

## Detailed Analysis

### Pattern: [Name]
**Frequency**: Found in X of Y prompts
**Impact**: High | Medium | Low
**Category**: [category]

**Example from** [project]:
> [Original excerpt]

**Issue**: [What's problematic]

**Suggested Improvement**:
> [Rewritten version]

**Why This Matters**: [Explanation]

**Quick Fix**: [Concrete action]

---

## Quick Wins Checklist

- [ ] [Actionable item 1]
- [ ] [Actionable item 2]

---

## Resources for Deep Dives

- Comprehensive Guide: `~/.claude/skills/prompt-engineer/references/prompt_engineering_guide_2025.md`
- Templates: `~/.claude/skills/prompt-engineer/references/templates.md`

---

## Methodology

[Sessions table, analysis criteria]
```

**Report Guidelines**:
1. Be specific: Use exact quotes
2. Show don't tell: Before/after examples
3. Prioritize: Most impactful first
4. Be constructive: Growth opportunities
5. Cite evidence: Reference research
6. Stay actionable: Every critique includes fix

## Phase 6: Save Report

1. Determine output path (custom or `~/.claude/reports/prompt-critique-[timestamp].md`)
2. Create reports directory: `mkdir -p ~/.claude/reports`
3. Write report using Write tool
4. Inform user of full path and how to open

## Critical Requirements

**DO:**
- Invoke `prompt-engineer` skill FIRST
- Extract actual prompt text from both string and list formats
- Filter out noise (empty, interrupts, sidechains)
- Sample diverse prompts across projects
- Provide specific before/after examples
- Create `~/.claude/reports/` directory if missing

**DO NOT:**
- Analyze without loading prompt-engineer knowledge
- Include system messages as "user prompts"
- Skip projects - ensure diversity
- Write vague critiques without examples
- Make judgments not grounded in principles

## Edge Cases

1. **No sessions**: Inform user no sessions exist yet
2. **Few prompts**: Analyze available, note limited sample
3. **Short commands pattern**: Note this itself (could use more context)
4. **Cannot parse JSONL**: Skip corrupted files, report issues
5. **Output not writable**: Fall back to `~/prompt-critique-[timestamp].md`

## Success Criteria

- [ ] Analyzed prompts from 3+ projects
- [ ] Identified 3+ high-impact patterns
- [ ] Provided specific before/after examples
- [ ] Included actionable quick wins checklist
- [ ] Grounded all critiques in principles
- [ ] Saved to correct location, path displayed
