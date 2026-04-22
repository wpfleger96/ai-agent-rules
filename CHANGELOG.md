# CHANGELOG


## v0.37.0 (2026-04-22)

### Features

- Map Claude Code settings to Amp, Codex, Gemini, and Goose
  ([`9ad4a04`](https://github.com/wpfleger96/ai-agent-rules/commit/9ad4a04a5a7b0c937beba075bbcd2dc15ef28d88))

Claude Code has extensive config tuning (reasoning effort, tool permissions, session retention,
  attribution, telemetry). The other agents had minimal configuration. This maps each setting to its
  closest equivalent per upstream schema, validated against cached JSON schemas from the config
  validation framework.

Codex: reasoning effort/summary, history persistence, analytics,

attribution. Gemini: read-only tool allowlist with auto_edit mode, session retention, inline
  thinking. Goose: telemetry disabled. Amp: anthropic effort/thinking, deny permissions for
  destructive

ops, notifications. Work profile: Codex fast mode, Goose config excluded (MDM-managed).

### Testing

- Run schema validation in default suite
  ([`a60f6ed`](https://github.com/wpfleger96/ai-agent-rules/commit/a60f6eddbde96d8ddf8e15f1feb5709c71e940ca))

The schema checks were effectively dormant because the normal test path and CI skipped the live
  validation class. Run them from the default suite so schema drift shows up in the same place as
  the rest of the project's regressions.

Split deterministic schema fetcher coverage from integration-style config compatibility checks so
  the test layout matches the real boundary and Goose validation no longer rides along with the
  remote-fetch marker.


## v0.36.0 (2026-04-21)

### Features

- Standardize on ai-agent-rules as canonical name, fix shell completions PATH shadowing
  ([`e2e1e67`](https://github.com/wpfleger96/ai-agent-rules/commit/e2e1e67bd190c23f99dca1d6110c4fc451160f00))

Shell completions hardcoded `ai-rules` as a bare command name in the eval line written to .zshrc.
  When Hermit installs a different `ai-rules` binary earlier on PATH, it shadows the Python CLI at
  shell startup — every new terminal in a Hermit-managed repo dumps Rust --help text through eval,
  producing a cascade of errors.

Replaced the hardcoded eval with shell-native completion aliasing: generates completions via
  `ai-agent-rules` (unshadowed by Hermit) with a `command -v` guard, then aliases the completion
  function to `ai-rules` via compdef/complete. Both commands get tab completion without hardcoded
  paths.

Broader naming standardization: `ai-agent-rules` is now the canonical name in all user-facing
  strings, tool IDs, config paths, and documentation. `ai-rules` remains as a CLI alias. Centralized
  path accessors (`get_user_config_path`, `get_state_dir`) handle lazy migration from old paths
  (`~/.ai-rules-config.yaml` → `~/.ai-agent-rules-config.yaml`, `~/.ai-rules/` →
  `~/.ai-agent-rules/`). MCP managed-by values use dual-read for backward compatibility. Fixed
  broken `willpfleger` GitHub URLs in pyproject.toml (username was never valid).


## v0.35.0 (2026-04-21)

### Features

- Enable thinking summaries and tighten schema validation
  ([`7c105e4`](https://github.com/wpfleger96/ai-agent-rules/commit/7c105e4ca18ef0d6595dcffb0ac003207ea64d66))

Add `showThinkingSummaries: true` to Claude settings so thinking blocks render as summaries instead
  of being omitted.

Replace the blanket `@pytest.mark.xfail` on the Claude schema test with an explicit allowlist of
  known SchemaStore false positives (`Read(*)`, `Skill(*)`). The test now collects all validation
  errors and only suppresses the specific known instances — any new schema violations surface as
  real failures.

Upstream: https://github.com/SchemaStore/schemastore/issues/5598


## v0.34.0 (2026-04-21)

### Features

- Ban test plan sections from PR descriptions
  ([`a0f9230`](https://github.com/wpfleger96/ai-agent-rules/commit/a0f9230bc7e2f46b7f3f294c582a5de968b33ebb))

Claude Code's system prompt now injects a `## Test plan` template into PR descriptions by default.
  The pr-creator skill already overrides this, but agents creating PRs via `gh pr create` or
  built-in flows bypass the skill. Adding the rule to AGENTS.md (always loaded) closes the gap.


## v0.33.0 (2026-04-21)

### Features

- Add amp as a managed agent
  ([`a5332c1`](https://github.com/wpfleger96/ai-agent-rules/commit/a5332c186236e098720dfdfadcf14a2280f99597))

Amp (ampcode.com) uses AGENTS.md for guidance and JSON settings at ~/.config/amp/settings.json with
  flat amp.*-prefixed keys. Base config maps Claude Code equivalents: thinking enabled, attribution
  disabled, xhigh reasoning effort. MCP servers managed under the amp.mcpServers key. Skills
  directory at ~/.config/agents/skills/ added to shared skills distribution.


## v0.32.0 (2026-04-17)

### Bug Fixes

- Codex exec non-TTY hang, cache activation for preserved_fields
  ([`95bc7cd`](https://github.com/wpfleger96/ai-agent-rules/commit/95bc7cdd8680c147825d851936198a2b37ee11c3))

codex exec hangs in non-TTY contexts (Claude Code's Bash tool) because it waits for stdin that never
  arrives. The ad37829 fix piped prompts via stdin, which worked but caused Codex to echo the full
  prompt to stderr. The OPENAI_API_KEY injection was also unnecessary — ChatGPT OAuth works when the
  configured model supports exec mode.

Fix: close stdin with < /dev/null and instruct Codex to cat the prompt file via its shell tool. Drop
  API key injection and key-file guard.

Separately, the cache system only activated when settings_overrides existed, but agents with
  preserved_fields (codex: projects, claude: hooks/plugins, goose: extensions, gemini: ide) need the
  cache as a write buffer even without overrides — otherwise the symlink points to the git-tracked
  source and the agent dirties the repo. Add Agent.needs_cache property and a force parameter on
  Config cache helpers so all four agents route through the cache unconditionally.

Also make the crossfire skill auto-execute by replacing the persona description with an imperative
  heading.

- Complete preserved_fields cache symmetry across all code paths
  ([`38a44cb`](https://github.com/wpfleger96/ai-agent-rules/commit/38a44cbf7c916f322d010ca959c305673a0d98b6))

The previous commit expanded cache creation to agents with preserved_fields, but three code paths
  still assumed "overrides = cache": cleanup_orphaned_cache deleted caches it shouldn't have, config
  show --merged skipped agents with preserved-field caches, and direct dict access on
  settings_overrides would KeyError for agents that only have preserved_fields.

Make cleanup_orphaned_cache require an explicit agents_needing_cache set (removes the unsafe
  settings_overrides-only fallback), fix config show --merged to detect cache files regardless of
  overrides, and guard dict accesses with .get().

- Remove invalid config keys caught by schema validation tests
  ([`613080a`](https://github.com/wpfleger96/ai-agent-rules/commit/613080a2c070cc37ddc79cea98f324fab17a8d6a))

Codex config.toml had `trust_level` at the top level, but it's a per-project key (nested under
  `projects` in the schema). Removed.

Claude settings.json had `Search(*)` in permissions.allow — `Search` is not a valid tool name, it
  was a no-op. Removed. `Skill(*)` and `Read(*)` are valid patterns kept as-is; the SchemaStore
  community schema's regex incorrectly rejects them (xfail in test).

Also excludes network-dependent schema tests from `just test` default run to prevent external schema
  drift from blocking local development.

### Features

- Add personal profile and three-tier profile hierarchy
  ([`ada6554`](https://github.com/wpfleger96/ai-agent-rules/commit/ada6554f7a4e1c49bcaf47a7d12084aaef74236d))

Establishes default → personal → work inheritance chain. Default stays lean with cc-marketplace as
  the only bundled default. Personal extends default with preferred model (opusplan). Work extends
  personal with extended-context model overrides.

Cleans up personal artifacts that leaked into the base tier: removes unused beads/perles Bash
  permissions, removes plugin-dev plugin from default profile, genericizes personal username and org
  references in AGENTS.md examples. Removes vestigial enabledPlugins from base settings.json, dead
  is_enabled field from ToolSpec, and stale refactoring comment in config.py. Adds empty mcps.json
  so profile mcp_overrides can merge onto a base.

### Testing

- Add config validation and deep-merge regression test suite
  ([`5bc21e3`](https://github.com/wpfleger96/ai-agent-rules/commit/5bc21e365c9c84f41925807bb250f7df282e8a20))

Zero test coverage existed for deep_merge() through real agent config shapes, so profile inheritance
  could silently regress to shallow merge with no test failure. No test validated bundled config
  files are parseable or structurally correct either.

Adds 60 new tests across three layers: deep-merge through all four agents' config shapes (19 tests),
  structural validation of bundled configs and profiles (23 tests), and schema validation against
  provider JSON Schemas with offline-safe TTL cache (12 tests). Also moves test/lint deps (pytest,
  ruff, hatch, etc.) from runtime to dev dependency group where they belong.


## v0.31.5 (2026-04-15)

### Bug Fixes

- Make crossfire Codex invocation work with API key auth and stdin
  ([`ad37829`](https://github.com/wpfleger96/ai-agent-rules/commit/ad37829b4451be69335c56afa623410852ecdb16))

codex exec rejects ChatGPT OAuth for all models — setting OPENAI_API_KEY from ~/.env/openai.key
  switches the auth path. Prompt file instruction was unreliable (codex sometimes ran cat, sometimes
  hung for stdin) — piping via stdin is consistent. cd to REPO_ROOT before launching CLIs so
  Gemini's ImportProcessor doesn't emit ENOENT errors from submodule directories.

- Track profile-contributed hooks and deploy all hook scripts
  ([`3f667eb`](https://github.com/wpfleger96/ai-agent-rules/commit/3f667ebd26931623698cb49ea3fe340533835710))

ManagedFieldsTracker used base_settings (raw repo file) as the source of truth for PRESERVED_FIELDS
  contributions. Hooks added via profile settings_overrides were never tracked, so profile switches
  couldn't clean up stale entries. Now uses the merged settings and tracks on first install too.

Hook script deployment only symlinked .py files matching a regex. Shell scripts (.sh) in the hooks
  directory were silently ignored. Now deploys all files unconditionally -- settings and MCP config
  control which ones are actually invoked.

Also adds is_enabled callback to ToolSpec for profile-conditional tools.

### Refactoring

- Move settings cache logic to Agent, make preserved fields agent-owned
  ([`ae73521`](https://github.com/wpfleger96/ai-agent-rules/commit/ae73521f6445d5ce3a9a226ccce487bcf8998316))

AGENT_CONFIG_METADATA in config.py duplicated data the agent classes already owned
  (config_file_name, config_file_format). Settings cache methods (build_merged_settings,
  is_cache_stale, get_cache_diff) took agent name strings and did internal lookups — but every
  caller already had an agent instance.

Moved cache methods to Agent base class where they read format and preserved_fields from self. Each
  agent subclass now declares which config fields are tool-managed (claude: enabledPlugins/hooks,
  codex: projects, gemini: ide, goose: extensions). Preservation logic lifted from JSON-only to all
  formats — fixes bogus stale-cache diffs for codex config.toml and goose config.yaml.

Deleted AGENT_CONFIG_METADATA and PRESERVED_FIELDS. Added AGENT_FORMATS and FORMAT_CONFIG_FILES for
  the few string-based lookups that remain (validate_override_path, config show). Made config I/O
  helpers public.


## v0.31.4 (2026-04-15)

### Bug Fixes

- Restore codex model config
  ([`cc9aac9`](https://github.com/wpfleger96/ai-agent-rules/commit/cc9aac94111d8ba74c8fe47563f6a2ee033e7319))

### Refactoring

- Extract multi-agent MCPManager from Claude-only implementation
  ([`63fcf4f`](https://github.com/wpfleger96/ai-agent-rules/commit/63fcf4f6b8dff161d45ddc260017e36fe7dbdd1d))

MCPManager was hardcoded to write only to ~/.claude.json. Refactored into an abstract base class
  with four agent-specific subclasses (Claude, Goose, Codex, Gemini), each translating a shared MCP
  definition format to the agent's native config (JSON, YAML, TOML). Agent base class gains
  get_mcp_manager() interface so the CLI can dispatch polymorphically instead of isinstance guards.


## v0.31.3 (2026-04-14)

### Bug Fixes

- Dev-docs PLAN files land in monorepo app dir, not monorepo root
  ([`0b80dc0`](https://github.com/wpfleger96/ai-agent-rules/commit/0b80dc06022a8146d9748a23ad508599fff08d08))

In monorepos the agent's CWD is <monorepo>/<app>/ but PLAN__ files were written to <monorepo>/ —
  invisible when the IDE opens at the app level. Introduces a {project_root} variable that combines
  --git-common-dir (worktree-safe repo root) with --show-toplevel (working tree root) to compute the
  correct target for all four scenarios: standard repo, worktree, monorepo, and worktree+monorepo.


## v0.31.2 (2026-04-14)

### Bug Fixes

- Harden crossfire CLI orchestration for reliability and concurrency
  ([`9a97595`](https://github.com/wpfleger96/ai-agent-rules/commit/9a975959f029ece090d2755c60ca5095dea3d7aa))

Gemini crashed scanning all of /tmp when given --include-directories /tmp, Codex produced
  false-negative "unavailable" results from nvm stderr noise, and neither CLI had timeout
  protection. Fixed by isolating prompt files in unique mktemp -d subdirectories, separating Codex
  stderr, adding timeout 300, and switching from temp-file-based result passing to inline delimited
  output with trap EXIT cleanup.


## v0.31.1 (2026-04-13)

### Bug Fixes

- Gemini can't access files outside its CWD
  ([`3a45cc2`](https://github.com/wpfleger96/ai-agent-rules/commit/3a45cc2b5b6991e58fc15742bf50331fc111f6d0))


## v0.31.0 (2026-04-08)

### Features

- Add Sprout system prompts for multi-agent dev workflow
  ([`b8c78a0`](https://github.com/wpfleger96/ai-agent-rules/commit/b8c78a0d2d0f191a7b62f1a536ab749954d87f3a))

Coordinator prompt teaches claude-lead how to use Sprout MCP tools (threading, @mentioning, polling)
  and when to engage reviewer agents vs respond directly. Reviewer prompt ports the crossfire review
  format (CRITICAL/IMPORTANT/MINOR) for codex/goose agents that don't have Claude's crossfire skill.


## v0.30.1 (2026-04-07)

### Bug Fixes

- Disable adaptive thinking and hardcode max effort
  ([`f35e8f2`](https://github.com/wpfleger96/ai-agent-rules/commit/f35e8f2526596472a938fb1ea8303ffdc3433b9e))

Adaptive thinking has an acknowledged bug where it under-allocates reasoning on turns it misjudges
  as simple, producing zero-reasoning responses that fabricate or take shortcuts — even at
  effort=high. Combined with the medium effort default (Mar 3), this matches the configuration
  identified in anthropics/claude-code#42796 as causing a 70% drop in read:edit ratio and 12x
  increase in user corrections.

Forces fixed thinking budget and max effort via env vars in base settings.json, which all profiles
  inherit via deep merge. Intended as a temporary measure until Anthropic resolves the adaptive
  thinking under-allocation bug.


## v0.30.0 (2026-04-03)

### Features

- Parallelize crossfire CLI launches with Claude's own review
  ([`b46a162`](https://github.com/wpfleger96/ai-agent-rules/commit/b46a16258432592dbb5d91d2bba8d55e2f8af7fb))

Crossfire CLIs (Codex/Gemini) only need the diff to run their review, not Claude's findings.
  Launching them in Phase 5 after Phases 1-4 wasted 1-3 minutes of wall-clock time. Now Phase 0
  fires the CLIs via Bash(run_in_background=true) immediately after diff gathering, and Phase 5 just
  reads the pre-launched results.

Also drops "Primary reviewer findings" from the crossfire prompt -- external models now review
  independently without anchoring bias, matching the standalone crossfire skill's behavior.


## v0.29.0 (2026-04-01)

### Features

- Consolidate crossfire agent into self-contained skills
  ([`ff9d5e7`](https://github.com/wpfleger96/ai-agent-rules/commit/ff9d5e78f75f595de49c5f48dd5bee241f3b6326))

The crossfire system had three components that didn't connect: a skill dispatcher, a code-reviewer
  integration, and a custom agent definition with all the CLI orchestration logic. The agent was
  unreachable in practice — subagents can't spawn other subagents, and neither skill had
  context:fork, so agent:general-purpose was a no-op.

Merged the agent's orchestration (CLI availability checks, temp file handling, parallel codex/gemini
  execution, consensus synthesis) into both skills directly. Added context:fork to code-reviewer so
  it runs isolated and model:opus actually takes effect. Fixed mktemp template that failed on macOS
  BSD (suffix after X pattern) and added gemini API key presence to the availability check.


## v0.28.2 (2026-03-26)

### Bug Fixes

- Plan file handling in git worktrees
  ([`2c6e4cb`](https://github.com/wpfleger96/ai-agent-rules/commit/2c6e4cbdb02effd86f2b50ec1c878eaf6ee89377))


## v0.28.1 (2026-03-25)

### Bug Fixes

- Stupid LLM responses
  ([`e2988c5`](https://github.com/wpfleger96/ai-agent-rules/commit/e2988c5c037c334f9c6db369e3acc0637dbd408a))


## v0.28.0 (2026-03-17)

### Features

- Extract crossfire into generic agent
  ([`e49b332`](https://github.com/wpfleger96/ai-agent-rules/commit/e49b332ee02a82cdb1e271d38e84f08693fbed30))


## v0.27.1 (2026-03-16)

### Bug Fixes

- Ai writing style
  ([`8561198`](https://github.com/wpfleger96/ai-agent-rules/commit/8561198dda703163c92883baf7a0fd0ddef737ba))


## v0.27.0 (2026-03-13)

### Features

- Add Gemini CLI agent management and crossfire code review
  ([`a7e6ca7`](https://github.com/wpfleger96/ai-agent-rules/commit/a7e6ca7b98c03f35738dde24ab2a3338269c6d4e))


## v0.26.0 (2026-03-06)

### Features

- Try out new codex model
  ([`d757b0b`](https://github.com/wpfleger96/ai-agent-rules/commit/d757b0bda05f789e43f5483dacd036a0777779e5))


## v0.25.0 (2026-03-03)

### Features

- **pr-creator**: Add formatting rules for code identifiers, links, and line wrapping
  ([`8b36304`](https://github.com/wpfleger96/ai-agent-rules/commit/8b36304a68e85701bc6aebc08608614ac37a844c))


## v0.24.0 (2026-02-27)

### Features

- Codex CLI support
  ([`6c6e01d`](https://github.com/wpfleger96/ai-agent-rules/commit/6c6e01d1d063c1229ac1494254c69a61efa1a436))


## v0.23.2 (2026-02-27)

### Bug Fixes

- Fuck it
  ([`0168bbc`](https://github.com/wpfleger96/ai-agent-rules/commit/0168bbc5ef745d5f0690c553a2d394e2cb3ccc46))


## v0.23.1 (2026-02-23)

### Bug Fixes

- Prefer local code exploration
  ([`0256efd`](https://github.com/wpfleger96/ai-agent-rules/commit/0256efdcdbbbd6f3c5e0781392c6d9b4f0435ffb))


## v0.23.0 (2026-02-18)

### Features

- Gas up Sonnet
  ([`dfe0fbc`](https://github.com/wpfleger96/ai-agent-rules/commit/dfe0fbc6c7ccf1b94415f55ab765937ae62b5a3b))


## v0.22.5 (2026-02-17)

### Bug Fixes

- Skill permissions
  ([`1d28665`](https://github.com/wpfleger96/ai-agent-rules/commit/1d28665ff2ff94100e922cdea6ca9a721a59f915))

### Chores

- Update AGENTS.md and cleanup dead code
  ([`666139f`](https://github.com/wpfleger96/ai-agent-rules/commit/666139fda2cc56b3956ca43a9abdfcb54ee86d36))

Removed empty performance/benchmark infrastructure (tests/performance/, .benchmarks/ data, 7
  Justfile recipes). Updated AGENTS.md to match current codebase: fixed project structure tree
  (removed nonexistent commands/hooks dirs, added all 9 skills), removed stale Quick Commands.
  Updated README.md to remove references to deleted Justfile targets.


## v0.22.4 (2026-02-14)

### Bug Fixes

- Unhelpful commit messages
  ([`abc1ff7`](https://github.com/wpfleger96/ai-agent-rules/commit/abc1ff7542210629fb5081640676313e80f38dc2))

- Validate command bug
  ([`8eb0684`](https://github.com/wpfleger96/ai-agent-rules/commit/8eb0684a9c7ab1ddc7a793743cc5d399c0e71c2f))


## v0.22.3 (2026-02-14)

### Bug Fixes

- Background update causing bugs
  ([`3f6b3ec`](https://github.com/wpfleger96/ai-agent-rules/commit/3f6b3ecdfc5870e9e12bec86537001d1a3378d39))


## v0.22.2 (2026-02-12)

### Bug Fixes

- Improve dev-docs quality
  ([`6a8fc6f`](https://github.com/wpfleger96/ai-agent-rules/commit/6a8fc6f3d6c79f0091a833686079a725c2f74023))


## v0.22.1 (2026-02-09)

### Bug Fixes

- Cc perm
  ([`66c0c8d`](https://github.com/wpfleger96/ai-agent-rules/commit/66c0c8de39b9a4534845ff840febdaf8bc0b9afb))


## v0.22.0 (2026-02-09)

### Bug Fixes

- Clean up commit messages and PR descriptions
  ([`2e63bae`](https://github.com/wpfleger96/ai-agent-rules/commit/2e63bae1691bdde4e1cf5ee1570ab7592f8281cb))

- Skill model configs
  ([`8485d41`](https://github.com/wpfleger96/ai-agent-rules/commit/8485d41586a429dadf22dfa0bcbaba4de95ab823))

### Features

- Add content diffs to diff/install commands and fix cache staleness
  ([`1ddb125`](https://github.com/wpfleger96/ai-agent-rules/commit/1ddb125cfc0b8f52ba88d16ea90a958493254572))

- Show unified diffs in diff/install/status commands when symlinks are mispointed or regular files
  exist instead of symlinks - Add content-based cache staleness check as fallback after mtime checks
  - Deduplicate cache comparison logic via get_cache_diff - Fix duplicate agent header and broken
  symlink handling edge cases


## v0.21.8 (2026-02-06)

### Bug Fixes

- Nerfed
  ([`4d8f17b`](https://github.com/wpfleger96/ai-agent-rules/commit/4d8f17bd4b338ef04e62de41fbfbc9e80fed0757))


## v0.21.7 (2026-02-05)

### Bug Fixes

- Cc perm
  ([`bdb454a`](https://github.com/wpfleger96/ai-agent-rules/commit/bdb454ae98b2d451bc3002e5b3c356398d46d6bf))


## v0.21.6 (2026-02-05)

### Bug Fixes

- Gas up work profile
  ([`ad93453`](https://github.com/wpfleger96/ai-agent-rules/commit/ad93453a80127ae9baf7a3c50940a661c14209d7))


## v0.21.5 (2026-02-05)

### Bug Fixes

- Opus 4.6 just dropped
  ([`d3868ca`](https://github.com/wpfleger96/ai-agent-rules/commit/d3868caa9db4e6e3dc60cb5452f8f00e519a6e3a))


## v0.21.4 (2026-02-04)

### Bug Fixes

- Cc perms
  ([`9a69359`](https://github.com/wpfleger96/ai-agent-rules/commit/9a693591b7ff56f50d3ca261c5258b14e3533a19))

- Improve top-level AGENTS.md instructions
  ([`e548a5b`](https://github.com/wpfleger96/ai-agent-rules/commit/e548a5b378f965523fb45067069a07f62e2a496b))


## v0.21.3 (2026-02-04)

### Bug Fixes

- Cc perm
  ([`4881d81`](https://github.com/wpfleger96/ai-agent-rules/commit/4881d810dad44f646b6df100e3f7cf37f94e7954))


## v0.21.2 (2026-02-03)

### Bug Fixes

- Cc perm
  ([`fbf64ad`](https://github.com/wpfleger96/ai-agent-rules/commit/fbf64adf814df8406637f4e940504a3ca3b159b6))


## v0.21.1 (2026-01-28)

### Bug Fixes

- Migrate code-reviewer to skill too
  ([`6b35f74`](https://github.com/wpfleger96/ai-agent-rules/commit/6b35f74efaf5793af970e57188531eca9a2a5039))

migrate to skill to align with the rest of the repo, aupport both local and PR review , and enhance
  prompts using content from Google eng best practices blog: 1.
  https://google.github.io/eng-practices/review/reviewer/standard.html 2.
  https://google.github.io/eng-practices/review/reviewer/looking-for.html


## v0.21.0 (2026-01-28)

### Documentation

- Add full automated CLI reference docs
  ([`8f355a0`](https://github.com/wpfleger96/ai-agent-rules/commit/8f355a08e72fc8c626aad48d45910de32e276fc3))

### Features

- Convert and consolidate CC slash commands into skills
  ([`2a99382`](https://github.com/wpfleger96/ai-agent-rules/commit/2a99382e8338954ab2837a1920a14b8a46c23126))

### Refactoring

- Convert and consolidate CC slash commands into skills to align with Anthropic change
  ([`9995fa5`](https://github.com/wpfleger96/ai-agent-rules/commit/9995fa5ff5cecf304a5ba866730a051788e2419f))


## v0.20.10 (2026-01-23)

### Bug Fixes

- Cc perm
  ([`de4759d`](https://github.com/wpfleger96/ai-agent-rules/commit/de4759d517e358a859f1ec2f52ff49bdb8c46160))


## v0.20.9 (2026-01-23)

### Bug Fixes

- Unnecessary output
  ([`765f530`](https://github.com/wpfleger96/ai-agent-rules/commit/765f5307f6ed407253a503eca8d3e827337bb72a))


## v0.20.8 (2026-01-23)

### Bug Fixes

- Standardize wording
  ([`4def6ae`](https://github.com/wpfleger96/ai-agent-rules/commit/4def6ae022165cad20d7b8cd1b73aca7c04e2a53))


## v0.20.7 (2026-01-23)

### Bug Fixes

- Goose config
  ([`9c1717f`](https://github.com/wpfleger96/ai-agent-rules/commit/9c1717fade8d6de2d3537b7c194b429e70be7feb))


## v0.20.6 (2026-01-22)

### Bug Fixes

- Cleanup orphaned hooks
  ([`8ebee1b`](https://github.com/wpfleger96/ai-agent-rules/commit/8ebee1bda9aafffa791c584f980e804399886313))

- Cleanup vestigial post-merge hook code
  ([`064a766`](https://github.com/wpfleger96/ai-agent-rules/commit/064a7661377a5ff3facbdafb2025ee71b757f2a9))


## v0.20.5 (2026-01-22)

### Bug Fixes

- Show unified diffs for all config drift detection types
  ([`98952cf`](https://github.com/wpfleger96/ai-agent-rules/commit/98952cfeb4e75c38ee8af295a283d353b9697490))


## v0.20.4 (2026-01-22)

### Bug Fixes

- Cc perm
  ([`016e409`](https://github.com/wpfleger96/ai-agent-rules/commit/016e4097de5194f9b09220d04213e0e3a5c00662))


## v0.20.3 (2026-01-22)

### Bug Fixes

- Forgot to cleanup a few
  ([`7eca265`](https://github.com/wpfleger96/ai-agent-rules/commit/7eca265e3854e8a7c60cff8a53b663466d5501d5))


## v0.20.2 (2026-01-22)

### Bug Fixes

- Standardize --yes vs --force flags
  ([`a6f55d8`](https://github.com/wpfleger96/ai-agent-rules/commit/a6f55d8a2338838ddf903f305eb3e18bc7b630af))

### Chores

- Docs
  ([`8b10c99`](https://github.com/wpfleger96/ai-agent-rules/commit/8b10c99c3baa0f65e73b8384fbb71c616d66e3e1))


## v0.20.1 (2026-01-21)

### Bug Fixes

- Claude code and goose agents should share skills since it's a common standard
  ([`e492a54`](https://github.com/wpfleger96/ai-agent-rules/commit/e492a54975411f3b0c2155c6be573124e8cbe0a5))

this was the intention in ae91931 but didn't fully get finished

- Don't overwrite hooks manually setup by the user
  ([`072b22c`](https://github.com/wpfleger96/ai-agent-rules/commit/072b22c050e422a305eb828733663b96ee649bf0))

or any other configs either, intelligently merge and note local overrides as unmanaged

- Standardize output
  ([`b16d53e`](https://github.com/wpfleger96/ai-agent-rules/commit/b16d53ee7b1a44ed2e74c0b987c9b6b687022484))


## v0.20.0 (2026-01-21)

### Bug Fixes

- Cc perm
  ([`9747329`](https://github.com/wpfleger96/ai-agent-rules/commit/97473292a4465c0b21fe37d8d47b2eec903c6eeb))

### Features

- Add full skills support for claude code and goose
  ([`ae91931`](https://github.com/wpfleger96/ai-agent-rules/commit/ae91931e18606f7849fefc64d07937999680bb24))

also disabling skill router hook temporarily


## v0.19.9 (2026-01-21)

### Bug Fixes

- Cc perm
  ([`514a67c`](https://github.com/wpfleger96/ai-agent-rules/commit/514a67caa05bcee3ef4eca802142415e4a35e0d5))


## v0.19.8 (2026-01-21)

### Bug Fixes

- Improved skills and added test-writer skill
  ([`d2720f9`](https://github.com/wpfleger96/ai-agent-rules/commit/d2720f9e0f9915c13a5b48d5e1f8a7f8805ef2ea))

- Tweak agents-md slash command prompts
  ([`c9414c1`](https://github.com/wpfleger96/ai-agent-rules/commit/c9414c1134b991935ce622ba306eb8885fa14a4c))


## v0.19.7 (2026-01-20)

### Bug Fixes

- Auto force install during upgrade, don't double prompt user
  ([`eea1d26`](https://github.com/wpfleger96/ai-agent-rules/commit/eea1d2681bcb6f03e28cc6c6f868dd1b42003399))

- Don't run pending update check when already running upgrade command
  ([`e368c9c`](https://github.com/wpfleger96/ai-agent-rules/commit/e368c9cd0737a05d72f920f5f3be50d688b19086))

otherwise this would cause confusing double-prompting

- Show changelog(s) when upgrading
  ([`2b69973`](https://github.com/wpfleger96/ai-agent-rules/commit/2b6997365ae167ee9cd2cbf3b5071a2eefaf066e))

### Chores

- Docs
  ([`6f496f4`](https://github.com/wpfleger96/ai-agent-rules/commit/6f496f49864f8b8de36c0e259d6e30b4bd626a9a))


## v0.19.6 (2026-01-19)

### Bug Fixes

- Cc perm
  ([`3fbef62`](https://github.com/wpfleger96/ai-agent-rules/commit/3fbef62dcbbc7af2cb376a794407895e6a3dce2a))

- Cleanup orphaned plugins that we uninstalled
  ([`104b480`](https://github.com/wpfleger96/ai-agent-rules/commit/104b48036d4d5b377ae003aa45295cd9edd85beb))

- Llms love dumb comments
  ([`32e059d`](https://github.com/wpfleger96/ai-agent-rules/commit/32e059d3e9bd85cff204a560e64ba91f3bd24723))


## v0.19.5 (2026-01-18)

### Bug Fixes

- Cleanup unused tools
  ([`06a1880`](https://github.com/wpfleger96/ai-agent-rules/commit/06a1880bffa819b5814784b286f1609505ed943f))

- Show unified diffs instead of just file path diffs
  ([`2202516`](https://github.com/wpfleger96/ai-agent-rules/commit/2202516e92d4d5af95416c9d82033817cef3f1ee))


## v0.19.4 (2026-01-18)

### Bug Fixes

- Lazyify imports for completion performance
  ([`4df5109`](https://github.com/wpfleger96/ai-agent-rules/commit/4df5109516e7668b619fc6b22627b767704ad89a))


## v0.19.3 (2026-01-18)

### Bug Fixes

- Cc perm
  ([`6441d43`](https://github.com/wpfleger96/ai-agent-rules/commit/6441d439828379a35df928a2dcad3c493d17a3a3))


## v0.19.2 (2026-01-13)

### Bug Fixes

- Dont prompt for reinstall when unmanaged plugins/skills detected
  ([`146da20`](https://github.com/wpfleger96/ai-agent-rules/commit/146da206c92c19f33a85b66fad9e46b485ae4d33))


## v0.19.1 (2026-01-12)

### Bug Fixes

- Cc perm
  ([`21513a6`](https://github.com/wpfleger96/ai-agent-rules/commit/21513a6c40224278bd7a2a3f2033681a5be43a77))


## v0.19.0 (2026-01-09)

### Features

- /prompt-critique slash command
  ([`7c9435d`](https://github.com/wpfleger96/ai-agent-rules/commit/7c9435dfe12888efbdacdf650138f9748225349c))

- /refresh-plan slash command
  ([`64da261`](https://github.com/wpfleger96/ai-agent-rules/commit/64da261fe1b842ae891ff97c87b968e5af7e4f87))


## v0.18.5 (2026-01-09)

### Bug Fixes

- Cc perm
  ([`bbf729b`](https://github.com/wpfleger96/ai-agent-rules/commit/bbf729bf48b379cbc03dde7f1b512e451df2d4d8))


## v0.18.4 (2026-01-09)

### Bug Fixes

- Cc perm
  ([`9ea6eff`](https://github.com/wpfleger96/ai-agent-rules/commit/9ea6eff12e45b6abbabb5e88d70b67a77e679bbf))

### Chores

- Docs
  ([`0d6b540`](https://github.com/wpfleger96/ai-agent-rules/commit/0d6b540817c8b8303f5a1ac71df12f72014630e5))


## v0.18.3 (2026-01-09)

### Bug Fixes

- Auto enable plugins
  ([`f4dafb7`](https://github.com/wpfleger96/ai-agent-rules/commit/f4dafb74cd02464ef96bbeb669d6c790514668b8))


## v0.18.2 (2026-01-09)

### Bug Fixes

- Plugin
  ([`c695c3d`](https://github.com/wpfleger96/ai-agent-rules/commit/c695c3dc0d4334284a2403077de2aee11bae3e93))


## v0.18.1 (2026-01-08)

### Bug Fixes

- Wordy PR descriptions
  ([`1a9fc3a`](https://github.com/wpfleger96/ai-agent-rules/commit/1a9fc3a66bc4a72aaa5b17a2620a15ab69394d1a))


## v0.18.0 (2026-01-08)

### Chores

- Clean up vestigial code
  ([`b86a53f`](https://github.com/wpfleger96/ai-agent-rules/commit/b86a53fa15685224d94491c1f1ccb3cc05fd09c8))

- Docs
  ([`41ff2bb`](https://github.com/wpfleger96/ai-agent-rules/commit/41ff2bba0e5256160fe4e08fbc48e00d39afb8f0))

### Features

- Add claude code plugin support
  ([`2e18fa4`](https://github.com/wpfleger96/ai-agent-rules/commit/2e18fa408f3fabcbcee5f664639017e383c3ac47))


## v0.17.0 (2025-12-20)

### Features

- Migrating cursor settings to shell-configs project
  ([`b95ea16`](https://github.com/wpfleger96/ai-agent-rules/commit/b95ea16e327eba3c4ed2a543d98f7f239f2b3cbb))


## v0.16.1 (2025-12-20)

### Bug Fixes

- Optimize token usage
  ([`bb93497`](https://github.com/wpfleger96/ai-agent-rules/commit/bb93497f41fc32fcad2064fbec0cb97f2aa8fbfb))

### Chores

- Docs
  ([`78ee562`](https://github.com/wpfleger96/ai-agent-rules/commit/78ee56246d8639ed7492b3605126ae6c573f85e8))


## v0.16.0 (2025-12-19)

### Bug Fixes

- /update-docs should auto invoke doc-writer skill, and remove unnecessary update command
  ([`93c8f72`](https://github.com/wpfleger96/ai-agent-rules/commit/93c8f72589f17e08363a76e74ec4f0222493435b))

### Features

- Userpromptsubmit hook to force skill activation, and claude code only autoloads skill frontmatter
  so put activation instructions there
  ([`fa37479`](https://github.com/wpfleger96/ai-agent-rules/commit/fa374794e912dc8e87f5f063e8ffbe61fe413409))


## v0.15.15 (2025-12-18)

### Bug Fixes

- Clarify between user/manual vs. profile overrides
  ([`975694e`](https://github.com/wpfleger96/ai-agent-rules/commit/975694e54e734e6dd68477921f91ff42dbcd2537))


## v0.15.14 (2025-12-18)

### Bug Fixes

- All commands should respect current profile if set
  ([`2a7cdd9`](https://github.com/wpfleger96/ai-agent-rules/commit/2a7cdd90f2ba8fe9c8dda127bd8109caa44d36a6))


## v0.15.13 (2025-12-18)

### Bug Fixes

- Add completions status command
  ([`5fbe247`](https://github.com/wpfleger96/ai-agent-rules/commit/5fbe2472ebd08262767ab9c4fb0162e58a6ef939))


## v0.15.12 (2025-12-18)

### Bug Fixes

- Get prompt-engineer skill to auto trigger
  ([`5490942`](https://github.com/wpfleger96/ai-agent-rules/commit/5490942778813fa8aa59980c628877dda62f0a00))

### Chores

- Cleanup dead code
  ([`b98d4d7`](https://github.com/wpfleger96/ai-agent-rules/commit/b98d4d7f5fad5eb40eb1ebde6ef8518ea8305c58))


## v0.15.11 (2025-12-18)

### Bug Fixes

- Switching profiles should gracefully handle conflicting overrides
  ([`7080a3d`](https://github.com/wpfleger96/ai-agent-rules/commit/7080a3df51608381be23805080765622828a6125))


## v0.15.10 (2025-12-17)

### Bug Fixes

- Remove useless hook
  ([`ad4d540`](https://github.com/wpfleger96/ai-agent-rules/commit/ad4d5403a12ca7f8a5f64041da1c43c513117038))


## v0.15.9 (2025-12-17)

### Bug Fixes

- Intelligent uninstall+reinstall logic
  ([`09274c4`](https://github.com/wpfleger96/ai-agent-rules/commit/09274c43a3856850e6f33908e971cc39a3737101))


## v0.15.8 (2025-12-17)

### Bug Fixes

- Remove local install option expose info command for troubleshooting
  ([`b998e5d`](https://github.com/wpfleger96/ai-agent-rules/commit/b998e5d0d2e638e117f6b06f1950c963f9c7e68f))


## v0.15.7 (2025-12-17)

### Bug Fixes

- Dryrun/force flags and cc perms
  ([`5f0d73e`](https://github.com/wpfleger96/ai-agent-rules/commit/5f0d73e3b680ab5624f00bc19a41890ca7b9894c))

- Setup commmand should also upgrade if already installed
  ([`f381cef`](https://github.com/wpfleger96/ai-agent-rules/commit/f381cef83c2bfeb6aed9006660d44da10b574139))


## v0.15.6 (2025-12-17)

### Bug Fixes

- **upgrade**: Flaky upgrade for GitHub-based installs
  ([`a8ed872`](https://github.com/wpfleger96/ai-agent-rules/commit/a8ed872c20b0a0cae6cd2c17de6b7c45d0b720ac))


## v0.15.5 (2025-12-11)

### Bug Fixes

- Update code comment instructions
  ([`ef78069`](https://github.com/wpfleger96/ai-agent-rules/commit/ef78069ac6f4b2838251737a681deb74acc4019f))

### Chores

- Docs
  ([`9a2dbdc`](https://github.com/wpfleger96/ai-agent-rules/commit/9a2dbdc01e36a8eab3303bb75cc1a3371ca743a1))


## v0.15.4 (2025-12-11)

### Bug Fixes

- Profile should show current and let you switch
  ([`7133c0e`](https://github.com/wpfleger96/ai-agent-rules/commit/7133c0e4e480f4f23c4b0b5ab1de64dceaf13c77))


## v0.15.3 (2025-12-11)

### Bug Fixes

- This burns through pro sub
  ([`828de97`](https://github.com/wpfleger96/ai-agent-rules/commit/828de97921774e45a416fc953c6cb30ced90eda6))

### Chores

- Docs
  ([`859d3b4`](https://github.com/wpfleger96/ai-agent-rules/commit/859d3b4c3c448e591b0fd4a80065616ecc5dfc7a))


## v0.15.2 (2025-12-11)

### Bug Fixes

- Goosehints not getting built in wheel
  ([`c0c4b8b`](https://github.com/wpfleger96/ai-agent-rules/commit/c0c4b8be353b0f66cf38655398e42eeba847435b))


## v0.15.1 (2025-12-11)

### Bug Fixes

- Statusline install should respect install source
  ([`8b0bada`](https://github.com/wpfleger96/ai-agent-rules/commit/8b0bada7a725ddc74ac4aa25b5e4fd45164bc9b2))


## v0.15.0 (2025-12-10)

### Features

- Add github installation support
  ([`a7c00cf`](https://github.com/wpfleger96/ai-agent-rules/commit/a7c00cfb224b78ea089f2ada1ae394bdac514ba1))


## v0.14.0 (2025-12-10)

### Chores

- Update AGENTS.md
  ([`1f3e7fd`](https://github.com/wpfleger96/ai-agent-rules/commit/1f3e7fd7dc33b928f6ff3e03397abb7cf6152e0a))

### Features

- Add profiles feature
  ([`f82159c`](https://github.com/wpfleger96/ai-agent-rules/commit/f82159cb6752fc119a0820c009da8720fbe1879c))


## v0.13.0 (2025-12-10)

### Bug Fixes

- Dont install completions if already installed
  ([`b95e30d`](https://github.com/wpfleger96/ai-agent-rules/commit/b95e30d8a170007d7070e4af2987b6dfaf2b87d2))

- Dont waste tokens, other hints files should @mention the main AGENTS.md
  ([`fab89e7`](https://github.com/wpfleger96/ai-agent-rules/commit/fab89e721a851472d37f0af4cb7519c3c2501b0b))

### Features

- Add supported CursorAgent
  ([`b648e66`](https://github.com/wpfleger96/ai-agent-rules/commit/b648e660730906ca6c3f017fc9ec8dabe05d0d0c))


## v0.12.4 (2025-12-09)

### Bug Fixes

- Cc perm
  ([`f895aa0`](https://github.com/wpfleger96/ai-agent-rules/commit/f895aa0fc6aeb8f9921b9ddcb98dc38b28eede60))


## v0.12.3 (2025-12-08)

### Bug Fixes

- Uvx pip still uses pip config not uv
  ([`1593f0d`](https://github.com/wpfleger96/ai-agent-rules/commit/1593f0d38f1781473a89ddec46d84fefe5ecff4e))


## v0.12.2 (2025-12-08)

### Bug Fixes

- Cc perm
  ([`7ffeb1a`](https://github.com/wpfleger96/ai-agent-rules/commit/7ffeb1a17948a245bc1e2969cfe1307c78f0fc02))

### Chores

- Update AGENTS.md
  ([`86956f0`](https://github.com/wpfleger96/ai-agent-rules/commit/86956f0121d8d2ba9e6d6cfb55e8bee1740c3fd0))


## v0.12.1 (2025-12-08)

### Bug Fixes

- Respect global package index settings
  ([`beb0fd4`](https://github.com/wpfleger96/ai-agent-rules/commit/beb0fd4814007ca8d4df10c327c7a6c2059038a8))


## v0.12.0 (2025-12-08)

### Features

- Agents-md slash command
  ([`9edb6e3`](https://github.com/wpfleger96/ai-agent-rules/commit/9edb6e30feeba26605d0b49921a3018964de397b))


## v0.11.0 (2025-12-08)

### Features

- Doc-writer skill and annotate-changelog slash command
  ([`0faaf4e`](https://github.com/wpfleger96/ai-agent-rules/commit/0faaf4ece829a80fb646b5815b77398e48a45c86))


## v0.10.3 (2025-12-07)

### Bug Fixes

- Cc perms
  ([`9dd366c`](https://github.com/wpfleger96/ai-agent-rules/commit/9dd366cd171480976fd25cc840256bf224453fe3))


## v0.10.2 (2025-12-07)

### Bug Fixes

- Still flaky
  ([`3a6a1ce`](https://github.com/wpfleger96/ai-agent-rules/commit/3a6a1ce4b4b70e49cf0968b42ca78c90c2109ef5))


## v0.10.1 (2025-12-07)

### Bug Fixes

- Flaky update behavior
  ([`f894249`](https://github.com/wpfleger96/ai-agent-rules/commit/f894249cf324fd6dfa86a6d99d6562386f1f9d85))

### Chores

- Update script
  ([`8ae0008`](https://github.com/wpfleger96/ai-agent-rules/commit/8ae00088ee8e4db9f07c7f4f101c214f425c79e1))


## v0.10.0 (2025-12-06)

### Chores

- More code quality
  ([`f639929`](https://github.com/wpfleger96/ai-agent-rules/commit/f639929156d919ea582140e151ee6114002d485a))

### Features

- Opus avaliable on pro now
  ([`c7e9969`](https://github.com/wpfleger96/ai-agent-rules/commit/c7e9969fadc997bfa7fe70d463fcd0deafd92197))


## v0.9.5 (2025-12-05)

### Chores

- Code quality
  ([`9793b0e`](https://github.com/wpfleger96/ai-agent-rules/commit/9793b0e22ab752bdf4deddfe9e2f083aff63d13a))


## v0.9.4 (2025-12-05)

### Bug Fixes

- Show diff during install
  ([`ea63ecc`](https://github.com/wpfleger96/ai-agent-rules/commit/ea63ecc5996a2994325c3cdc6cc741441c4421ec))


## v0.9.3 (2025-12-05)

### Bug Fixes

- Cc perm
  ([`490ad02`](https://github.com/wpfleger96/ai-agent-rules/commit/490ad0204b37f1553852f6dd96aceaf8556ce8c8))

- Llms are dumb
  ([`fd29f5b`](https://github.com/wpfleger96/ai-agent-rules/commit/fd29f5b9e9c62064737853e29da7cb3e4fe63d74))


## v0.9.2 (2025-12-04)

### Bug Fixes

- Update daily and force --version to bypass cache
  ([`f2efa65`](https://github.com/wpfleger96/ai-agent-rules/commit/f2efa653bfea854476c33e947078c1ade9d6e07d))

### Chores

- Add editor config and fix precommit bug
  ([`35693f0`](https://github.com/wpfleger96/ai-agent-rules/commit/35693f0f986bc272ff90875ddf9424ab1c9d820e))


## v0.9.1 (2025-12-04)

### Bug Fixes

- Shell lint cmds
  ([`447463e`](https://github.com/wpfleger96/ai-agent-rules/commit/447463e4da6b35c840e3201ec3c8a3d968e865b3))


## v0.9.0 (2025-12-04)

### Features

- Use shell registry for supported shells
  ([`623e375`](https://github.com/wpfleger96/ai-agent-rules/commit/623e37544b15dd333baca55dc665d13d53fa8325))


## v0.8.1 (2025-12-04)

### Bug Fixes

- Install should install completions
  ([`6cbb669`](https://github.com/wpfleger96/ai-agent-rules/commit/6cbb669a17121a7f9f1de076a9d11e4e254f3d2d))

### Chores

- Migrate repo to use Just
  ([`b139720`](https://github.com/wpfleger96/ai-agent-rules/commit/b139720729344e12ea1877fdfac4e5b74f5305fa))

### Continuous Integration

- Prevent race condition in release workflow
  ([`9ee9827`](https://github.com/wpfleger96/ai-agent-rules/commit/9ee982700ff78230726e715ae896c8c54e11d4e6))


## v0.8.0 (2025-12-04)

### Bug Fixes

- Detect and handle local wheel installations in upgrade command
  ([`41a9797`](https://github.com/wpfleger96/ai-agent-rules/commit/41a97973cd7385c2124e1bffc309e8ec288380ea))

### Features

- Add shell completions support with auto install
  ([`f8c3bd8`](https://github.com/wpfleger96/ai-agent-rules/commit/f8c3bd84a479d89aa4e83accf8d5bb64f856ef61))


## v0.7.0 (2025-12-03)

### Features

- Auto update statusline script
  ([`fbb4688`](https://github.com/wpfleger96/ai-agent-rules/commit/fbb468850ac943ba37e6a1f162e4278632933f8e))


## v0.6.0 (2025-12-03)

### Documentation

- Update README
  ([`a8b1815`](https://github.com/wpfleger96/ai-agent-rules/commit/a8b18150468d16ddd6a22384125d443192db4655))

### Features

- Auto install status line script
  ([`e09d21c`](https://github.com/wpfleger96/ai-agent-rules/commit/e09d21c3740fdcc5a923431444b79c106db2d76c))


## v0.5.4 (2025-12-02)

### Bug Fixes

- Stop caching wrong symlink path when overrides exist
  ([`8611713`](https://github.com/wpfleger96/ai-agent-rules/commit/86117135c0854acc7b370bc3c1d4325595003845))


## v0.5.3 (2025-12-02)

### Bug Fixes

- Performance improvements during symlink install
  ([`4cc1700`](https://github.com/wpfleger96/ai-agent-rules/commit/4cc170055db596cf067a69d4b56d14f829e6f562))


## v0.5.2 (2025-12-02)

### Bug Fixes

- Symlink to tool install dir instead of uvx cache
  ([`9b9a617`](https://github.com/wpfleger96/ai-agent-rules/commit/9b9a61730912c7378178d6db7c5b338a4481f149))

### Continuous Integration

- Fix publish workflow not running
  ([`3e184d6`](https://github.com/wpfleger96/ai-agent-rules/commit/3e184d6c6fde4a1983a3929d2106ef3d0a1107ef))


## v0.5.1 (2025-12-02)

### Bug Fixes

- Test failures in CI and cleanup
  ([`02211d3`](https://github.com/wpfleger96/ai-agent-rules/commit/02211d3c20c52825af0f9aacf2b90e22aa7fed04))

### Chores

- Add AGENTS.md for project
  ([`b871ea8`](https://github.com/wpfleger96/ai-agent-rules/commit/b871ea8f52177c2c92adadeec50c39d364826b66))


## v0.5.0 (2025-12-02)

### Bug Fixes

- Make sure config files get built into wheel package
  ([`3c92f88`](https://github.com/wpfleger96/ai-agent-rules/commit/3c92f88744705168af7a34ee650cd9be519da430))

### Continuous Integration

- Enable ad-hoc runs of publish workflow
  ([`4388662`](https://github.com/wpfleger96/ai-agent-rules/commit/43886624aca953c8bf6f17bbbc368f08269382f9))

- Fix publish workflow bug
  ([`f09ab45`](https://github.com/wpfleger96/ai-agent-rules/commit/f09ab455e7e6f89dc3db2a83028611aedf17482b))

### Features

- Show full diff for stale cache
  ([`cffabd8`](https://github.com/wpfleger96/ai-agent-rules/commit/cffabd827e9adedc875c1f73a2796fc8aa132ae5))


## v0.4.1 (2025-12-02)

### Bug Fixes

- Expose both package names
  ([`dc78525`](https://github.com/wpfleger96/ai-agent-rules/commit/dc78525b2ad019cdeaf4b713fa7ec054bc4ec77d))

### Chores

- Only run publish workflow if we released a new version tag
  ([`5b8488b`](https://github.com/wpfleger96/ai-agent-rules/commit/5b8488b0d37aa38236bcfae466d96c88a1b41dd4))

- Readme badges
  ([`274b949`](https://github.com/wpfleger96/ai-agent-rules/commit/274b949ce9d91a39bc23b861a6aa879be0c2bb3e))


## v0.4.0 (2025-12-02)

### Chores

- Ai spaghetti refactor
  ([`e1c0694`](https://github.com/wpfleger96/ai-agent-rules/commit/e1c0694822c34320c2ad7ee0b9dee4667460eff8))

- Cleanup and another CI test fix
  ([`7acadcf`](https://github.com/wpfleger96/ai-agent-rules/commit/7acadcf9b757f211d1fd306cace79e3932f6f131))

### Features

- Add bootstrap install and auto update processes
  ([`6569767`](https://github.com/wpfleger96/ai-agent-rules/commit/65697676c24c08a2b5da7a0fb6deb6df0b065920))

- Publish to pypi
  ([`14e41f3`](https://github.com/wpfleger96/ai-agent-rules/commit/14e41f3863284d08ddd645c9324ea741fed858d0))


## v0.3.0 (2025-12-01)

### Bug Fixes

- Address critical code review issues
  ([`8b97673`](https://github.com/wpfleger96/ai-agent-rules/commit/8b976730ce1ca41c9e7c3cf5a69594baf457bd6f))

This commit fixes the critical and high-priority issues identified in the code review:

Critical Fixes: - Fix deep merge shallow copy bug - Use copy.deepcopy() instead of base.copy() to
  prevent mutation of base dictionaries (CRITICAL) - Add nested key support to override unset
  command - Now matches override set functionality for consistency

High-Priority Fixes: - Add cache invalidation/staleness detection - Cache is now checked against
  base settings and user config modification times - Optimize cache rebuilding - Cache only built
  during install, not on every get_symlinks() call (status checks are now read-only)

Technical Changes: - Added is_cache_stale() method to check if cache needs rebuilding - Added
  get_settings_file_for_symlink() for read-only symlink enumeration - Modified
  build_merged_settings() to skip rebuild when cache is fresh - Added force_rebuild parameter to
  build_merged_settings() - Cache building moved to install command, before symlink creation - Added
  7 new tests for cache invalidation logic

Test Results: - All 30 tests passing (23 original + 7 new) - Tests cover cache staleness detection,
  force rebuild, and file selection

Performance Impact: - Status/diff commands no longer rebuild cache unnecessarily - Cache
  automatically invalidates when base settings or overrides change - --rebuild-cache flag forces
  cache rebuild when needed

### Chores

- Couple more CC perms
  ([`2af58b4`](https://github.com/wpfleger96/ai-agent-rules/commit/2af58b475f76e0900fce0a35d4911381ace03af9))

- Tweak AGENTS file
  ([`8b02b94`](https://github.com/wpfleger96/ai-agent-rules/commit/8b02b94197dc50cd86cc8b69586bd1f45133a57f))

### Features

- Improve exclusion config UX and add settings merge functionality
  ([`673057a`](https://github.com/wpfleger96/ai-agent-rules/commit/673057a8c5278ed913d698deaf11482f4a447737))

This commit significantly improves the user experience for managing exclusions and adds powerful
  settings override capabilities for machine-specific configurations.

Major Features: - Glob pattern support for exclusions (e.g., ~/.claude/*.json) - Settings overrides
  for machine-specific settings with deep merge - Interactive config wizard (ai-rules config init) -
  New CLI command groups: exclude, override, config - Settings cache management with --rebuild-cache
  flag

CLI Improvements: - ai-rules config init: Interactive wizard for first-time setup - ai-rules config
  show: View raw or merged settings - ai-rules config edit: Edit config in $EDITOR - ai-rules
  exclude add/remove/list: Manage exclusions - ai-rules override set/unset/list: Manage settings
  overrides

Settings Merge System: - Sync base settings.json via git - Override specific keys per machine (e.g.,
  model access) - Deep merge with caching in ~/.ai-rules/cache/ - Supports different settings across
  work/personal laptops

Technical Changes: - Added fnmatch for glob pattern matching in config.py - Implemented deep merge
  algorithm for settings - Added build_merged_settings() for cache management - Enhanced ClaudeAgent
  to use merged settings - Added 16 new tests covering glob patterns and merging

Documentation: - Comprehensive README updates with examples - Updated .ai-rules-config.yaml.example
  with detailed comments - Added troubleshooting section - Documented config precedence and merging
  behavior - Updated CHANGELOG.md

All tests passing (23 tests).

Fixes #[issue-number]


## v0.2.0 (2025-12-01)

### Bug Fixes

- Don't double-prompt the user for confirmation
  ([`54fa5e1`](https://github.com/wpfleger96/ai-agent-rules/commit/54fa5e1399f78188854a3a8703382a5761343fc5))

### Chores

- Update README and readd MIT license
  ([`9bd4e65`](https://github.com/wpfleger96/ai-agent-rules/commit/9bd4e65c4e790e15c5457d33f00db4a2e342ad57))

### Features

- Add SubagentStop hook, project-level rule support, shared AGENTS.md config, and post-merge hook
  ([`263e07c`](https://github.com/wpfleger96/ai-agent-rules/commit/263e07cbf712afad6720c17fe4327818d80fedb1))

- Initial release
  ([`8a9c739`](https://github.com/wpfleger96/ai-agent-rules/commit/8a9c73994c4b84f2754076d555bed68303d715fe))
