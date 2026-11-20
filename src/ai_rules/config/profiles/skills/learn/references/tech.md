# Target: Technology

A library, framework, language feature, protocol, or tool the user wants to use well and judge confidently (for example an async runtime, a database engine, a build system).

## Frame prompts

The user's model should cover: what problem it solves, its core abstractions, and how it differs from the alternatives they know. Question ideas if they are stuck:

- What is the core abstraction, and what guarantee does it give?
- What happens on failure (a crashed task, a lost connection, a partial write)?
- When would you not use it, and what would you use instead?
- What is the most common way people misuse it?

## Artifacts (Step 2)

1. Core abstractions and the guarantees each one provides, with links to official docs or source.
2. The execution or data model: what actually happens at runtime, traced through one concrete example.
3. Failure semantics: errors, cancellation, retries, consistency.
4. Comparison with 1–2 alternatives the user already knows: the tradeoff, not a feature list.
5. Common misuse and the symptom each produces.

Prefer primary sources (official docs, source code, the design paper) and link them.

## Check by hand (Step 4)

The user writes or traces a small example from memory (a minimal program, a config, a query) and predicts its behavior, including one failure case. Verify by running it when possible, otherwise against the docs or source.

## Review-question targets

Guarantees and their limits, failure behavior, when to choose it over alternatives, misuse symptoms. Not API names or flag spellings, which the user can look up.
