#!/bin/bash
# Wrapper: 执行 run-obsidian-pipeline.sh 并广播输出到邮箱

# 加载统一环境变量
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

output=$(/Users/liuwei/.hermes/scripts/run-obsidian-pipeline.sh ${@:+"$@"} 2>&1) || true
echo "$output"
echo "$output" | /Users/liuwei/.hermes/scripts/notify.sh "Obsidian 每日流水线" 2>&1 || echo "notify.sh 推送失败（非致命）"

# 写入投递队列
QUEUE_DIR="$HOME/.hermes/delivery-queue/pending"
mkdir -p "$QUEUE_DIR"
echo "$output" | head -10 > "$QUEUE_DIR/$(date +%Y%m%d-%H%M)-obsidian-pipeline.txt"
