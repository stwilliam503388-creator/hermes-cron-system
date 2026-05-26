#!/bin/bash
# wechat-batch-deliver.sh — 批量汇总投递队列到微信
# 所有 stdout 输出通过 iconv 确保纯 UTF-8，避免 cron 调度器编码解码失败

exec 1> >(iconv -f utf-8 -t utf-8//IGNORE 2>/dev/null)

export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8

HOME="/Users/liuwei"
QUEUE_DIR="$HOME/.hermes/delivery-queue/pending"
SENT_DIR="$HOME/.hermes/delivery-queue/sent"
HERMES="$HOME/.local/bin/hermes"
WECHAT_TARGET="weixin:o9cq80_qR7JsvMCuLrvxGNriW_es@im.wechat"
LOCK_FILE="$HOME/.hermes/delivery-queue/.wechat_lock"
MAX_ITEMS=8
MAX_CHARS_PER_ITEM=500

# 清理超过 30 天的过期文件
find "$QUEUE_DIR" -name "*.txt" -type f -mtime +30 -delete 2>/dev/null
find "$SENT_DIR" -name "*.txt" -type f -mtime +30 -delete 2>/dev/null
mkdir -p "$SENT_DIR"

# 获取锁（防止并发）
if [ -f "$LOCK_FILE" ]; then
    lock_age=$(( $(date +%s) - $(stat -f %m "$LOCK_FILE" 2>/dev/null || echo 0) ))
    if [ "$lock_age" -lt 120 ]; then
        echo "[SKIP] Lock still active (${lock_age}s < 120s)"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
touch "$LOCK_FILE"

# 读取所有待投递文件
shopt -s nullglob
files=( "$QUEUE_DIR"/*.txt )
file_count=${#files[@]}

if [ "$file_count" -eq 0 ]; then
    echo "[QUEUE_EMPTY] No pending items"
    rm -f "$LOCK_FILE"
    exit 0
fi

# 确定批次名称
HOUR=$(date +%H)
if [ "$HOUR" -lt 10 ]; then
    BATCH="[AM] Daily Digest $(date +%m-%d)"
elif [ "$HOUR" -lt 15 ]; then
    BATCH="[Noon] Daily Digest $(date +%m-%d)"
else
    BATCH="[PM] Daily Digest $(date +%m-%d)"
fi

# 构建 digest
digest="$BATCH"
digest+=$'\n'"===================="
digest+=$'\n'

count=0
for f in "${files[@]}"; do
    ((count++))
    [ "$count" -gt "$MAX_ITEMS" ] && break
    content=$(iconv -f utf-8 -t utf-8//IGNORE < "$f" 2>/dev/null)
    if [ ${#content} -gt "$MAX_CHARS_PER_ITEM" ]; then
        content="${content:0:$MAX_CHARS_PER_ITEM}..."
    fi
    digest+=$'\n'"--- Item $count ---"$'\n'
    digest+="$content"$'\n'
done

if [ "$file_count" -gt "$MAX_ITEMS" ]; then
    leftover=$((file_count - MAX_ITEMS))
    digest+=$'\n'"... ($leftmore more items omitted)"
fi

# 发送到微信
echo "[SEND] Delivering $file_count items to WeChat"
if echo "$digest" | "$HERMES" send --to "$WECHAT_TARGET" -s "$BATCH" 2>/dev/null; then
    echo "[OK] Delivered, archiving $file_count items"
    for f in "${files[@]}"; do
        mv "$f" "$SENT_DIR/"
    done
    rm -f "$LOCK_FILE"
    exit 0
fi

echo "[FAIL] Delivery failed, will retry"
rm -f "$LOCK_FILE"
exit 1
