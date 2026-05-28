#!/usr/bin/env bash
# Switch Hermes to use Headroom proxy (compress all traffic)
# Usage: bash proxy-on.sh

CONFIG=/Users/liuwei/.hermes/profiles/minimal/config.yaml

# Check proxy is running
if ! curl -sf http://127.0.0.1:8787/readyz >/dev/null 2>&1; then
  echo "WARNING: Headroom proxy is not responding on port 8787"
  echo "Start it with: launchctl load ~/Library/LaunchAgents/com.nousresearch.headroom-proxy.plist"
  echo "Force-apply anyway? (y/N)"
  read -r ans
  [[ "$ans" != "y" ]] && exit 1
fi

sed -i '' 's|base_url: http://localhost:8787/v1|base_url: https://api.deepseek.com/v1|' "$CONFIG"
sed -i '' 's|base_url: https://api.deepseek.com/v1|base_url: http://localhost:8787/v1|' "$CONFIG"
grep base_url "$CONFIG"
echo "Proxy: ON"
