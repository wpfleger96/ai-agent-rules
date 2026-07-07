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

---

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

---

## GitHub Path Resolution

**Path resolution:** `github.com/<org>/<repo_name>` → `~/Development/<repo_name>`

---

## Agent-Authored Commits

**Rule:** Before every commit, run `git config user.name` and compare to "Will Pfleger". Only add trailers when they differ — i.e., the agent has its own git identity. If the user's name is already the committer, omit all trailers.

**When trailers are needed** (agent identity ≠ user identity), include both:

```
Co-authored-by: Will Pfleger <email>
Signed-off-by: Will Pfleger <email>
```

**Discover email:** Run `git log --format="%aN <%aE>" | grep -i "will pfleger" | head -1` in the repo. Never hardcode.

**Why:** `Co-authored-by` ensures proper GitHub attribution. `Signed-off-by` satisfies DCO checks requiring human sign-off on agent-authored commits. Applies to commit messages only — not PR descriptions.

---

## Writing Voice

**Rule:** When drafting content posted under the user's name (GitHub comments, PR descriptions/reviews, Slack messages, emails), match the user's natural voice. Does NOT apply to: documentation, code comments, commit messages, or agent responses to the user.

**Casual, first-person, hedged.** "I think," "I opened" — not impersonal voice. Casual greetings ("hey @name"), hedge disagreements with softeners. Narrative flow with natural conjunctions, not bullet lists or bold headers for conversational prose.

**Minimal formatting.** Backticks for code identifiers, skip bold/italic for emphasis. No performative framing ("Thanks for...", "Let me know if you have questions!").
