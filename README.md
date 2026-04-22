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

Consolidates config files for AI coding agents (Claude Code, Goose) into a single source of truth via symlinks:

- Git-tracked configs synced across machines
- Edit once, apply everywhere
- Declarative plugin management (Claude Code)
- Exclude specific files (e.g., company-managed)
- Per-agent customizations

**Supported:** Claude Code (settings, agents, commands, plugins), Goose (hints, config), Shared (AGENTS.md, skills)

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
```

The `upgrade` command automatically displays changelogs for new versions and installs without additional prompts.

## Usage

> **Complete CLI Reference:** See [CLI Reference](docs/CLI_REFERENCE.md) for detailed command documentation.

### User-Level Configuration

```bash
ai-agent-rules setup                      # One-time setup: install symlinks + make available system-wide
ai-agent-rules setup --github             # Install from GitHub (pre-release)
ai-agent-rules setup --profile work       # Setup with a specific profile
ai-agent-rules upgrade                    # Upgrade to latest version
ai-agent-rules upgrade --check            # Check for updates without installing

ai-agent-rules install                    # Install all agent configs + optional tools
ai-agent-rules install --agents claude    # Install specific agents
ai-agent-rules install --dry-run          # Preview changes
ai-agent-rules install -y                 # Auto-confirm without prompting
ai-agent-rules install --rebuild-cache    # Rebuild merged settings cache

ai-agent-rules status                     # Check symlink status + optional tools + active profile (✓✗⚠○), shows diffs
ai-agent-rules diff                       # Show config differences
ai-agent-rules validate                   # Verify source files exist
ai-agent-rules install                    # Re-sync after adding files
ai-agent-rules uninstall                  # Remove all symlinks
ai-agent-rules list-agents                # Show available agents
```

### Configuration Management

```bash
# Interactive wizard for first-time setup
ai-agent-rules config init                # Start configuration wizard

# View configuration
ai-agent-rules config show                # Show raw config files
ai-agent-rules config show --merged       # Show merged settings with overrides
ai-agent-rules config show --agent claude # Show config for specific agent
ai-agent-rules config edit                # Edit user config in $EDITOR

# Manage exclusions
ai-agent-rules exclude add "~/.claude/*.json"      # Add exclusion pattern (supports globs)
ai-agent-rules exclude remove "~/.claude/*.json"   # Remove exclusion pattern
ai-agent-rules exclude list                        # List all exclusions

# Manage settings overrides (for machine-specific settings)
ai-agent-rules override set claude.model "claude-sonnet-4-5-20250929"  # Set simple override
ai-agent-rules override set claude.hooks.SubagentStop[0].hooks[0].command "script.py"  # Array notation
ai-agent-rules override unset claude.model         # Remove override
ai-agent-rules override list                       # List all overrides
```

## Configuration

### Quick Start with Config Wizard

Run the interactive configuration wizard for guided setup:

```bash
ai-agent-rules config init
```

This will walk you through:
1. Selecting common exclusions
2. Adding custom exclusion patterns (with glob support)
3. Setting up machine-specific settings overrides

### User-Level Config

Create `~/.ai-agent-rules-config.yaml` for user-level settings:

```yaml
version: 1

# Global exclusions (apply to all contexts)
# Supports glob patterns: *.json, **/*.yaml, etc.
exclude_symlinks:
  - "~/.config/goose/config.yaml"
  - "~/.claude/*.log"              # Glob: exclude all log files
  - "~/.claude/agents/debug-*.md"  # Glob: exclude debug agents

# Machine-specific settings overrides
# Keeps repo settings.json synced via git, but allows local overrides
settings_overrides:
  claude:
    model: "claude-sonnet-4-5-20250929"  # Override model on personal laptop
    # Other settings inherited from base config/claude/settings.json
  goose:
    provider: "anthropic"
```

**Config File Location:**
- `~/.ai-agent-rules-config.yaml` - User-specific config (exclusions and overrides)
- `~/.ai-agent-rules/state.yaml` - Active profile and last install timestamp (auto-managed)
- `~/.ai-agent-rules/cache/` - Merged settings cache (auto-generated)

### Settings Overrides - Syncing Configs Across Machines

**Problem:** You want to sync your `settings.json` via git, but need different settings on different machines (e.g., different model access on work vs personal laptop).

**Solution:** Use `settings_overrides` in your user config:

```yaml
# ~/.ai-agent-rules-config.yaml on personal laptop
settings_overrides:
  claude:
    model: "claude-sonnet-4-5-20250929"  # No Opus access

# ~/.ai-agent-rules-config.yaml on work laptop
settings_overrides:
  claude:
    model: "claude-opus-4-20250514"  # Has Opus access
```

Both machines sync the same `config/claude/settings.json` via git, but each has different local overrides. The system merges them at install time:

1. **Base settings** from `config/claude/settings.json` (git-tracked)
2. **Merged with** overrides from `~/.ai-agent-rules-config.yaml` (local only)
3. **Cached** in `~/.ai-agent-rules/cache/claude/settings.json`
4. **Symlinked** to `~/.claude/settings.json`

After changing overrides, run:
```bash
ai-agent-rules install --rebuild-cache
```

#### Array Notation for Nested Settings

Override commands support array index notation for complex nested structures:

```bash
# Override nested array elements (e.g., hooks)
ai-agent-rules override set claude.hooks.SubagentStop[0].hooks[0].command "uv run ~/my-hook.py"

# Override environment variables
ai-agent-rules override set claude.env.MY_VAR "value"

