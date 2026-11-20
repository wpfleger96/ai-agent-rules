## Personal Infrastructure

**Rule:** When debugging config, shell, git, editor, or agent behavior issues, check the relevant source repo before guessing or asking the user.

| Issue area | Source repo | Path | Deployment |
|------------|-------------|------|------------|
| AI agent configs (AGENTS.md, settings, MCP servers, hooks, skills, profiles) | `ai-agent-rules` | `~/Development/ai-agent-rules` | Deployed via uv tool from PyPI; `~/AGENTS.md` symlinks into `~/.ai-agent-rules/cache/`, not the repo — editing the live file does NOT modify the source. Run `ai-agent-rules status` to verify symlinks. CLI: `ai-agent-rules`. |
| Shell/terminal, git global config, editor settings (VS Code, Cursor), SSH signing, AI agent binary installs | `shell-configs` | `~/Development/shell-configs` | Managed section injection — NOT symlinks. Delimited blocks inside config files are overwritten on `shell-configs install`; content outside blocks persists. CLI: `shell-configs`. |
| Claude Code statusline (model, tokens, cost, git branch bar) | `claude-code-status-line` | `~/Development/claude-code-status-line` | Wired into `~/.claude/settings.json`. |
| GitHub repo settings (branch protection, merge rules, labels, Renovate) | `github-config` | `~/Development/github-config` | Declarative YAML manifests applied via `gh-infra`. |
| `gh-infra` fork workflow | `gh-infra` | `~/Development/gh-infra` | Fork of `babarot/gh-infra`. `origin` = `wpfleger96/gh-infra`, `upstream` = `babarot/gh-infra`. See fork workflow section below. |
| `enpass-cli` fork workflow | `enpass-cli` | `~/Development/enpass-cli` | Fork of `hazcod/enpass-cli`. `origin` = `wpfleger96/enpass-cli`, `upstream` = `hazcod/enpass-cli`. See fork workflow section below. |

### Fork Workflows

**Rule:** When making changes to gh-infra or enpass-cli, always follow the fork workflow — never commit directly to `dev`.

- After pushing a fix to a PR branch, also merge it into `dev` so dogfooding picks it up immediately:
  ```
  git checkout dev && git merge wpfleger96/<type>/<slug> --no-ff -m "chore: merge <slug> into dev" && git push origin dev
  ```
- `dev` has dev-only content (its own AGENTS.md with deeper context) that must never go upstream
- For fixes that touch code only on `dev` (not yet in upstream), stack the PR branch on the relevant upstream PR branch — GitHub recomputes diffs dynamically once the base PR merges

| | gh-infra | enpass-cli |
|---|---|---|
| Path | `~/Development/gh-infra` | `~/Development/enpass-cli` |
| Upstream | `babarot/gh-infra` | `hazcod/enpass-cli` |
| PR target | `main` | `master` |
| Build | `go build -o gh-infra ./cmd/gh-infra/` | `make build` |
| Trailers | None (maintainer identity) | Standard rules apply |

## GitHub Path Resolution

**Path resolution:** `github.com/<org>/<repo_name>` → `~/Development/<repo_name>`

## Agent-Authored Commits

**Rule:** Before every commit, run `git config user.name` and compare to "Will Pfleger". Only add trailers when they differ — i.e., the agent has its own git identity. If the user's name is already the committer, omit all trailers.

**When trailers are needed** (agent identity ≠ user identity), include both in the commit message (not PR descriptions):

```
Co-authored-by: Will Pfleger <email>
Signed-off-by: Will Pfleger <email>
```

**Discover email:** Run `git log --format="%aN <%aE>" | grep -i "will pfleger" | head -1` in the repo. Never hardcode.

## Writing as Will

**Rule:** When drafting prose that goes out under the user's name for human readers, use the `writing-as-will` skill.

## Learning Mode

**Build mode is the default.** Learn mode starts when the user says "learn mode" or runs the `learn` skill. It lasts until the user says "build mode", the `learn` skill finishes (unless the user turned learn mode on themselves), or the session ends.

**Always, in both modes:** If the user's message includes their own guess ("I think X; where is Y?"), grade the guess first (right, partial, or wrong, with `file:line` or source evidence), then answer.

**In learn mode, these rules override "Include everything relevant in the first answer" and "Lead with the answer or action" from Response Style:**
- Before answering a question about how something works (how, why, where, what happens if), ask for a one-line guess, as plain text with no answer options. If the user says "skip", answer. Never block a request to do work.
- Then answer, opening with what the guess got right and wrong.
- Tag non-obvious claims EVIDENCED (cite `file:line`, commit, or source) or INFERRED.
- When the user is debugging, ask for their hypothesis before proposing a fix.
- Grade the user's answers on a 0–3 scale: 0 wrong, 1 vague or names only the area, 2 right mechanism, 3 right mechanism and why. Call a vague answer vague; never round up.
- The user writes their own summaries, models, and review questions. Propose candidates and critique; never write or rewrite the user's versions. When saving the user's words, save them exactly as typed.

**Journal:** the private repo `wpfleger96/learning-journal` (local path per GitHub Path Resolution), one file per topic. The `learn` skill reads and writes it.

## Completion Reports: Decisions

**Rule:** In addition to Response Style → Completion reports, add one line for each design choice where an alternative was genuinely considered: "Chose X over Y because Z." Omit it when there was no real alternative.

**Why:** The reasoning behind a change is otherwise lost when the session ends or a subagent's summary drops it. These lines are the answer key when the user later checks their understanding of the change.
