# Research Report Format

Use this format for Standard, Medium, and High tier research output. Simple tier queries get a direct answer without this structure.

**File output**: For Standard+ tiers, the orchestrator writes the final report to a file in the working directory: `research-report_{topic-slug}_{date}.md`. The topic slug is lowercase with hyphens, max ~40 chars. The file provides persistence — the report is also output inline in the conversation, but the file ensures it survives context compaction and is easy to reference later.

---

## Template

```markdown
## Research Report: [Topic]

**Date:** [date] | **Confidence:** HIGH/MEDIUM/LOW | **Scope:** [e.g., "3 agents covering technical landscape, adoption data, and limitations via web search"]

---

### Bottom Line

[2-4 sentences stating the most important conclusions directly. Bold 1-3 critical facts. No hedging unless genuinely uncertain — if the evidence is strong, state it plainly.]

[Write this section LAST after completing the full synthesis, even though it appears first.]

---

### Key Findings

#### [Theme 1 — descriptive heading]

[Narrative prose, 3-7 sentences. Synthesize across agent findings — connect dots, identify implications. Use epistemic honesty: "The evidence strongly suggests X" when confident, "Sources disagree on Y — [perspective A] vs [perspective B]" when conflicting. Bold critical facts.]

#### [Theme 2 — descriptive heading]

[Same structure. Each theme should represent a distinct facet of the research question, not a per-agent dump.]

[Add more themes as needed. Typical: 2-4 for Standard, 3-6 for Medium/High.]

---

### What Remains Uncertain

[Bulleted list of specific open questions the research could not resolve. Drawn from agents' "Open Questions" sections plus any gaps identified during synthesis. No speculation — just honest acknowledgment of limits.]

- [Specific unanswered question 1]
- [Specific unanswered question 2]

---

### Sources and Confidence

| Finding | Source types | Confidence |
|---------|-------------|------------|
| [Key claim from report] | [e.g., "2 academic papers, 1 official doc"] | HIGH |
| [Another claim] | [e.g., "1 news article, 1 blog post"] | MEDIUM |

[Include only the most significant claims — not every fact, just the ones that drive the Bottom Line and Key Findings.]

---

### Methodology

- **Classification:** [Simple/Standard/Medium/High]
- **Agents deployed:** [N]
- **Research angles:** [list of agent objectives]
- **Tools used:** [list of search, retrieval, and other tools used]
- **Coverage notes:** [Optional — note if coverage was saturated, if certain angles yielded thin results, or if a second research pass would be valuable]
```

---

## Formatting Principles

**BLUF (Bottom Line Up Front)**: The most important conclusions appear first. A reader who stops after the Bottom Line section should have the key answer.

**Themes, not agents**: Organize Key Findings by topic theme, not by which agent produced the finding. A theme may draw from multiple agents' outputs.

**Narrative over bullets**: Use flowing prose in Key Findings, not bullet lists. Bullets are for the Uncertainty and Methodology sections only.

**Epistemic honesty**: Match language to confidence level:
- HIGH confidence: "X is Y" or "The evidence shows X"
- MEDIUM confidence: "X appears to be Y" or "Available evidence suggests X"
- LOW confidence: "Limited evidence points to X, though this remains uncertain"

**Bold sparingly**: 1-3 critical facts per section. Over-bolding dilutes emphasis.

## Good vs. Bad Synthesis

**Bad — mechanical concatenation:**
> Agent 1 found that React Server Components reduce bundle size. Agent 2 found that Astro Islands use partial hydration. Agent 3 found that htmx uses HTML attributes for interactivity.

**Good — connected reasoning:**
> All three frameworks attack the same problem — excessive client-side JavaScript — but from fundamentally different angles. **React Server Components move rendering to the server** while preserving React's component model, making them the natural choice for existing React codebases. Astro and htmx both challenge the SPA assumption itself: Astro through selective hydration of otherwise static pages, htmx by replacing JSON API calls with HTML fragment exchanges. The tradeoff is ecosystem maturity vs. architectural simplicity — RSC inherits React's tooling but also its complexity, while htmx's 14KB footprint comes with a much thinner ecosystem.

The orchestrator's job is to produce the second kind — reasoning that connects findings into insight.
