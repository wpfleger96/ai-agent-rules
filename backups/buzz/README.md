# Buzz team backup: Sietch Tabr

`sietch-tabr.team.json` is a Buzz team snapshot export (`buzz-team-snapshot` v1). It holds the Sietch Tabr team's name, description and instructions, plus each member's name, system prompt, runtime, provider, model, session policy and avatar. It was exported with memories off, and it carries no keys, credentials or env vars.

This directory sits outside `src/`, so it is not packaged into the `ai-agent-rules` wheel and `ai-rules install` never deploys it.

Restoring creates a **new** team whose agents have **new** keys. The old identities are not reused, so channel memberships have to be redone.

## What the export drops

Team export has no field for effort, it takes parallelism from each agent's saved definition rather than the running team, and it leaves out env vars. Re-apply these values by hand after a restore:

| Agent | Runtime / provider / model (kept) | Effort (dropped) | Team parallelism (export has 10) |
|-------|-----------------------------------|------------------|----------------------------------|
| Paul | buzz-agent / anthropic / `claude-opus-5-5` | high | 24 |
| Duncan | buzz-agent / anthropic / `claude-opus-5-5` | low | 24 |
| Thufir | buzz-agent / openai / `gpt-6-astra` | unset (default) | 24 |
| Alia | buzz-agent / databricks_v2 / `goose-gpt-5-6-luna` | max | 24 |
| Gurney | buzz-agent / openai / `gpt-6-astra` | unset (default) | 10 |
| Hayt | buzz-agent / anthropic / `claude-opus-5-5` | low | 10 |

Effort is set with the `BUZZ_AGENT_THINKING_EFFORT` env var on the agent. Paul's avatar is exported as an `https://` media URL, not embedded, so it depends on that relay media staying available. The other five avatars are embedded.

## Restore

1. In Buzz, open Agents → Import team.
2. Pick `sietch-tabr.team.json`, review the preview, and confirm.
3. Set each agent's effort (`BUZZ_AGENT_THINKING_EFFORT`) and team parallelism from the table above.
4. Re-add the new agents to their channels.

## Refresh

1. In Buzz, open Agents → Sietch Tabr → Share → Export team.
2. Set Memories to **Team only** and File format to **JSON**.
3. Overwrite `sietch-tabr.team.json` with the export, and update the table if effort or parallelism changed.
