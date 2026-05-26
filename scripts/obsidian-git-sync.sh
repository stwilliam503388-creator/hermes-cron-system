#!/bin/bash
# Obsidian Vault auto git sync — silent when nothing to do
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

# Check if there are any changes
if ! git status --porcelain | grep -q .; then
    # No changes — silent exit (watchdog pattern)
    echo ""
    exit 0
fi

# Changes detected — commit and push
echo "$(date '+%Y-%m-%d %H:%M') — Changes detected"

# Add everything
git add -A >> "$LOG" 2>&1

# Count changes for commit message
CHANGED=$(git diff --cached --stat | tail -1 | awk '{print $1" files changed"}' || echo "changes")

# Commit
git commit -m "auto sync: $(date '+%Y-%m-%d %H:%M') — ${CHANGED}" >> "$LOG" 2>&1
echo "  Committed: ${CHANGED}"

# Pull first to avoid rejected push
git pull --rebase origin main >> "$LOG" 2>&1

# Push
if git push origin main >> "$LOG" 2>&1; then
    echo "  Pushed successfully"
else
    echo "  ERROR: push failed — check $LOG"
    exit 1
fi
