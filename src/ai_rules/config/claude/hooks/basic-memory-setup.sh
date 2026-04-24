#!/usr/bin/env bash
# Idempotent setup: ensure ~/basic-memory is a git repo with GitHub remote.
# Safe to run on every `ai-rules install` / `ai-rules upgrade`.
# Handles: fresh install, second machine, repo migration, graceful degradation.
set -euo pipefail

WIKI_DIR="${BASIC_MEMORY_HOME:-$HOME/basic-memory}"
REPO_NAME="${BASIC_MEMORY_WIKI_REPO:-basic-memory-wiki}"

resolve_repo() {
    local name="$1"
    case "$name" in
        */*) echo "$name" ;;
        *)
            local user
            user=$(gh api user --jq '.login' 2>/dev/null) || return 1
            [ -n "$user" ] && echo "$user/$name" || return 1
            ;;
    esac
}

check_gh() {
    command -v gh >/dev/null 2>&1 || { echo "⚠ gh CLI not found — skipping GitHub remote setup. Knowledge base works locally."; return 1; }
    gh auth status >/dev/null 2>&1 || { echo "⚠ gh not authenticated — run 'gh auth login' for cross-machine sync."; return 1; }
    return 0
}

mkdir -p "$WIKI_DIR"
for dir in repos projects patterns decisions preferences references references/block people feedback; do
    mkdir -p "$WIKI_DIR/$dir"
    [ -f "$WIKI_DIR/$dir/.gitkeep" ] || touch "$WIKI_DIR/$dir/.gitkeep"
done

if [ ! -d "$WIKI_DIR/.git" ]; then
    cd "$WIKI_DIR"
    git init
    if ! git config --global user.name >/dev/null 2>&1; then
        git config --local user.name "AI Agent"
        git config --local user.email "agent@local"
    fi
    git add -A
    git commit -m "feat: initialize knowledge base" --allow-empty
fi

cd "$WIKI_DIR"

CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")

if [ -z "$CURRENT_REMOTE" ]; then
    check_gh || exit 0
    FULL_REPO=$(resolve_repo "$REPO_NAME") || { echo "⚠ Could not detect GitHub username — skipping remote setup."; exit 0; }

    if gh repo view "$FULL_REPO" >/dev/null 2>&1; then
        git remote add origin "git@github.com:$FULL_REPO.git"
        git fetch origin
        git branch --set-upstream-to=origin/main main 2>/dev/null || true
        git pull --rebase --autostash >/dev/null 2>&1 || git rebase --abort >/dev/null 2>&1
    else
        gh repo create "$FULL_REPO" --private --description "Persistent LLM knowledge base"
        git remote add origin "git@github.com:$FULL_REPO.git"
    fi
    git push -u origin main 2>/dev/null || true

else
    check_gh || exit 0
    FULL_REPO=$(resolve_repo "$REPO_NAME") || exit 0
    EXPECTED_URL="git@github.com:$FULL_REPO.git"

    if [ "$CURRENT_REMOTE" != "$EXPECTED_URL" ]; then
        echo "Migrating knowledge base remote: $CURRENT_REMOTE → $EXPECTED_URL"

        git fetch origin 2>/dev/null || true
        git pull --rebase --autostash >/dev/null 2>&1 || git rebase --abort >/dev/null 2>&1

        if ! gh repo view "$FULL_REPO" >/dev/null 2>&1; then
            gh repo create "$FULL_REPO" --private --description "Persistent LLM knowledge base"
        fi

        git remote set-url origin "$EXPECTED_URL"
        git push -u origin main 2>/dev/null || true

        OLD_REPO=$(echo "$CURRENT_REMOTE" | sed 's|git@github.com:||;s|\.git$||')
        echo "✓ Migrated knowledge base to $FULL_REPO"
        echo "⚠ Old repo '$OLD_REPO' still exists on GitHub. Delete manually if no longer needed."
        exit 0
    fi
fi

echo "✓ Knowledge base ready at $WIKI_DIR"
