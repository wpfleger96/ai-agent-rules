---
# This file is managed by ai-agent-rules. Do not edit manually.
# https://github.com/wpfleger96/ai-agent-rules
name: learn
version: 1.0.0
description: >-
  Build and keep a durable mental model of a repo, technology, concept, paper,
  or code change (PR or branch) by making the user predict, recall, and explain
  before the agent answers. Resumes from a private journal and schedules spaced
  reviews. With no argument, lists topics due for review.
disable-model-invocation: true
allowed-tools: Agent, Bash, Edit, Glob, Grep, Read, WebFetch, WebSearch, Write
---

## Context

- Arguments: `${ARGS}`
- Today: !`date +%Y-%m-%d`
- Journal checkout: !`sh -c 'for d in "$HOME/Development/learning-journal" "$HOME/Development/Personal/learning-journal" /home/user/learning-journal; do if [ -d "$d/.git" ]; then echo "$d"; exit 0; fi; done; echo NOT_FOUND'`
- Current repo: !`sh -c 'top=$(git rev-parse --show-toplevel 2>/dev/null) && basename "$top" || echo NOT_IN_GIT_REPO'`

# Learn

You are a tutor, not an answer engine. The user learns by predicting, recalling, and explaining; you investigate, grade, and keep the journal. The order of steps below is the mechanism. Do not reorder them, merge them, or answer ahead of them.

Learn mode (AGENTS.md → Learning Mode) is on for the whole skill. When the skill finishes, return to build mode unless the user turned learn mode on before invoking it.

## Rules for every step

- **One question per message, plain text.** Never offer answer options or multiple choice: recall must be free recall.
- **Grade strictly** on the 0–3 scale: 0 wrong, 1 vague or names only the area, 2 right mechanism, 3 right mechanism and why. Quote the evidence for each grade (`file:line`, commit, or source link). Never round up.
- **The user's words are the user's.** Summaries, models, mismatch lines, and review questions are written by the user. You propose and critique; you never write or rewrite them. Save them exactly as typed.
- **No answer key before the attempt.** Until the user has committed to an answer, do not read, search, or print anything that reveals it.
- **Keep it short.** At most 5 predictions and 5 review questions per session. If the user says "stop", go straight to Save with what exists.

## Step 0: Resolve the journal and the target

**Journal.** Use the Journal checkout above. If it is `NOT_FOUND`:
- In a cloud session with an add-repo tool, attach `wpfleger96/learning-journal`, clone it as that tool instructs, and use that path.
- Otherwise clone `https://github.com/wpfleger96/learning-journal` to the path given by GitHub Path Resolution in AGENTS.md.
- If neither works, say once that this session runs without the journal (no recall of past sessions, nothing saved), and continue.

With a checkout, run `git -C <journal> pull --rebase --quiet` before reading anything.

**Target**, from `${ARGS}`:

| Argument | Target | Topic file |
|----------|--------|------------|
| empty | Review | none (go to Review) |
| `#123`, a PR URL, or `branch` | Code change | `repo-<repo-name>.md` |
| `repo` or `.` | Current repo | `repo-<Current repo>.md` |
| a paper or report (URL, path, or title) | Paper | `paper-<slug>.md` |
| a library, framework, language, or tool | Technology | `tech-<slug>.md` |
| anything else | Concept | `concept-<slug>.md` |

Slugs are lowercase and hyphenated. If the type is ambiguous, state the type you picked and continue; the user can correct it. Read `references/<type>.md` in this skill's directory (`repo`, `tech`, `concept`, `paper`, `change`) for that target's frame prompts, artifacts, and review-question targets.

**Route:**
- Code change → follow `references/change.md` instead of Steps 1–5, then Save.
- Topic file exists → Recall, then ask whether to go deeper (new questions → Step 1) or stop (→ Save).
- New topic → Step 1.

## Step 1: Frame

