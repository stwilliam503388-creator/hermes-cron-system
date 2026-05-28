#!/usr/bin/env bash
# Toggle Hermes proxy mode: ON / OFF
#   bash proxy-toggle.sh on   → Route via Headroom (compression)
#   bash proxy-toggle.sh off  → Direct to DeepSeek (no compression)
#   bash proxy-toggle.sh      → Show current state

CONFIG=/Users/liuwei/.hermes/profiles/minimal/config.yaml

current=$(grep 'base_url:' "$CONFIG" | sed 's/.*: //')

case "${1:-status}" in
  on)
    if echo "$current" | grep -q 'localhost'; then
      echo "Already ON ($current)"
    else
      sed -i '' 's|base_url: https://api.deepseek.com/v1|base_url: http://localhost:8787/v1|' "$CONFIG"
      echo "→ Proxy ON  (traffic via localhost:8787)"
      # check proxy is alive
      if curl -sf http://127.0.0.1:8787/readyz >/dev/null 2>&1; then
        echo "  ✓ Proxy responding on :8787"
      else
        echo "  ⚠ Proxy not running — start with: launchctl load ~/Library/LaunchAgents/com.nousresearch.headroom-proxy.plist"
      fi
    fi
    ;;
  off)
    if echo "$current" | grep -q 'api.deepseek'; then
      echo "Already OFF ($current)"
    else
      sed -i '' 's|base_url: http://localhost:8787/v1|base_url: https://api.deepseek.com/v1|' "$CONFIG"
      echo "→ Proxy OFF (direct to api.deepseek.com)"
    fi
    ;;
  status)
    if echo "$current" | grep -q 'localhost'; then
      echo "Proxy: ON  → $current"
    else
      echo "Proxy: OFF → $current"
    fi
    ;;
esac
