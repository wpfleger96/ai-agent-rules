# Distill Summary Template

Produce a structured summary following this exact 9-section format. Each section has a **preservation rule** that controls how content is captured.

**Verbatim rule:** When a section is marked **verbatim**, copy identifiers EXACTLY as they appear in the transcript — file paths, function names, class names, variable names, branch names, error codes, CLI flags. Never paraphrase, abbreviate, or "clean up" technical identifiers.

---

## 1. Primary Request and Intent

*Preservation: Summarize concisely*

What is the user trying to accomplish and why? State the high-level goal, not the individual steps. If the goal evolved during the session, capture the current understanding.

## 2. Current Work State

*Preservation: **Verbatim** identifiers*

What is the exact current state of work? What was the last thing completed? What is actively in progress? Include:
- Current branch name (verbatim)
- Files currently being modified (verbatim paths)
- Current phase/step of the task
- Any active debugging or investigation state

## 3. Key Technical Decisions

*Preservation: **Verbatim** identifiers*

Architecture choices, design patterns, and trade-offs that were made during the session. For each decision, capture:
- What was decided
- Why (the reasoning or constraint)
- What was rejected and why (if discussed)

## 4. Files and Code

*Preservation: **Verbatim** paths*

Every file that was read, created, or modified. For each file:
- Full path (verbatim)
- What role it plays in the current task
- What was done to it (created, modified specific sections, read for context)

## 5. Errors and Fixes

*Preservation: **Verbatim** error strings*

Every error encountered and its resolution. For each:
- The exact error message or code (verbatim)
- What caused it
- How it was fixed (or if it's still unresolved)

## 6. Problem Solving Progress

*Preservation: Summarize*

Approaches tried and their outcomes. What worked, what didn't, and why. Current direction of investigation. Include dead ends — knowing what was already tried prevents re-exploration.

## 7. User Instructions and Constraints

*Preservation: **Verbatim** — MOST CRITICAL SECTION*

EVERY instruction, preference, or constraint the user stated during the session. This is the most important section because user constraints are the #1 casualty of lossy compaction. Capture:
- Explicit instructions ("don't do X", "always Y", "use Z approach")
- Stated preferences ("I prefer...", "let's not...", "that's the wrong approach")
- Corrections ("no, not that — do this instead")
- Scope limitations ("only touch X", "leave Y alone")

Copy the user's words as closely as possible. Do not paraphrase constraints into softer language.

## 8. Pending Tasks

*Preservation: Actionable detail*

Numbered list of remaining work. Each item must have enough detail for a cold-start agent to execute without re-exploring the codebase:
1. [Task] — [what to do, which files, what approach]
2. [Task] — [what to do, which files, what approach]

## 9. Next Step

*Preservation: Enough context to execute cold*

The single most important next action. Include:
- What to do
- Which file(s) to touch
- Any context needed to execute without reading the full summary

---

## Recovery

If details are missing from this summary, the full masked transcript is available at:
`{{BACKUP_PATH}}`

Use `Read` on this file to recover specific details.
