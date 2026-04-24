#!/usr/bin/env bash
# Wrapper: sync pending changes, pull latest, then launch basic-memory MCP server.
# Used as the MCP command in mcps.json for all agents.
export PATH="$HOME/.local/bin:$PATH"
WIKI_DIR="${BASIC_MEMORY_HOME:-$HOME/basic-memory}"
if [ -d "$WIKI_DIR/.git" ]; then
    (
        cd "$WIKI_DIR"
        git push >/dev/null 2>&1 || true
        git pull --rebase --autostash >/dev/null 2>&1 || git rebase --abort >/dev/null 2>&1
    ) &
fi
exec basic-memory mcp "$@"
