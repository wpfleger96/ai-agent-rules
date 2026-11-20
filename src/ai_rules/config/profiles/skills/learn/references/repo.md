# Target: Repo

A codebase the user needs to reason about fluently: brainstorming features, arguing tradeoffs, discussing the roadmap with teammates.

## Frame prompts

The user's model should cover: the main components, how a typical request or job flows through them, where state lives, and which parts are riskiest. Question ideas if they are stuck:

- Where is retry or error handling for the main external dependency?
- Which component owns the most important invariant (idempotency, ordering, auth)?
- What breaks if the core data model changes?
- Why is the system split the way it is?

## Artifacts (Step 2)

1. A component diagram (Mermaid): the 3–7 main subsystems, their boundaries, and external dependencies.
2. Two or three end-to-end traces of the most important flows, each step with `file:line`.
3. A glossary: domain terms mapped to code entities.
4. Invariants: what must always be true, and where each is enforced.
5. Seams and extension points: where new features plug in.
6. Decision records: context, decision, alternatives, consequences. Mark each EVIDENCED (commit, PR, comment, doc) or INFERRED.
7. Failure modes and blast radius.

Then spot-check: ask the user to pick three claims from the artifacts and verify them in the code themselves. Agent maps are confidently incomplete.

## Review-question targets

Invariants and where they're enforced, why major decisions were made and what was rejected, subsystem boundaries, failure modes and blast radius, known tech debt. Never file paths, function signatures, or config keys: those stay in the code and docs.
