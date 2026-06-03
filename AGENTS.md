# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Identity

| Aspect | Value |
|--------|-------|
| **PyPI package** | `ai-agent-rules` |
| **CLI command** | `ai-agent-rules` (canonical) or `ai-rules` (alias) |
| **Python module** | `ai_rules` |

The name `ai-rules` was taken on PyPI, so the package is published as `ai-agent-rules`. Both CLI entry points work. Use `ai-agent-rules` as the canonical name; `ai-rules` is kept as a convenience alias.

**Supported agents:** Claude Code, Goose, Gemini CLI, Codex CLI, Amp, Shared (AGENTS.md, skills)

## Quick Commands

```bash
just                          # Lint, format, and type check
just test                     # Run tests
just test-unit                # Run unit tests only
just test-integration         # Run integration tests only
just test-e2e                         # Run E2E tests (subprocess, real CLI, all 3 OSes in CI)
uv run ai-agent-rules <cmd>         # Run CLI

# GitHub installation
uv run ai-agent-rules setup --github  # Install from GitHub instead of PyPI

# Key CLI commands
uv run ai-agent-rules install        # Install symlinks
uv run ai-agent-rules status         # Check symlink status (shows diffs)
uv run ai-agent-rules info           # Show installation method and version info
uv run ai-agent-rules upgrade        # Upgrade to latest (shows changelogs)
uv run ai-agent-rules validate       # Validate config files
uv run ai-agent-rules diff           # Show diffs between repo and installed

# Filtering flags (apply to install, status, diff, uninstall)
#   --agents <list>  Comma-separated agent IDs to target (default: all)
#   --only <list>    Comma-separated component types to target (default: all)
#                    Valid values: config, skills, settings, mcps, plugins,
#                    extensions, completions, tools, source-files
#                    Composes with --agents as an intersection

# Subcommands
uv run ai-agent-rules config show    # Show current config
uv run ai-agent-rules config edit    # Edit user config in $EDITOR
uv run ai-agent-rules override list  # List settings overrides
uv run ai-agent-rules completions install  # Install shell completions
uv run ai-agent-rules profile list   # List available profiles
uv run ai-agent-rules profile switch <name>  # Switch to different profile
```

## Tech Stack

- Python 3.10+ with strict type checking (mypy)
- **uv** for dependency management
- **Click** for CLI framework
- **Rich** for console output
- **pytest** with xdist for parallel testing
- **just** for task automation
- **ruff** for linting and formatting

## Project Structure

```
src/ai_rules/
├── cli/                # Click CLI package (commands, groups, components, helpers)
├── config.py           # Config loading, path parsing, merging, preserved fields
├── profiles.py         # Profile loading and inheritance resolution
├── state.py            # State management (active profile tracking)
├── utils.py            # Deep merge and utility functions
├── symlinks.py         # Symlink operations with backups
├── plugins.py          # Claude Code plugin management via marketplace
├── mcp.py              # MCP server management
├── skills.py           # Shared skills management for Claude Code & Goose
├── claude_extensions.py # Claude extensions (agents, commands, hooks) status
├── completions.py      # Shell completion management
├── agents/
│   ├── base.py         # Abstract Agent base class
│   ├── amp.py          # Amp agent (ampcode.com)
│   ├── claude.py       # ClaudeAgent (settings, MCPs, extensions)
│   ├── codex.py        # CodexAgent (config.toml, MCPs)
│   ├── gemini.py       # GeminiAgent (settings, MCPs)
│   ├── goose.py        # GooseAgent (config, hints, MCPs)
│   └── shared.py       # SharedAgent (AGENTS.md, shared skills)
├── bootstrap/          # GitHub install utilities
│   ├── registry.py     # Tool lifecycle registry (DEPRECATED_TOOLS, ACTIVE_TOOLS) — single source of truth
│   ├── installer.py    # Generic install/uninstall (ensure_tool_installed, ensure_tool_uninstalled)
│   ├── updater.py      # Update checking
│   └── version.py      # Version parsing
└── config/             # Source configs (bundled in package)
    ├── AGENTS.md       # Shared behavioral rules
    ├── chat_agent_hints.md  # Chat agent hints
    ├── mcps.json       # Shared MCP server definitions
    ├── amp/            # Amp configs (AGENTS.md, settings.json)
    ├── claude/         # Claude Code configs (CLAUDE.md, settings.json, mcps.json)
    ├── codex/          # Codex configs (config.toml)
    ├── gemini/         # Gemini configs (GEMINI.md, settings.json)
    ├── goose/          # Goose configs (.goosehints, config.yaml)
    ├── skills/         # **SHARED** skills (symlinked to Claude, Goose, Codex, Amp)
    │   ├── agents-md/, code-reviewer/, continue-crash/, crossfire/
    │   ├── dev-docs/, doc-writer/, pr-creator/, prompt-critique/
    │   ├── prompt-engineer/, test-writer/
    ├── profiles/       # Built-in profiles (default.yaml, personal.yaml, work.yaml)
    └── sprout/         # Multi-agent Sprout coordinator prompts
tests/
├── fixtures/           # Test fixture files
├── unit/               # No filesystem side effects
├── integration/        # Modifies files/symlinks
└── e2e/                # Subprocess tests invoking real CLI binary (zero mocking)
```

