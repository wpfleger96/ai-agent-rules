# AI Rules

Manage AI agent configurations through symlinks. Keep all your configs in one git-tracked location.

[![PyPI Downloads](https://img.shields.io/pypi/dm/ai-agent-rules.svg)](https://pypi.org/project/ai-agent-rules/)
[![PyPI version](https://img.shields.io/pypi/v/ai-agent-rules.svg)](https://pypi.org/project/ai-agent-rules/)
[![Python Versions](https://img.shields.io/pypi/pyversions/ai-agent-rules.svg)](https://pypi.org/project/ai-agent-rules/)
[![CI](https://github.com/wpfleger96/ai-agent-rules/actions/workflows/ci.yml/badge.svg)](https://github.com/wpfleger96/ai-agent-rules/actions/workflows/ci.yml)
[![GitHub Contributors](https://img.shields.io/github/contributors/wpfleger96/ai-agent-rules.svg)](https://github.com/wpfleger96/ai-agent-rules/graphs/contributors)
[![Lines of Code](https://aschey.tech/tokei/github/wpfleger96/ai-agent-rules?category=code)](https://github.com/wpfleger96/ai-agent-rules)
[![License](https://img.shields.io/github/license/wpfleger96/ai-agent-rules.svg)](https://github.com/wpfleger96/ai-agent-rules/blob/main/LICENSE)

## Overview

Consolidates config files for AI coding agents (Claude Code, Goose, Gemini CLI, Codex CLI, Amp) into a single source of truth via symlinks:

- Git-tracked configs synced across machines
- Edit once, apply everywhere
- Declarative plugin management (Claude Code)
- Exclude specific files (e.g., company-managed)
- Per-agent customizations

**Supported:** Claude Code, Goose, Gemini CLI, Codex CLI, Amp — plus Shared (AGENTS.md, skills)

| Agent | Config dir | Skills dir |
|-------|-----------|------------|
| Amp | `~/.config/amp/` | `~/.config/agents/skills/` |
| Claude Code | `~/.claude/` | `~/.claude/skills/` |
| Codex CLI | `~/.codex/` | `~/.agents/skills/` |
| Gemini CLI | `~/.gemini/` | (via `~/.agents/skills/`) |
| Goose | `~/.config/goose/` | `~/.config/goose/skills/` |

## Installation

**Requirements:** Python 3.10+, [uv](https://github.com/astral-sh/uv)

### From PyPI (Recommended)

One-command setup from PyPI:

```bash
uvx --from ai-agent-rules ai-agent-rules setup
```

This will:
1. Install AI agent configuration symlinks
2. Make `ai-agent-rules` (and the `ai-rules` alias) available system-wide
3. Auto-install optional tools (claude-code-statusline)

After setup, you can run `ai-agent-rules` (or `ai-rules` for short) from any directory.

### From GitHub (Development)

Install from GitHub to get the latest development code:

```bash
uvx --from ai-agent-rules ai-agent-rules setup --github
```

This installs from the main branch and auto-detects the GitHub source for future updates.

### Local Development

For contributing or local development:

```bash
git clone https://github.com/wpfleger96/ai-agent-rules.git
cd ai-agent-rules
uv run ai-agent-rules install
```

Use `uv run ai-agent-rules <command>` to test local changes. The global `ai-agent-rules` command continues to run your installed version (PyPI/GitHub).

### Updating

Check for and install updates:

```bash
ai-agent-rules upgrade              # Check and install updates (shows changelogs)
ai-agent-rules upgrade --check      # Only check for updates
ai-agent-rules upgrade --force      # Force reinstall even if up to date
ai-agent-rules upgrade --skip-install  # Skip running install --rebuild-cache after upgrade
ai-agent-rules upgrade --only statusline  # Upgrade only a specific tool (ai-agent-rules | statusline)
```

## Usage

Generate the full CLI reference with `just docs`.

### Setup and Upgrade

```bash
ai-agent-rules setup                      # One-time setup: install symlinks + make available system-wide
ai-agent-rules setup --github             # Install from GitHub (pre-release)
ai-agent-rules setup --profile work       # Setup with a specific profile
ai-agent-rules setup --skip-symlinks      # Skip symlink installation
ai-agent-rules setup --skip-completions   # Skip shell completion installation
ai-agent-rules upgrade                    # Upgrade to latest version
ai-agent-rules upgrade --check            # Check for updates without installing
```

### Install and Sync

```bash
ai-agent-rules install                    # Install all agent configs + optional tools
ai-agent-rules install --agents claude    # Install specific agent(s): amp, claude, codex, gemini, goose, shared
ai-agent-rules install --dry-run          # Preview changes
ai-agent-rules install -y                 # Auto-confirm without prompting
ai-agent-rules install --rebuild-cache    # Rebuild merged settings cache
ai-agent-rules install --profile work     # Install with a specific profile
```

### Status and Inspection

```bash
ai-agent-rules status                     # Check symlink status + optional tools + active profile (✓✗⚠○), shows diffs
ai-agent-rules diff                       # Show config differences
ai-agent-rules validate                   # Verify source files exist
ai-agent-rules list-agents                # Show available agents
ai-agent-rules uninstall                  # Remove all symlinks
```

### Configuration

```bash
ai-agent-rules config init                # Interactive wizard for first-time setup
ai-agent-rules config show                # Show raw config files
ai-agent-rules config show --merged       # Show merged settings with overrides applied
ai-agent-rules config show --agent claude # Show config for a specific agent
ai-agent-rules config edit                # Edit user config in $EDITOR
```

### Exclusions and Overrides

```bash
ai-agent-rules exclude add "~/.claude/*.json"      # Add exclusion pattern (supports globs)
ai-agent-rules exclude remove "~/.claude/*.json"   # Remove exclusion pattern
ai-agent-rules exclude list                        # List all exclusions

ai-agent-rules override set claude.model "claude-sonnet-4-6"        # Set override
ai-agent-rules override set claude.hooks.SubagentStop[0].hooks[0].command "script.py"  # Array notation
ai-agent-rules override unset claude.model                          # Remove override
ai-agent-rules override list                                        # List all overrides
```

### Skills

```bash
ai-agent-rules skill list                 # List all bundled skills
ai-agent-rules skill show research        # Render skill content in terminal
ai-agent-rules skill show research --url  # Print versioned GitHub URL for sharing
ai-agent-rules skill show research --raw  # Print raw markdown (for piping)
```

### Tools

```bash
ai-agent-rules tool list                              # Show managed tools with version and update info
ai-agent-rules tool show statusline                   # Detailed info for a specific tool
ai-agent-rules tool source list                       # List install source preferences
ai-agent-rules tool source get statusline             # Show source preference for a tool
ai-agent-rules tool source set statusline github      # Set install source (pypi, github, local:<path>, reset)
```

### Shell Completions

```bash
ai-agent-rules completions install [--shell bash|zsh]   # Install shell completions
ai-agent-rules completions uninstall [--shell bash|zsh] # Remove completions
ai-agent-rules completions update [--shell bash|zsh]    # Update completion script
ai-agent-rules completions status                       # Check if installed
ai-agent-rules completions bash                         # Print raw bash completion script
ai-agent-rules completions zsh                          # Print raw zsh completion script
```

## Configuration

### User-Level Config

Create `~/.ai-agent-rules-config.yaml` for user-level settings:

```yaml
version: 1

# Supports glob patterns: *.json, **/*.yaml, etc.
exclude_symlinks:
  - "~/.config/goose/config.yaml"
  - "~/.claude/*.log"
  - "~/.claude/agents/debug-*.md"

# Machine-specific settings overrides
settings_overrides:
  claude:
    model: "claude-sonnet-4-6"
  goose:
    provider: "anthropic"
```

**Config file locations:**
- `~/.ai-agent-rules-config.yaml` — User-specific config (exclusions and overrides)
- `~/.ai-agent-rules/state.yaml` — Active profile and last install timestamp (auto-managed)
- `~/.ai-agent-rules/cache/` — Merged settings cache (auto-generated)

### Settings Overrides

Use `settings_overrides` to keep `settings.json` synced via git while allowing machine-specific values:

```yaml
# ~/.ai-agent-rules-config.yaml on personal laptop
settings_overrides:
  claude:
    model: "claude-sonnet-4-6"

# ~/.ai-agent-rules-config.yaml on work laptop
settings_overrides:
  claude:
    model: "claude-opus-4-6"
```

Merge pipeline at install time:
1. **Base settings** from `src/ai_rules/config/claude/settings.json` (git-tracked)
2. **Profile overrides** applied (if a profile is active)
3. **User overrides** from `~/.ai-agent-rules-config.yaml` (local only)
4. **Preserved fields** merged from cache (agent-managed fields)
5. **Cached** in `~/.ai-agent-rules/cache/claude/settings.json`
6. **Symlinked** to `~/.claude/settings.json`

After changing overrides, run `ai-agent-rules install --rebuild-cache`.

#### Preserved Fields

When agents manage their own config fields (e.g., MCP server lists, installed plugins), ai-agent-rules preserves them during installs by merging through a cache file:

| Agent | Preserved fields | Cache path |
|-------|-----------------|------------|
| Claude | `enabledPlugins`, `hooks` | `~/.ai-agent-rules/cache/claude/settings.json` |
| Goose | `extensions` | `~/.ai-agent-rules/cache/goose/config.yaml` |
| Codex | `projects` | `~/.ai-agent-rules/cache/codex/config.toml` |
| Gemini | `ide` | `~/.ai-agent-rules/cache/gemini/settings.json` |

#### Array Notation for Nested Settings

Override commands support array index notation for complex nested structures:

```bash
ai-agent-rules override set claude.hooks.SubagentStop[0].hooks[0].command "uv run ~/my-hook.py"
ai-agent-rules override set claude.env.MY_VAR "value"

# Path validation catches typos with suggestions
ai-agent-rules override set claude.modle "sonnet"
# Error: Key 'modle' not found at 'modle'
# Available options: model, env, hooks, statusLine, ...
```

#### Codex Native Status Line

Codex stores footer configuration in `~/.codex/config.toml` under `[tui].status_line`, so ai-agent-rules manages the native Codex footer directly instead of installing a separate status line tool.

| Claude status line | Codex native item |
|--------------------|-------------------|
| `model` | `model-with-reasoning` |
| `directory` | `current-dir` |
| `git-branch` | `git-branch` |
| `context-percentage` | `context-used` |
| `context-tokens` | `used-tokens` |
| `session-id` | `session-id` |
| `cost` | No native Codex equivalent |
| `lines-changed` | No native Codex equivalent |
| `session-clock` | No native Codex equivalent |

Override per machine with `settings_overrides`:

```yaml
settings_overrides:
  codex:
    tui:
      status_line:
        - model-with-reasoning
        - current-dir
        - git-branch
        - context-used
        - used-tokens
        - session-id
```

`codex.tui.status_line` replaces the entire footer list, so setting a shorter array removes the bundled defaults instead of merging with them.

### MCP Management

MCP servers are defined in `src/ai_rules/config/mcps.json` (shared across agents). Each agent's MCP manager translates the shared definitions into its native config format:

| Agent | Format |
|-------|--------|
| Amp | JSON |
| Claude Code | JSON (`mcpServers` in `settings.json`) |
| Codex CLI | TOML |
| Gemini CLI | JSON |
| Goose | YAML extensions |

Managed MCPs are tracked with a `_managedBy: "ai-agent-rules"` marker so the tool can distinguish its entries from user-added servers. Override MCPs per machine via `mcp_overrides` in your user config or profile:

```yaml
# ~/.ai-agent-rules-config.yaml
mcp_overrides:
  my-server:
    env:
      API_KEY: "local-key"
```

### Profiles

Profiles group configuration overrides into named presets for different machines or contexts.

```bash
ai-agent-rules profile list                    # List available profiles
ai-agent-rules profile show work               # View profile details
ai-agent-rules profile show work --resolved    # Show with inheritance applied
ai-agent-rules profile current                 # Check which profile is active
ai-agent-rules profile switch work             # Switch to a different profile
ai-agent-rules install --profile work          # Install with a specific profile
```

Three built-in profiles with inheritance: `default -> personal -> work`. Profiles support these keys:

```yaml
# profiles/work.yaml
name: work
description: Work laptop with extended context model
extends: personal          # Inherit from personal, then override
settings_overrides:
  claude:
    env:
      ANTHROPIC_DEFAULT_SONNET_MODEL: "claude-sonnet-4-6[1m]"
    model: opus
plugins: []
marketplaces: []
exclude_symlinks: []
mcp_overrides: {}
```

User-defined profiles live at `~/.ai-agent-rules/profiles/<name>.yaml`. Priority order (lowest to highest): profile overrides → local `~/.ai-agent-rules-config.yaml`. Your local config always wins.

The active profile persists in `~/.ai-agent-rules/state.yaml` across sessions.

### Plugin Management

Specify Claude Code plugins declaratively in your profile or user config:

```yaml
# profiles/work.yaml or ~/.ai-agent-rules-config.yaml
plugins:
  - name: feature-dev
    marketplace: claude-plugins-official
  - name: python-expert
    marketplace: cc-marketplace

marketplaces:
  - name: cc-marketplace
    source: ananddtyagi/cc-marketplace
```

When you run `ai-agent-rules install`:
1. Adds missing marketplaces via `claude plugin marketplace add`
2. Installs missing plugins via `claude plugin install <name>@<marketplace>`
3. Auto-uninstalls orphaned plugins that were previously managed by ai-agent-rules but removed from config
4. Warns about manually-installed plugins not in config (doesn't auto-uninstall them)

Plugin state is tracked in `~/.claude/plugins/ai-agent-rules-managed.json` to avoid removing manually-installed plugins.

## Structure

```
src/ai_rules/config/
├── AGENTS.md              # -> ~/AGENTS.md
├── chat_agent_hints.md    # Chat agent custom instructions
├── mcps.json              # Shared MCP server definitions
├── amp/                   # -> ~/.config/amp/
├── claude/                # -> ~/.claude/
├── codex/                 # -> ~/.codex/
├── gemini/                # -> ~/.gemini/
├── goose/                 # -> ~/.config/goose/
├── profiles/              # Built-in profiles (default, personal, work)
├── skills/                # 10 shared skills -> multiple agent skill dirs
│   └── */SKILL.md
└── sprout/                # Multi-agent coordinator prompts
```

## Optional Tools

AI Rules automatically installs optional tools that enhance functionality:

- **claude-code-statusline** — Custom status line for Claude Code showing token usage, git info, time, and workspace details

These tools are installed automatically during `setup` and `install`. Check installation status:

```bash
ai-agent-rules status  # Shows Optional Tools section
ai-agent-rules tool list  # Shows install source, versions, update availability
```

If a tool fails to install, ai-agent-rules continues normally (fail-open behavior).

## Extending

**Add shared skill (Claude Code, Goose, Codex, Amp):**
1. Create `src/ai_rules/config/skills/my-skill/SKILL.md` with frontmatter:
```yaml
---
name: my-skill
description: "Brief description"
metadata:
  trigger-keywords: "keyword1, keyword2"
  trigger-patterns: "pattern1, pattern2"
---
```
2. Run `ai-agent-rules install`
3. Skill symlinked to `~/.claude/skills/`, `~/.config/goose/skills/`, `~/.config/agents/skills/` (Amp), and `~/.agents/skills/` (Codex). Gemini discovers skills from `~/.agents/skills/` via built-in alias — no dedicated dir needed.

**Add Claude hook:**
1. Create `src/ai_rules/config/claude/hooks/my-hook.py`
2. Run `ai-agent-rules install`
3. Configure in settings or overrides (e.g., UserPromptSubmit, SubagentStop)

**Add new AI tool:**
1. Add configs to `src/ai_rules/config/<tool>/`
2. Implement `src/ai_rules/agents/<tool>.py`
3. Register in `src/ai_rules/cli.py::get_targets()`

## Safety

- First-run warnings
- Timestamped backups (`*.ai-agent-rules-backup.YYYYMMDD-HHMMSS`)
- Interactive prompts and dry-run mode
- Only manages symlinks (never deletes real files)
- Contextual error messages with tips

## Troubleshooting

**Wrong target:** `ai-agent-rules status` then `ai-agent-rules install -y`

**Restore backup:**
```bash
ls -la ~/.CLAUDE.md.ai-agent-rules-backup.*
mv ~/.CLAUDE.md.ai-agent-rules-backup.20250104-143022 ~/.CLAUDE.md
```

**Disable symlink:** Use the exclude command or add to config manually:
```bash
ai-agent-rules exclude add "~/.claude/settings.json"
ai-agent-rules config edit
```

**Override not applying:** Rebuild the merged settings cache:
```bash
ai-agent-rules install --rebuild-cache
```

**View merged settings:** Check what's actually being applied:
```bash
ai-agent-rules config show --merged
ai-agent-rules config show --merged --agent claude
```

**Upgrading from pre-v0.35?** Config auto-migrates from `~/.ai-rules-config.yaml` to `~/.ai-agent-rules-config.yaml` and `~/.ai-rules/` to `~/.ai-agent-rules/`.

## License

MIT
