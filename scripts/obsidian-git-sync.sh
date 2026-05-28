#!/bin/bash
# Obsidian Vault auto git sync — v2: pull-first to avoid rebase conflicts
# Designed for cron use (no_agent mode): empty stdout = silent, non-empty = delivered

export HOME="/Users/liuwei"
VAULT="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
LOG="/tmp/obsidian-git-sync.log"
MAX_LOG_SIZE=$((500 * 1024))  # 500KB max

cd "$VAULT" || { echo "ERROR: vault dir not found"; exit 1; }

# Rotate log if over size limit
if [ -f "$LOG" ]; then
    log_size=$(stat -f %z "$LOG" 2>/dev/null || echo 0)
    if [ "$log_size" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOG" "$LOG.old" 2>/dev/null
    fi
fi

# ── Step 1: Pull remote first (stash local if needed) ──
NEED_STASH=false
if ! git diff --quiet || ! git diff --cached --quiet; then
    NEED_STASH=true
    git stash push -m "auto-sync stash $(date +%Y%m%d-%H%M)" >> "$LOG" 2>&1
fi

PULL_OK=false
if git pull --rebase origin main >> "$LOG" 2>&1; then
    PULL_OK=true
else
    echo "$(date '+%Y-%m-%d %H:%M') — Pull failed, aborting rebase"
    git rebase --abort 2>/dev/null || true
    if $NEED_STASH; then
        git stash pop >> "$LOG" 2>&1 || true
    fi
fi

# Restore stashed changes if pull succeeded
if $NEED_STASH && $PULL_OK; then
    git stash pop >> "$LOG" 2>&1 || true
fi

# ── Step 2: Check if there are local changes to commit ──
if ! git status --porcelain | grep -q .; then
    # No changes — silent exit (watchdog pattern)
    exit 0
fi

# ── Step 3: Stage and commit ──
echo "$(date '+%Y-%m-%d %H:%M') — Changes detected"

git add -A >> "$LOG" 2>&1

CHANGED=$(git diff --cached --stat | tail -1 | awk '{print $1" files changed"}' || echo "changes")

git commit -m "auto sync: $(date '+%Y-%m-%d %H:%M') — ${CHANGED}" >> "$LOG" 2>&1
echo "  Committed: ${CHANGED}"

# ── Step 4: Push ──
if git push origin main >> "$LOG" 2>&1; then
    echo "  Pushed successfully"
else
    echo "  ERROR: push failed — check $LOG"
    exit 1
fi
