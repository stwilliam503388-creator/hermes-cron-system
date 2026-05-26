#!/bin/bash
# Wrapper for cron: run the learning plan push script
# Uses brew python3 (auto-resolved via PATH) as fallback to system python3
set -euo pipefail

PYTHON_BIN=""
for candidate in python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: no python3 found" >&2
    exit 1
fi

export HOME="/Users/liuwei"
"$PYTHON_BIN" /Users/liuwei/.hermes/scripts/learning-plan-push.py
