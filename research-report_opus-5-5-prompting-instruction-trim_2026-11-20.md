## Research Report: Claude Opus 5.5 prompting practices, applied to trimming ai-agent-rules instructions

**Date:** 2026-11-20 | **Confidence:** HIGH on vendor guidance and file mechanics, MEDIUM on empirical effects | **Scope:** 3 web-research agents (Anthropic's model-specific prompting docs; official docs for instruction files and skills across Claude Code, Codex, Gemini CLI, Goose, Amp; independent empirical studies) plus 1 repository audit of all 16 skills. `AGENTS.md`, `chat_agent_hints.md` and the profile fragments were analyzed directly.

---

### Bottom Line

Anthropic's Claude 5 guidance says to **prune instructions you have accumulated rather than add more**. Its specific advice:

- Delete cautions whose reason no longer holds.
- Rewrite absolute rules with their scope and reason.
- Soften CRITICAL/MUST language, which now causes over-triggering.
- Remove instructions to verify, re-check, or delegate, because Opus 5-generation models already do these and over-do them when told to.

Claude Code's docs put a number on it: **target under 200 lines per CLAUDE.md, because "longer files consume more context and reduce adherence."** `@~/AGENTS.md` imports do not reduce that cost, and the file is also loaded into every custom subagent. The deployed global file (21.6 KB of `AGENTS.md` plus the profile fragment) sits well above that target.

The independent evidence agrees on what is worth keeping. Exact commands, tooling quirks, and narrow scope guardrails measurably change behavior. Generic engineering advice, overviews, and duplicated rules add cost without improving success. Stale or wrong rules are followed even over contrary evidence in the code.

Applying this, **`AGENTS.md` can drop from about 19.6 KB to about 8–9 KB (roughly 2,700 fewer tokens per session and per subagent) without removing any rule that is specific to you.** `chat_agent_hints.md` can drop from 5.3 KB to about 2.8 KB, mostly by deleting Dropbox connector tips that the Dropbox connector's own server instructions now cover, and in one place contradict. The enabled skills hold about 26 KB of duplicated or generic text. Seven skills are already disabled, so cutting them saves nothing today.

---

### Key Findings

#### What Anthropic says changed for Opus 5.5 and the Claude 5 family

Anthropic's [Prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5) page is mostly about effort and thinking. It says existing Opus 5 prompts work unchanged, and that effort, not prompt text, is the control for how much the model thinks. The [Opus 5.5 migration guide](https://platform.claude.com/docs/en/models/opus-5-5/migration-guide) says to "re-evaluate model-specific prompt instructions." The concrete pruning guidance is on the sibling Claude 5 pages, which the general best-practices page says apply to current models:

- **Verification instructions.** [Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5): explicit verification and "double-check" instructions "cause over-verification… removing them reduces wasted tokens with no loss in quality."
- **Accumulated cautions.** [Fable 5.2](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2): "Memory files, notes, and instruction files collect cautions over time… delete cautions whose reason no longer holds, and rewrite absolute rules with their scope and reason." It also says the model treats "never" as absolute.
- **Delegation.** Fable 5.2 says to remove delegation lines from "system prompts, skills, and agent files" if the model delegates too much. The Opus 5 page says the model delegates "more readily than prior models."
- **Over-prescriptive skills.** [Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5): skills written for prior models "are often too prescriptive… and can degrade output quality," and "you can steer most behaviors with a brief instruction rather than enumerating each behavior by name."
- **Emphasis.** The [general best-practices page](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) says to replace "CRITICAL: You MUST use this tool when…" with plain "Use this tool when…". That text was written for Opus 4.5/4.6; no Opus 5.5-specific statement on capitals was found.

The same docs say to keep two things: reasons attached to rules, because the model generalizes from the reason, and positive examples of the style you want. Verbosity is the one area where Anthropic still recommends a short standing instruction for Opus 5-generation models.

Anthropic's own [Opus 5.5 consumer system prompt](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-opus-5-5) is long. It is organized in XML-tagged sections, mostly plain prose with reasons, and keeps capitalized absolutes only for safety rules. The lesson is to spend words on reasons, not on emphasis or repetition. Short is not the goal for its own sake.

#### How these files actually load

These are mechanics, read in each tool's official docs:

- **Claude Code CLAUDE.md** ([memory](https://code.claude.com/docs/en/memory)):
  - Target under 200 lines per file. `/status` warns when a file, or the combined set, is over that.
  - `@` imports "don't reduce its context cost".
  - Block-level HTML comments are stripped before injection, so the provenance header costs nothing.
  - The user-level file survives compaction (it is re-injected).
  - `/doctor prompt-audit` flags instructions written for older models.
- **Subagents** ([sub-agents](https://code.claude.com/docs/en/sub-agents)) receive the full CLAUDE.md hierarchy. The exceptions are the built-in Explore and Plan agents and agents with `omitClaudeMd: true`. Each custom subagent therefore pays for the global file again. This is also why the "if you are a subagent, don't delegate" line in `AGENTS.md` is load-bearing.
- **Skills** ([agentskills.io spec](https://agentskills.io/specification), [authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [Claude Code skills](https://code.claude.com/docs/en/skills)):
  - Only the name and description are always in context.
  - Keep the SKILL.md body under 500 lines and under about 5,000 tokens.
  - An invoked body stays in context for the rest of the session. After compaction, only its first 5,000 tokens are re-attached, so put the important instructions first.
  - `disable-model-invocation: true` removes the description from context entirely.
  - The authoring guide's core rule: "Only add context Claude doesn't already have."
- **Codex** ([AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)) stops adding instruction files at `project_doc_max_bytes`, 32 KiB by default, and the global file counts toward it. The deployed global file (about 21.6 KB) plus this repo's own `AGENTS.md` (16.6 KB) is about 38 KB, already **over the default cap**. Codex silently drops whichever project file comes later. Gemini CLI, Goose, and Amp document no size limit. Goose's docs say concise hints "reduce cost and improve performance."
- **Where else content can go** ([best practices](https://code.claude.com/docs/en/best-practices), [features overview](https://code.claude.com/docs/en/features-overview)):
  - Procedures belong in skills.
  - File-type-specific rules belong in path-scoped `.claude/rules/`.
  - Zero-exception mechanical rules belong in hooks: "If you keep adding emphasis to a CLAUDE.md line and Claude still misses it, that's a sign the line belongs in a hook."

#### What the empirical studies support

- **[Gloaguen et al., ICLR 2026](https://arxiv.org/html/2602.11988v3)** (Claude Code with Sonnet 4.5, Codex with GPT-5.2, and others):
  - Context files raised cost about 19–23% and added 2.5–3.9 agent steps, a statistically significant increase.
  - Success rates did not change significantly.
  - Overviews and content duplicating existing docs bought nothing.
  - Tool mentions such as `uv` reliably changed behavior.
- **[Zhang et al., "Guardrails Beat Guidance"](https://arxiv.org/html/2604.11088)** (Claude Code with Opus 4.6, SWE-bench Verified):
  - Narrow negative scope rules ("no unrelated refactor", "no new dependencies") helped most.
  - Generic directives ("follow code style", "handle edge cases") were inert or slightly harmful.
  - Rule count from 0 to 50 had no significant effect. The per-rule results are suggestive, not significant after correction.
- **[McMillan](https://arxiv.org/abs/2605.10039)** found no compliance effect from file size or rule position, with Bayes-factor support for the size result.
- **[Xu and Wu, Oct 2026](https://arxiv.org/html/2610.30571v1)**, the only study using Claude 5-generation models (Sonnet 5.5): **agents followed stale instruction-file text over the actual code in 90.1% of conflicting choices.**

Taken together:

- At about 50–100 rules, a file this size probably isn't causing many outright misses.
- Its measurable costs are tokens and steps, generic rules that act as noise, and stale or conflicting rules that get followed.
- Removing duplicates and resolving contradictions therefore matters more than raw byte count. Every conflict found below is a correctness risk, not just waste.

The older instruction-density benchmark ([IFScale](https://arxiv.org/html/2507.11538v1)) measured degradation only at 150 or more simultaneous instructions on pre-Claude-5 models. It is weak evidence here.

#### Recommendations for `src/ai_rules/config/AGENTS.md` (19,629 B, 274 lines)

The "Opus 5.5 rationale" column ties each change to the findings above. The byte figures are measured section sizes; the targets are estimates.

| Section (bytes now) | Action | Target | Opus 5.5 rationale |
|---|---|---|---|
| Quick Reference Checklist (481) | Delete | 0 | A pure recap of the body. Its ☐ glyphs and pipe syntax cost tokens and add nothing. |
| Delegation & Multi-Agent Orchestration (3,279) | Keep the subagent-identity paragraph and the briefing contents (objective, output format, scope, what's ruled out, worker line). Drop the three-condition spawning essay and the Implementation and Inline paragraphs. Claude Code's own Agent tool description already says nearly the same things ("every handoff is lossy", "do it yourself when it's a handful of tool calls"). | ~900 | Anthropic: remove standing delegation lines, since the model already delegates readily. Duplicating the harness's own guidance is paid twice. |
| Mandatory Worktree (1,705) | Keep the rule, applies/does-not-apply, and branch and folder naming. Move the "Worktree isolation errors" recovery steps (4 steps, about 600 B) into the skills that hit it (`code-reviewer`), or shrink them to one line. | ~800 | That failure path is rare and Claude Code-specific, yet it is paid in every session of every agent. |
| Simplicity Over Engineering (826) | Keep the 9/10 quality gate; the user reports it is useful. At most, consider dropping the last sentence ("If you can still see a way to improve, the score is lower — fix it before proceeding."), which leaves the loop with no stopping point, and A/B test the change. | ~750 | Anthropic's guidance does not mention self-scoring rubrics. The Opus 5 page targets generic "verify"/"double-check" instructions, which this gate is not: it defines what "good" means (minimalism, elegance, edge cases). Only its open-ended "iterate" tail resembles what the page warns against. Evidence for cutting it is inference only, so the user's direct experience outweighs it. |
| Project Tooling (655) | Keep the lookup order (Justfile → Makefile → package.json → `uv run` → cargo). Remove CRITICAL/ALWAYS/NEVER and the "#1 agent mistake" line. | ~350 | Commands are the content the studies show changes behavior. Emphasis is the part Anthropic says causes over-triggering. |
| Security-First (370), Software Engineering Standards (256), Testing Standards (359) | Delete the generic items: SQL injection, XSS, clear naming, arrange-act-assert, "skip getters/setters". Keep your own conventions in one line: `test_<scenario>_<result>`, and error handling at boundaries only. | ~200 | The model already knows these. Zhang et al. found generic directives inert or harmful. |
| Collaboration Protocol (792) | Keep the "failed operation → stop and report" rule and "check docs before assuming an API supports something". Drop the arrow-chain workflow and "ask before guessing", which the harness already instructs. | ~350 | Fable 5.2 says scope absolutes and add the reason. The NEVER×3 block reads as absolute. |
| Debugging Circuit Breaker (593) | Keep. Drop the "Why" line. | ~450 | This behavior is not a default and is specific to you, which is the kind of rule worth keeping. |
| GitHub Integration + PR Maintenance + PR Titles + PR Description + PR Cross-Referencing + Commit Messages (4,558) | Condense to one "Git and PRs" section. Keep the conventional-commit format, the non-obvious type rules (moving code is not `feat`; code plus docs takes the primary type), the four PR-description prohibitions as one sentence, "rewrite the description after each push", and the "related means functionally coupled" definition. Move the PR-URL → worktree lookup workflow and the stack/back-fill procedure into `pr-creator`. Drop the 5-row type table, which the model already knows. | ~1,500 | Procedures belong in skills. Generic conventional-commit knowledge adds nothing. |
| Inline Code + External References + Line Wrapping + Non-Breaking Spaces (1,602) | Combine into about 4 lines: backtick identifiers; link external IDs, but keep a bare ID if the URL is unknown; don't hard-wrap prose; no NBSP. Drop the ❌/✅ example and the table. | ~450 | These rules are clear without examples. The NBSP rule is a good hook candidate: a `PostToolUse` grep for U+00A0 in Claude Code. |
| Response Style (1,785) + Writing for a Reader (1,873) | Merge. Keep answer-first, no pleasantries or apologies, no re-hedging, one bounded action per user step, completion reports with a verify command, and the five "writing for a reader" bullets in shorter form. Cut repetition: "include all relevant information" and "get right to the point" each appear twice, and the "Check before sending" and "Why" paragraphs restate the bullets. | ~1,700 | This is real preference content specific to you, so condense it rather than delete. Keep the reasons. Anthropic says the model generalizes from them. |
| Workflow Management (330), Planning (94) | Keep "restate position in progress updates". Drop "create TODO list", which the harness already prompts for. Keep Planning. | ~250 | Duplicates the harness. |

Total target is about 8.5 KB, roughly 120 lines, under Claude Code's 200-line guideline even with the profile fragment appended.

**Profile fragments.**

- `personal.md` (3.8 KB) is almost all specific to you and should stay. The "Why" paragraph under Agent-Authored Commits can go.
- `work.md` (2.5 KB) states the WARP VPN toggle twice, once for uv and once for npm, and has emphatic "NOT broken / NOT corrupted / Do NOT…" lines. Merge it into one section: "WARP routes PyPI and npm through Artifactory, which breaks personal repos; wrap network-touching `uv`/`npm`/`pnpm` commands in `warp-cli disconnect` / `connect`; don't debug caches or metadata." That brings it to about 1.3 KB. The anti-debugging line is a legitimate guardrail. Keep it as one sentence with its reason, not three capitalized NOTs.

#### Recommendations for `chat_agent_hints.md` (5,278 B)

- **Dropbox Connector Tips (lines 35–61, about 2.6 KB): cut to about 500 B.**
  - The Dropbox connector now ships server instructions covering path handling, pagination, write confirmation, and `list_folder` recursion. They were visible in this session.
  - Line 53 *contradicts* them. It says "prefer the returned `id` or `path_display`", while the connector says prefer `id`, then `ns_path`, and use the display path "only as a last resort".
  - Given the Xu and Wu result, keeping a stale copy is a liability, not just waste.
  - Keep the folder map and the two pieces of knowledge specific to your Dropbox: search by document type, provider, or date-named file rather than by diagnosis; always scope searches with `path`, especially to avoid `/Backups/`.
- **Response-style paragraphs (lines 5–19, about 1.9 KB): light merge, about 1.5 KB.**
  - "Get to the point… answer the question that was asked" (line 11) overlaps "Lead with the answer" (line 13).
  - "Include all relevant information" (line 9) overlaps "Give in-depth technical explanations" (line 17).
  - These rules are worth the words. This is the part to keep.
- **Duplicated context in Claude Code cloud sessions.**
  - In this session, the claude.ai preferences were injected into the system prompt alongside `AGENTS.md`. The response-style rules and the Dropbox block are therefore paid twice in Claude Code on the web.
  - Shrinking the Dropbox block is the main saving there.
  - Only observed in this one cloud session; not checked for the desktop app or the CLI.

#### Skills (from the repository audit, spot-checked)

- **Disabled skills.** 7 of 16 skills are disabled (`disabled: true`, filtered by `managed_skills()` in `src/ai_rules/skills.py`): `agents-md`, `crossfire`, `doc-writer`, `prompt-critique`, `prompt-engineer`, `session-search`, `test-writer`. They cost no context, so the decision is whether to delete them.
  - `prompt-engineer` and its 30 KB `prompt_engineering_guide_2025.md` are outdated. They cover Sonnet 4.5/Opus 4.1 model tables and the old `budget_tokens` thinking API, and say "MUST be extremely explicit", the opposite of current guidance.
  - `prompt-critique` and `agents-md` both hard-depend on `prompt-engineer`, so re-enabling either alone breaks it.
  - Recommend deleting those three plus `doc-writer` and `test-writer`, which are almost entirely generic. `test-writer` also contradicts the test naming convention in `AGENTS.md`.
- **Descriptions are already cheap.** About 1,375 characters (about 345 tokens) across the deployed skills. Shortening the four longest saves about 100 tokens. Fix `dev-docs`'s description, which says `PLAN.md` while the body writes `PLAN__<TASK>.md`.
- **Largest savings in enabled skills.** These are paid only on invocation, but then stay in context for the rest of the session:
  - **`pr-creator`, about 9 KB of 15 KB.**
    - `references/templates.md` restates the `AGENTS.md` markdown rules verbatim (including the same `SESSION_ID_MAP_CACHE_MAXSIZE` example).
    - It has six full example PRs and five anti-pattern pairs.
    - It lists "This PR adds X…" opener phrases that contradict both `writing-as-will` and the file's own line 5.
    - `SKILL.md` lines 64–68 restate the PR rules from `AGENTS.md`.
    - Keep one example and the PLAN-file and HEREDOC mechanics.
  - **`dev-docs`, about 9 KB.** Three full PLAN templates, where one would do. Its "Critical Requirements" recap restates Phases 2–3.
  - **`code-reviewer`, about 4.5 KB of 21 KB.**
    - Three overlapping principle lists that contradict each other: "surface ALL legitimate issues—never skip" versus "Skip nitpicks".
    - The severity framework appears three times.
    - The review lenses are mostly generic questions.
    - You need to pick the nitpick policy before trimming.
  - **`research`, `worktree-cleanup`, `rebase`, about 1–2 KB each.** All are recap "Rules" or "Key Requirements" sections that restate the body. `rebase`'s Python row uses bare `ruff`/`pytest`, contradicting `AGENTS.md`'s `uv run` rule.
- **Drop "You are an expert…" role lines** from `code-reviewer`, `pr-creator`, and `rebase`.
- **Don't trim** the load-bearing procedure:
  - the `code-reviewer` boundary-relevance tiers and verdict order;
  - the `worktree-cleanup` classification tree and its `git cherry` and `lsof` gotchas;
  - the `rebase` squash-first and `--force-with-lease` steps;
  - the `handoff` four-backtick fence rule;
  - nearly all of `writing-as-will`.
- **Gap, not waste.** None of the subagent briefing templates (`code-reviewer`, `research`, `rebase`) include the "you are the worker, do not delegate further" line that `AGENTS.md` requires. If the Delegation section shrinks as proposed, that line should live in these templates.

---

### What Remains Uncertain

- No study measures instruction-file length tolerance on Opus 5.5 specifically. The Opus 5.5 page itself says nothing about prompt length or capitals. The emphasis guidance comes from the Opus 4.5/4.6 and Fable 5.2 pages.
- The size effect is unresolved. Lulla et al. (secondary summary only) reported context files *reduced* Codex runtime and output tokens, the opposite direction from Gloaguen et al.
- Whether the `${ARGS}` placeholders in several skills are substituted by Claude Code, or work only because raw arguments get appended. This needs a quick test.
- Whether `pr-creator`'s `$1` is the first or second argument under Claude Code's indexing.
- Whether the claude.ai preference injection seen in this cloud session also happens in the desktop app or the CLI.
- The exact combined-size threshold behind Claude Code's `/status` warning was not captured.

---

### Sources and Confidence

| Finding | Source types | Confidence |
|---|---|---|
| Remove verification, delegation, and caution accumulation; scope absolutes; soften emphasis | 4 official Anthropic prompting pages, fetched in full | HIGH (MEDIUM for applying them to 5.5 specifically) |
| Under 200 lines per CLAUDE.md; imports don't reduce cost; subagents inherit CLAUDE.md | Claude Code memory and sub-agents docs | HIGH |
| SKILL.md under 500 lines and about 5k tokens; only metadata always loaded | agentskills.io spec, Anthropic authoring guide, Claude Code skills docs | HIGH |
| Codex 32 KiB combined cap includes the global file | Codex AGENTS.md docs | HIGH |
| Context files add about 20% cost and don't significantly lift success; generic and duplicated content is wasted | Peer-reviewed ICLR 2026 paper plus a corroborating preprint | MEDIUM–HIGH |
| Narrow scope guardrails help; generic directives are inert | One preprint (Opus 4.6), not significant after correction | MEDIUM |
| Stale instruction text overrides code in about 90% of conflicts (Claude 5-generation model) | One preprint, Oct 2026 | MEDIUM |
| Dropbox tips conflict with the connector's own path guidance | Direct comparison in this session | HIGH |
| 7 skills disabled; pr-creator duplicates AGENTS.md | Repository audit, spot-checked by grep | HIGH |

---

### Methodology

- **Classification:** Medium. The topic is changing quickly and combines vendor docs, empirical studies, and a repository audit.
- **Agents deployed:** 4.
- **Research angles:** Anthropic's Opus 5.5 and Claude 5 prompting guidance; official mechanics and size guidance for instruction files and skills across five agents; independent empirical studies; a line-level audit of all 16 skills.
- **Tools used:** web search and fetch (platform.claude.com, code.claude.com, agentskills.io, anthropic.com, arxiv.org, Codex, Gemini, Goose, and Amp docs); local file reads, `wc`, and `grep` on the repository.
- **Coverage notes:** The vendor docs and empirical results agree closely on *what* to cut. Coverage of measured format effects (tables versus prose, emphasis ablations) is thin, and no source measured them for instruction files.
