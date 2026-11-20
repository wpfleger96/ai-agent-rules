# Target: Code Change

A PR, branch, refactor, or migration, usually produced with an agent. The goal is that the user can defend every behavior-changing part of it: what changed, why, the alternatives, and what breaks if it is wrong. This replaces Steps 1–5 of SKILL.md. Keep it short: a small change should take a few minutes.

## C1: Load the change and the answer key (do not show either)

- `#123` or a PR URL: the PR diff, commits, and description.
- `branch`: the diff and commit log from the merge base with the default branch (`git symbolic-ref refs/remotes/origin/HEAD`, falling back to `origin/main`) to `HEAD`.

Answer-key sources, best first: this session's own context (if the change was built here, it knows the rejected alternatives), `PLAN__*.md` files, commit bodies, the PR description, the diff itself. Do not print the diff or summarize the change yet.

## C2: Size it

Sort hunks into mechanical (renames, formatting, generated files, lockfiles, version bumps) and behavior-changing. Question budget: one per behavior-changing area plus one per invariant it relies on, at least 2 and at most 6. If the user says "full", drop the cap.

## C3: Pretest

The user writes, from memory, what the change does and why it was needed, in 1–3 sentences. Grade it.

## C4: Questions

Ask one at a time, choosing from this set for each behavior-changing area:

- Why was this change necessary?
- What approach was taken, and what alternatives were there?
- Why this approach over those?
- What invariants or assumptions does it rely on?
- What breaks, and how visibly, if it is wrong?
- What do the tests actually cover, and what do they miss?

Grade each answer on the 0–3 scale against the answer key, citing `file:line` or the commit. When the key has no recorded reason for a choice, say so instead of inventing one; that gap is itself worth fixing.

## C5: Rationale

The user drafts the "why" for the PR description in 2–4 sentences. Critique it for accuracy and missing reasons; do not rewrite it. If they want, it goes into the PR description as written.

## C6: Verdict

List every area graded 0 or 1 as "can't defend yet", with `file:line`. Suggest running `/code-reviewer` focused on those areas. If nothing scored below 2, say the change is ready to defend.

## Save

Log to the repo's topic file (`repo-<repo-name>.md`) as a session titled `change #123` or `change <branch>`, with the pretest and rationale in the user's words, the grades, and the misses. Add misses to Open misses and any review questions the user writes. Do not change the schedule.
