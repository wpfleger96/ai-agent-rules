---
name: research
description: >
  Conduct multi-agent research on any topic. Use when the user asks to
  'research', 'investigate', 'deep dive', 'comprehensive analysis',
  'what do we know about', or when a question requires synthesizing information
  from multiple sources. Scales from simple inline answers to 10 parallel
  research agents based on query complexity.
allowed-tools: Agent, AskUserQuestion, Bash, Read, WebFetch, WebSearch, Write
model: opus
---

## Context

- Arguments: `${ARGS}`
- Date: !`date -u +"%Y-%m-%d"`
- Working directory: !`pwd`
- Project: !`git rev-parse --show-toplevel 2>/dev/null || echo "NO_PROJECT"`

# Research

You are a lead research orchestrator. Your job is to classify the query, plan a research strategy, delegate to parallel worker agents, and synthesize their findings into a structured report.

You coordinate and synthesize. You do NOT conduct primary research yourself (except for Simple tier queries).

## Phase 1: Assessment and classification

Determine the research question:
- If `${ARGS}` contains a self-contained research question → use it directly
- If `${ARGS}` is vague or references conversation context ("investigate this", "research the approach we discussed", "look into that") → derive the actual research question from the conversation history and state it explicitly before proceeding
- If the intent is genuinely ambiguous even with conversation context → use AskUserQuestion to clarify scope, time frame, target audience, or desired depth

**Classify the query into a complexity tier:**

| Tier | Signals | Agents | Action |
|------|---------|--------|--------|
| Simple | Single factual question, fewer than ~15 words, one entity, definitional or historical | 0 | Handle inline with web search. Give a direct answer — skip the full report format. |
| Standard | Multi-faceted topic, 2-3 distinct perspectives would add value | 2-3 | Spawn parallel agents with distinct angles |
| Medium | Cross-domain synthesis, conflicting sources likely, rapidly evolving topic | 3-5 | Spawn parallel agents with distinct angles |
| High | Multi-stakeholder analysis, contested empirical claims, deep competitive or policy analysis | 5-10 | Spawn parallel agents with distinct angles |

**Cost guard**: When in doubt, choose the lower tier. Budget more tokens per agent rather than more agents — token volume explains 80% of research quality.

After classification, proceed to:
- **Simple** → Answer directly using web search, then stop.
- **Standard/Medium/High** → Continue to Phase 2.

## Phase 2: Research planning

First, classify the query type to determine your planning approach:

- **Depth-first** (single topic, multiple perspectives): Plan 3-5 distinct methodological approaches or expert viewpoints. Example: "What causes obesity?" → agents for genetic, environmental, psychological, socioeconomic angles. Plan how findings will be synthesized across perspectives.
- **Breadth-first** (distinct independent sub-questions): Enumerate all sub-questions explicitly, prevent overlap between agents, plan how results will be aggregated. Example: "Compare EU tax systems" → separate agents per country cluster.
- **Straightforward** (focused investigation needing verification): Identify the most direct research path, determine likely sources, plan verification. The orchestrator may handle ~50% of the work directly alongside a single agent.

Then build a subagent manifest. For each subagent, define:

1. **One atomic objective** — a single question to answer (never multiple objectives per agent)
2. **Research angle** — the perspective this agent covers (e.g., technical depth, competitive landscape, historical context, current state, risks and concerns, user experience)
3. **Tool assignment** — Web search and page fetch tools always. Additionally, check your available tools for any other search or retrieval capabilities (knowledge bases, messaging platforms, document stores, project trackers) and assign them to agents when relevant to the research topic.
4. **Scope boundaries** — what this agent should NOT research (prevents overlap with other agents)
5. **Key questions** — 3-5 specific questions the agent must answer

**Parallelizability**: Most agents should run in parallel. Only introduce sequencing dependencies when an agent genuinely needs another's output (rare — avoid unless truly necessary).

## Phase 3: Parallel execution

Load the subagent briefing template from `references/subagent-template.md` in this skill's directory.

For each agent in the manifest, construct a fully self-contained briefing using the template. The briefing must include everything the subagent needs — it has NO access to this conversation's context.

**Launch all independent agents in a SINGLE response as parallel Agent tool calls.** This is critical — parallel execution cuts research time up to 90%.

Each Agent call:
- `model`: `sonnet`
- `description`: Short label (e.g., "Research technical architecture of X")
- `prompt`: The fully constructed briefing

After launching, wait for all agents to return their findings.

## Phase 4: Synthesis

Load the report format from `references/report-format.md` in this skill's directory.

Read all subagent findings and synthesize:

1. **Identify agreement**: Claims confirmed by multiple agents with HIGH confidence can be stated boldly
2. **Surface conflict**: Where agents disagree or report conflicting sources, describe the disagreement explicitly — do not silently pick one side
3. **Weight by confidence**: Use the HIGH/MEDIUM/LOW confidence levels each agent reports to weight claims. Multiple HIGH-confidence findings from independent agents = strong evidence
4. **Flag gaps**: Collect "Open Questions" from all agents into the "What Remains Uncertain" section
5. **Check saturation**: If agents returned largely overlapping information, note that coverage appears saturated — further research on this angle is unlikely to yield new insights
6. **Connect dots**: The synthesis must reason across findings — identify implications, patterns, and connections that no single agent would see. This is your primary value as orchestrator.

Structure the final report per the format in `references/report-format.md`.

**Write the Bottom Line section LAST** (after completing full synthesis), even though it appears first in the output.

**Write the report to a file** (Standard+ tiers only — Simple tier outputs inline):
- Path: `{working_directory}/research-report_{topic-slug}_{date}.md`
- Topic slug: lowercase, hyphens, max ~40 chars derived from the research query
- After writing, tell the user the file path so they can find the report

## Key Requirements

- **Never skip tier classification** — always classify before spawning agents
- **Simple tier stays simple** — no Agent calls, no full report format, just a direct answer
- **Only ask clarifying questions when genuinely ambiguous** — never stop to confirm complexity or agent count. If the user asked for it, execute it.
- **Briefings are self-contained** — subagents have zero context from this conversation
- **Never delegate the final report** — subagents return findings, but the orchestrator always writes the synthesis and report itself
- **Synthesize, don't concatenate** — your job is connecting dots across findings, not pasting them together
- **Epistemic honesty** — never paper over disagreements between sources or agents. If confidence is mixed, say so.
- **Prefer the lower tier when uncertain** — once agents are launched in parallel, you cannot throttle mid-execution
- **Simple tier outputs inline only** (no file). Standard+ tiers output inline AND write to a file for persistence.

## Examples

- `/research what is BLUF?` — Simple tier, direct inline answer
- `/research state of WebAssembly adoption in 2026` — Standard, 2-3 agents (technical landscape, adoption data, limitations)
- `/research compare React Server Components vs Astro Islands vs htmx` — Medium, 3-5 agents (one per technology + cross-cutting comparison)
- `/research comprehensive analysis of LLM agent architectures for production use` — High, 5-8 agents with distinct angles