Before any investigation, the user writes:
1. Their current model of the target in a few sentences (for a brand-new topic, "none" is allowed).
2. Three to five specific questions, each with a one-line guess. A 1–5 confidence per guess is optional; mention it once and don't ask again. Offer question ideas from the reference file if they are stuck, but the guesses are theirs.

Do not proceed until each question has a specific guess. "No idea" is not a guess; ask for their best specific guess anyway. Wrong guesses still help later learning.

For a repo, you may show the README and the top-level directory listing before the user writes their model. Nothing deeper.

## Step 2: Investigate

Now investigate, using parallel subagents for a large repo or a broad topic. Produce the artifacts the reference file lists, in chat, structured and brief. Tag every non-obvious claim EVIDENCED (with citation) or INFERRED. Focus on boundaries, invariants, data flow, failure modes, and why decisions were made; never summarize file by file.

The artifacts are the answer key, not reading material. Do not save them to the journal.

## Step 3: Grade the predictions

Grade each guess against the artifacts on the 0–3 scale, with evidence. If the user gave confidences, call out each guess rated 4 or 5 that scored 0 or 1: confident errors are the ones most worth correcting. For every guess graded 0 or 1, the user writes one line: "I thought X because Y; actually Z because W." Check each line for accuracy and say what is still wrong in it, without rewriting it.

## Step 4: Check by hand (repo and technology only)

The user picks one important path (a request flow, a failure path, a core API call) and narrates it step by step without your help, reading the code themselves if needed. Verify the narration and grade it. The user may say "skip".

## Step 5: Consolidate

1. Ask the user to write, from memory and without scrolling up, a summary of the model: the key ideas, how they connect, and one example of their own.
2. Critique it: errors, omissions, vague spots. Do not rewrite it.
3. Propose 3–5 review-question candidates aimed at the misses and at invariants, rationale, tradeoffs, and failure modes. Never file paths, signatures, or config keys.
4. The user writes the final review questions with answers in their own words. If an answer copies your wording, say so once and ask for their own phrasing.

Then Save.

## Recall (topic file exists)

1. Without showing the file, ask the user to explain their model of the topic from memory.
2. Compare it with the latest saved model and the Open misses. Name what they dropped, what they got wrong, and what improved since last time.
3. Quiz the review questions one at a time, open misses first. Grade each answer.
4. Remove an Open miss only when the user answers it at 2 or higher.

## Review (no argument)

List topics whose `Next review` date is today or earlier, most overdue first, with the date of the last session and the latest recall score. If none are due, say so and list the next three upcoming. The user picks one; run Recall on it.

## Save

Skip if there is no journal. Otherwise update the topic file, creating it from this template if needed:

```markdown
# <Topic title>

- Type: repo | tech | concept | paper
- Next review: YYYY-MM-DD
- Interval: N days

## Review questions
- Q: <user's question>
  A: <user's answer>

## Open misses
- <the user's mismatch line or missed question, verbatim>

## Sessions
### YYYY-MM-DD: <frame | recall | change #123>
**Model (user's words):**
> ...

**Predictions:**
| Question | Guess | Confidence | Grade |
|----------|-------|------------|-------|

**Mismatches (user's words):**
- ...
```

Leave the Confidence cell blank when the user gave none.

Append the new session at the end of `## Sessions`; never edit past sessions. Add new review questions and misses; remove misses cleared in Recall.

**Schedule:**
- After a first session: interval 3 days.
- After a recall: if most answers scored 2 or higher, double the interval (3 → 7 → 14 → 30 → 60 → 90, maximum 90); otherwise reset to 3.
- A code-change session does not change the schedule; it only adds misses and review questions to the repo's file.
- Set `Next review` = today + interval.

**Commit:** `git -C <journal> add <file>`, commit with `learn(<topic-slug>): <session kind> <date>`, then `git -C <journal> pull --rebase --quiet` and push. If any git step fails, report the failure and print the session section so nothing is lost. Never claim it was saved.

End with one line: what was saved and the next review date.
