#!/bin/bash
# ensure-clashx-us-node.sh — 确保 ClashX 当前节点在美国或日本（用于 NotebookLM 访问）
#
# 工作原理：
#   读取 ClashX plist → 检查 SavedProxyModels.selected → 若不在 US/JP
#   则从订阅文件中找到第一个 🇺🇸 节点 → 写入 plist → 重启 ClashX
#
# 依赖: plutil (macOS 内置)、python3

set -uo pipefail

PLIST="$HOME/Library/Preferences/com.west2online.ClashX.plist"
SUBSCRIPTION_FILE="$HOME/.config/clash/www.vip16888.yaml"

# 1. 读取当前节点
current_raw=$(plutil -extract "SavedProxyModels" raw "$PLIST" 2>/dev/null)
if [ -z "$current_raw" ]; then
    echo "[!] 无法读取 ClashX plist SavedProxyModels"
    exit 1
fi

current_decoded=$(echo "$current_raw" | base64 -d 2>/dev/null)
current_selected=$(echo "$current_decoded" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d[0].get('selected', ''))
except Exception:
    pass
" 2>/dev/null)

echo "当前节点: $current_selected"

# 2. 检查是否已在 US/JP
case "$current_selected" in
    *🇺🇸*|*🇯🇵*)
        echo "✓ 已在 US/JP 节点，无需切换"
        exit 0
        ;;
esac

echo "→ 当前节点非 US/JP，需要切换..."

# 3. 从订阅文件中找到第一个 🇺🇸 节点
if [ ! -f "$SUBSCRIPTION_FILE" ]; then
    echo "[!] 订阅文件不存在: $SUBSCRIPTION_FILE"
    exit 1
fi

us_node=$(grep -E 'name:.*🇺🇸' "$SUBSCRIPTION_FILE" | head -1 | sed 's/.*name: "\(.*\)"/\1/' | tr -d '\r')
if [ -z "$us_node" ]; then
    echo "[!] 未找到 🇺🇸 节点"
    exit 1
fi

echo "目标节点: $us_node"

# 4. 写入 plist — 通过临时 Python 脚本确保正确处理编码
python3 << PYEOF
import sys, json, plistlib

plist_path = "$PLIST"
us_node = "$us_node"

# 读取当前 plist
with open(plist_path, 'rb') as f:
    p = plistlib.load(f)

# 解码 SavedProxyModels（NSData = bytes → JSON string）
raw_bytes = p['SavedProxyModels']
if isinstance(raw_bytes, bytes):
    raw_str = raw_bytes.decode('utf-8')
else:
    raw_str = str(raw_bytes)

data = json.loads(raw_str)
data[0]['selected'] = us_node

# 写回
new_bytes = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
p['SavedProxyModels'] = new_bytes

with open(plist_path, 'wb') as f:
    plistlib.dump(p, f)

print('✓ plist 已更新')
PYEOF

# 5. 重启 ClashX
echo "→ 重启 ClashX..."
killall ClashX 2>/dev/null || true
sleep 1
open -a ClashX
echo "✓ ClashX 已重启，等待代理就绪..."
sleep 3
echo "✓ 完成 — 节点已切换至：$us_node"