## Key Patterns

### Agent Abstraction
All AI tools inherit from `Agent` (`agents/base.py`). To add a new tool:
1. Create `agents/<tool>.py` inheriting from `Agent`
2. Implement: `name`, `agent_id`, `get_symlinks()`
3. Register in `targets/registry.py::TARGET_CLASSES`

### Config System
- User config: `~/.ai-agent-rules-config.yaml`
- **State file**: `~/.ai-agent-rules/state.yaml` (tracks active profile, last install time)
- **Profiles**: Named collections of overrides (default, personal, work) with inheritance
  - Built-in: `config/profiles/{default,personal,work}.yaml`
  - User: `~/.ai-agent-rules/profiles/*.yaml`
  - Inheritance via `extends:` key (e.g., work extends default)
  - Commands: `profile list`, `profile show`, `profile current`, `profile switch`
- `settings_overrides` for machine-specific agent settings
- Cache-based override merging for all agents with preserved fields
  - **Critical**: Preserves agent-managed fields during cache rebuild:
    - Claude: `enabledPlugins`, `hooks`
    - Codex: `projects`
    - Gemini: `ide`
    - Goose: `extensions`
- **Plugin management**: Declarative plugin installs from profiles (`plugins`, `marketplaces` keys)
  - Auto-uninstalls orphaned plugins (previously managed by ai-agent-rules, removed from config)
  - Tracks managed plugins in `~/.claude/plugins/ai-agent-rules-managed.json`
  - Warns about manually-installed plugins not in config (doesn't auto-remove)
- Agent-specific hints (CLAUDE.md, .goosehints) use `@~/AGENTS.md` to reference main file (token-saving)

## Testing

```bash
uv run pytest -m unit           # Unit only
uv run pytest -m integration    # Integration only
uv run pytest -m agents         # Agent tests only
uv run pytest -m bootstrap      # Bootstrap tests only
uv run pytest -m completions    # Shell completion tests only
uv run pytest -m config         # Config tests only
uv run pytest -m state          # State management tests only
just test-e2e                   # E2E only — runs real CLI as subprocess, no mocking
                                # E2E isolation: tmp_path, HOME/USERPROFILE/APPDATA/XDG all redirected
                                # Use run_cli / run_cli_with_config fixtures (see tests/e2e/conftest.py)
```

## Code Style

- Run `just` before committing (handles linting, formatting, type checks)
- **pathlib.Path** not string paths
- **rich.console** for CLI output
- **Conventional commits** (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`)

## Common Gotchas

1. **Array path notation** - Setting paths use brackets for arrays: `hooks.SubagentStop[0].command`

2. **Mocking HOME in tests** - Must patch both or tests fail subtly:
   ```python
   monkeypatch.setenv("HOME", str(home))
   monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
   ```

3. **Package index config** - `uvx pip` and `uv tool` use different index configs:
   - `uvx pip` → pip config (PIP_INDEX_URL)
   - `uv tool` → uv config (UV_DEFAULT_INDEX/UV_INDEX_URL)
   - Solution: Pass explicit `--index-url` to pip, `--default-index` to uv

4. **Local development vs installed tool** - **CRITICAL**: Always use `uv run ai-agent-rules` when developing locally:
   - **Local dev (from repo)**: `uv run ai-agent-rules <command>` → runs YOUR local code changes directly
   - **Installed tool (any directory)**: `ai-rules <command>` → runs installed version from `~/.local/share/uv/tools/`
   - Running `ai-rules` without `uv run` will NOT reflect your local changes
   - **NEVER use editable install** (`uv pip install -e .`) - risks conflicts with installed version, unnecessary complexity

5. **Package data dotfiles** - Dotfiles require explicit glob pattern:
   - `pyproject.toml`: `ai_rules = ["config/**/*", "config/**/.*"]`
   - Second pattern needed for `.goosehints` and other dotfiles to be included in wheel

6. **GitHub installs** - `setup --github` installs from HEAD of main branch, not tags:
   - Update checks use GitHub API tags
   - Useful for pre-release features before PyPI publish

7. **Preserved fields in settings.json** - `enabledPlugins`, `hooks` managed by Claude Code or user:
   - ai-agent-rules preserves these fields during cache rebuilds
   - Defined in the `preserved_fields` property of each agent class (e.g., `claude.py`, `codex.py`)
   - Tracking file: `~/.claude/ai-agent-rules-managed-fields.json` (tracks ai-agent-rules contributions)
   - Cleanup: When ai-agent-rules removes a hook from source, it's removed from user settings
   - User hooks preserved (e.g., custom UserPromptSubmit hooks won't be removed)

8. **Upgrade shows changelogs** - `upgrade` command fetches CHANGELOG.md from GitHub:
   - Displays version notes between current and latest
   - Fetches from `https://raw.githubusercontent.com/{repo}/main/CHANGELOG.md`
   - Fails silently on network errors (still proceeds with upgrade)
   - Auto-forces install (no double prompt)

9. **Optional tool registry** — Adding/retiring an optional tool requires ONE registry entry in `bootstrap/registry.py`. Never add per-tool functions:
   ```python
   # ✅ Add to DEPRECATED_TOOLS to retire a tool (cleanup on next install)
   DeprecatedToolSpec(tool_id="foo", package_name="foo-pkg", command_name="foo", is_mcp=False)
   # ✅ Add to ACTIVE_TOOLS to manage a new tool
   ActiveToolSpec(tool_id="bar", command_name="bar-cli", get_install_spec=lambda: BarTool.INSTALL_SPEC)
   # ❌ Do NOT add ensure_foo_installed() / ensure_foo_uninstalled() functions
   ```
   - `DeprecatedToolSpec.is_still_in_use` — True means "skip cleanup" (user still wants it)
   - `ActiveToolSpec.is_configured` — True means "install it" (different semantics!)
   - `ActiveToolSpec.get_install_spec` is a `Callable[[], ToolSpec]` — always call it: `active.get_install_spec()`. Storing the result at module level causes circular imports.
   - `ensure_tool_installed(..., skip_update_check=True)` in `_install_active_tools` — install is a fast presence-check; upgrade checks belong in the `upgrade` command

10. **Gemini skill directory** - Gemini discovers skills from `~/.agents/skills/` (the Codex directory) via a built-in alias:
   - Do NOT add a `~/.gemini/skills/` directory — it causes "Skill conflict detected" warnings in headless invocations
   - This is why `AGENT_SKILLS_DIRS` in `config.py` intentionally excludes Gemini

## Skills

**Skills:** Explore `config/skills/*/SKILL.md` for available skills (10 total: agents-md, code-reviewer, continue-crash, crossfire, dev-docs, doc-writer, pr-creator, prompt-critique, prompt-engineer, test-writer).
- **SHARED across agents** - symlinked to `~/.claude/skills/`, `~/.config/goose/skills/`, `~/.config/agents/skills/` (Amp), `~/.agents/skills/` (Codex)
- Managed by SharedAgent (displays under "Shared:" in status)
- To add a skill: Create subdir in `config/skills/` with `SKILL.md`

## Key Files by Task

| Task | Files |
|------|-------|
| Add CLI command | `cli/commands/` (one module per command) or `cli/groups/` (subcommand groups), then register in `cli/__init__.py::_register_commands` |
| Add/retire optional tool | `bootstrap/registry.py` — one entry in `ACTIVE_TOOLS` or `DEPRECATED_TOOLS` only; no other files needed |
| Add skill | Create subdir in `config/skills/` with `SKILL.md` (shared) |
| Config loading | `config.py` (Config class, load_config) |
| Profile management | `profiles.py`, `state.py`, `cli/groups/profile.py` |
| State management | `state.py` (ProfileState class) |
| Symlink behavior | `symlinks.py` (create_symlink, remove_symlink) |
| Config files component | `cli/components/config.py` (ConfigComponent — install/status/diff for symlinked config files) |
| Settings cache component | `cli/components/settings.py` (SettingsComponent — build/rebuild merged settings cache) |
| Shell completions | `completions.py`, `cli/groups/completions.py` |
| New agent | `agents/base.py`, `agents/<new>.py`, `targets/registry.py::TARGET_CLASSES` |
| Plugin management | `plugins.py`, each `agents/*.py` defines `preserved_fields` |
| MCP management | `mcp.py` (MCPManager base + subclasses: Claude, Goose, Codex, Gemini, Amp) |
| Skills management | `skills.py` (SkillManager), `agents/shared.py` |
| Preserved fields tracking | `config.py` (ManagedFieldsTracker), each `agents/*.py` defines `preserved_fields` |
| Upgrade checking | `bootstrap/updater.py`, `bootstrap/installer.py` |
| GitHub install support | `bootstrap/installer.py` (GITHUB_REPO_URL) |
