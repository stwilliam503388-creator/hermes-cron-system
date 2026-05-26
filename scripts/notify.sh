#!/bin/bash
# notify.sh — 统一推送层（方案B核心）
# 三通道：飞书 → 邮件 → 本地日志（逐级降级）
#
# 用法:
#   echo "内容" | notify.sh <title>                          # stdin
#   notify.sh <title> -m "直接消息"                           # 参数传
#   notify.sh <title> --file /path/to/content.md              # 文件传
#
# 退出码:
#   0 = 至少一个通道送达
#   1 = 全通道不可用

set -euo pipefail

# === 配置 ===
LOG_DIR="${HOME}/.hermes/logs/notify"
FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/a25f8d98-43dc-455b-88df-63446957064e"
EMAIL_TIMEOUT=30  # SMTP 超时（秒）

# === 解析参数 ===
TITLE="${1:-未命名通知}"
shift 2>/dev/null || true

CONTENT=""
if [ "${1:-}" = "-m" ] && [ -n "${2:-}" ]; then
    CONTENT="$2"
elif [ "${1:-}" = "--file" ] && [ -n "${2:-}" ]; then
    CONTENT="$(cat "$2" 2>/dev/null || echo "")"
else
    CONTENT="$(cat)"
fi

if [ -z "$CONTENT" ] || [ -z "$(echo "$CONTENT" | tr -d '[:space:]')" ]; then
    echo "notify.sh: 无内容可推送，跳过" >&2
    exit 0
fi

# === 确保日志目录存在 ===
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/$(date '+%Y-%m-%d').log"

# === 时间戳 ===
TS="$(date '+%Y-%m-%d %H:%M:%S')"

# === 写入本地日志（兜底通道） ===
log_entry() {
    local header="$1"
    local status="$2"
    {
        echo "=============================="
        echo "[$TS] $header"
        echo "状态: $status"
        echo "---"
        echo "$CONTENT"
        echo ""
    } >> "$LOG_FILE"
}

# === 通道1: 飞书 webhook ===
feishu_ok=false
FEISHU_RESP="$(echo "$CONTENT" | python3 -c "
import sys, json
content = sys.stdin.read().strip()
# 飞书消息有长度限制：text < 5000 chars，post/full_card更贵，用 text 模式
truncated = content[:4000] + ('...' if len(content) > 4000 else '')
payload = json.dumps({
    'msg_type': 'text',
    'content': {'text': f'[$TS] $TITLE\n\n{truncated}'}
})
print(payload)
" 2>/dev/null)"

if [ -n "$FEISHU_RESP" ]; then
    HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
        -X POST "$FEISHU_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$FEISHU_RESP" \
        --max-time 10 2>/dev/null || echo "000")"
    if [ "$HTTP_CODE" = "200" ]; then
        feishu_ok=true
    fi
fi

# === 通道2: 邮件（飞书失败时降级） ===
email_ok=false
if [ "$feishu_ok" = false ]; then
    if echo "$CONTENT" | python3 "/Users/liuwei/.hermes/scripts/email-broadcast.py" "$TITLE" 2>/dev/null; then
        email_ok=true
    fi
fi

# === 通道3: 投递队列（邮件也失败时降级，延迟批量投递） ===
queue_ok=false
if [ "$feishu_ok" = false ] && [ "$email_ok" = false ]; then
    QUEUE_DIR="/Users/liuwei/.hermes/delivery-queue/pending"
    mkdir -p "$QUEUE_DIR"
    if echo "$CONTENT" > "$QUEUE_DIR/$(date +%Y%m%d-%H%M)-notify-fallback.txt" 2>/dev/null; then
        queue_ok=true
    fi
fi

# === 日志写入 ===
if [ "$feishu_ok" = true ]; then
    log_entry "推送: $TITLE" "✅ 飞书"
elif [ "$email_ok" = true ]; then
    log_entry "推送: $TITLE" "⚠️ 飞书失败→邮件（降级）"
elif [ "$queue_ok" = true ]; then
    log_entry "推送: $TITLE" "⚠️ 飞书+邮件均失败→投递队列（延迟批量投递）"
else
    log_entry "推送: $TITLE" "❌ 飞书+邮件+投递队列均失败→仅本地日志"
fi

# === 退出码 ===
if [ "$feishu_ok" = true ] || [ "$email_ok" = true ] || [ "$queue_ok" = true ]; then
    exit 0
else
    exit 1
fi