# The system validates paths and provides helpful suggestions
ai-agent-rules override set claude.modle "sonnet"
# Error: Key 'modle' not found at 'modle'
# Available options: model, env, hooks, statusLine, ...
```

Path validation ensures you only set valid overrides that exist in the base settings, preventing typos and configuration errors.

### Profiles - Machine-Specific Configuration

Profiles let you group configuration overrides into named presets. Instead of manually maintaining different `~/.ai-agent-rules-config.yaml` files across machines, define profiles once and select them at install time.

```bash
# List available profiles
ai-agent-rules profile list

# View profile details
ai-agent-rules profile show work
ai-agent-rules profile show work --resolved  # Show with inheritance

# Check which profile is active
ai-agent-rules profile current

# Switch to a different profile
ai-agent-rules profile switch work

# Install with a specific profile
ai-agent-rules install --profile work
```

Profiles are stored in `src/ai_rules/config/profiles/` and support inheritance:

```yaml
# profiles/work.yaml
name: work
description: Work laptop with extended context model
extends: null
settings_overrides:
  claude:
    env:
      ANTHROPIC_DEFAULT_SONNET_MODEL: "claude-sonnet-4-5-20250929[1m]"
    model: opusplan
```

Configuration layers (lowest to highest priority):
1. Profile overrides
2. Local `~/.ai-agent-rules-config.yaml` overrides

Your local config always wins, so you can use a profile as a base and tweak specific settings per-machine. Profiles are git-tracked and can be shared across your team.

The active profile is tracked in `~/.ai-agent-rules/state.yaml` and persists across sessions. Use `profile current` to see which profile is active, or `profile switch` to quickly change profiles without re-running the full install.

### Plugin Management - Declarative Claude Code Plugins

Specify Claude Code plugins in your profile or user config, and ai-agent-rules automatically installs them via `claude plugin install`:

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

Check plugin status:
```bash
ai-agent-rules status  # Shows Plugins section with installed/pending/extra
```

Plugins are tracked in `~/.claude/plugins/installed_plugins.json` and synced across machines via your git-tracked profile configuration. ai-agent-rules tracks which plugins it manages in `~/.claude/plugins/ai-agent-rules-managed.json` to avoid removing manually-installed plugins.

## Structure

```
config/
├── AGENTS.md              # User-level rules → ~/AGENTS.md
├── claude/
│   ├── CLAUDE.md          # → ~/.claude/CLAUDE.md
│   ├── settings.json      # → ~/.claude/settings.json
│   └── mcps.json          # → ~/.claude/mcps.json
├── goose/
│   ├── .goosehints        # → ~/.config/goose/.goosehints
│   └── config.yaml        # → ~/.config/goose/config.yaml
└── skills/                # Shared between Claude & Goose (9 skills)
    └── */SKILL.md         # → ~/.claude/skills/* + ~/.config/goose/skills/*
```

## Optional Tools

AI Rules automatically installs optional tools that enhance functionality:

- **claude-code-statusline** - Custom status line for Claude Code showing token usage, git info, time, and workspace details

These tools are installed automatically during `setup` and `install` commands. Check installation status:

```bash
ai-agent-rules status  # Shows Optional Tools section
```

If a tool fails to install, ai-agent-rules continues normally (fail-open behavior).

## Extending

**Add shared skill (Claude Code + Goose):**
1. Create `config/skills/my-skill/SKILL.md` with frontmatter:
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
3. Skill symlinked to both `~/.claude/skills/` and `~/.config/goose/skills/`
4. Auto-suggests when user prompt matches keywords/patterns

**Add Claude hook:**
1. Create `config/claude/hooks/my-hook.py`
2. Run `ai-agent-rules install`
3. Configure in settings or overrides (e.g., UserPromptSubmit, SubagentStop)

**Add new AI tool:**
1. Add configs to `config/<tool>/`
2. Implement `ai_rules/agents/<tool>.py`
3. Register in `ai_rules/cli.py::get_agents()`

## Safety

- First-run warnings
- Timestamped backups (`*.ai-agent-rules-backup.YYYYMMDD-HHMMSS`)
- Interactive prompts and dry-run mode
- Only manages symlinks (never deletes real files)
- Contextual error messages with tips

## Development

### Quick Start with Just

This project uses [just](https://github.com/casey/just) for task automation.

**Install just**:
```bash
# macOS
brew install just

# Linux
cargo install just
# or: sudo apt install just (Ubuntu 23.04+)

# Windows
choco install just
```

**Common commands**:
```bash
just              # Run quick quality checks (sync, type-check, lint-check, format-check)
just --list       # List all available recipes

# Setup
just sync         # Sync dependencies

# Code Quality
just check        # Quick quality checks (no tests)
just check-all    # All checks including tests
just lint         # Fix linting issues
just format       # Auto-format code
just type-check   # Run mypy type checking

# Testing
just test         # Run all tests
just test-unit    # Unit tests only
just test-integration  # Integration tests only
just validate-schemas  # Schema validation tests

# Build
just build        # Build package
just rebuild      # Clean and build
```

### Running Tests
The test suite includes both unit tests and integration tests.

Using just (recommended):
```bash
just test         # Run all tests
just test-unit    # Only unit tests
just test-integration  # Only integration tests
just validate-schemas  # Only schema validation tests
```

Using uv directly:
```bash
uv run pytest [--cov=src --cov-report=term-missing]  # All tests
uv run pytest -m unit      # Unit tests only
uv run pytest -m integration  # Integration tests only
uv run pytest -m schema    # Schema validation tests only
```

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
# Or edit manually: ai-agent-rules config edit
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

## License

MIT
