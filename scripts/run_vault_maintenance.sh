#!/bin/bash
# 知识库自动维护流水线 — run_vault_maintenance.sh
# 定时调度：先自动补链 → 再生成健康报告 → 更新所有索引 → 检测过期索引
#
# 新增 (2026-05-21):
#   - vault_news_index_update.py     → 📰资讯索引
#   - vault_conversation_index_update.py → 📅对话归档索引
#   - 过期索引检测（工具笔记索引、Skills文档索引）

set -euo pipefail

# 加载统一环境变量
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

VAULT="${OBSIDIAN_VAULT_PATH:?环境变量 OBSIDIAN_VAULT_PATH 未设置}"
VAULT_SCRIPTS="${HERMES_SCRIPTS:-$HOME/.hermes/scripts}"
NOW=$(date "+%Y-%m-%d %H:%M:%S")

echo "=== [$NOW] 知识库自动维护开始 === VAULT=$VAULT"

# Step 1: 自动补链
echo "[1/5] 自动补链..."
python3 "$VAULT_SCRIPTS/vault_autolink.py" --apply <<< "y" 2>&1

# Step 2: 健康巡检
echo "[2/5] 健康巡检..."
python3 "$VAULT_SCRIPTS/vault_health.py" 2>&1

# Step 3: 更新知识库总索引
echo "[3/5] 更新知识库总索引..."
python3 "$VAULT_SCRIPTS/vault_master_index_update.py" 2>&1

# Step 4: 更新资讯索引
echo "[4/5] 更新资讯索引..."
python3 "$VAULT_SCRIPTS/vault_news_index_update.py" 2>&1

# Step 5a: 更新对话归档索引
echo "[5a/5] 更新对话归档索引..."
python3 "$VAULT_SCRIPTS/vault_conversation_index_update.py" 2>&1

# Step 5b: 检测手工维护的索引是否过期
echo "[5b/5] 检测手工索引过期状态..."
EXPIRED=0

check_index_stale() {
    local file="$1"
    local label="$2"
    if [ ! -f "$file" ]; then
        echo "  ⚠️  $label 文件不存在: $file"
        EXPIRED=$((EXPIRED + 1))
        return
    fi
    local mtime
    mtime=$(stat -f "%m" "$file")
    local now_epoch
    now_epoch=$(date +%s)
    local age_hours=$(( (now_epoch - mtime) / 3600 ))
    if [ "$age_hours" -gt 48 ]; then
        echo "  ⚠️  $label 已 $age_hours 小时未更新（超过48h阈值）"
        EXPIRED=$((EXPIRED + 1))
    elif [ "$age_hours" -gt 24 ]; then
        echo "  ⚠️  $label 已 $age_hours 小时未更新（建议24h内更新）"
    else
        echo "  ✅ $label 在 ${age_hours}h 内更新过"
    fi
}

check_index_stale "$VAULT/工具笔记/🔧工具笔记索引.md" "🔧工具笔记索引"
check_index_stale "$VAULT/工具笔记/skills/🛠Skills文档索引.md" "🛠Skills文档索引"

if [ "$EXPIRED" -gt 0 ]; then
    echo "  ⚠️  发现 $EXPIRED 个过期索引，建议手动更新"
else
    echo "  ✅ 所有手工索引均在有效期内"
fi

echo ""
# Step 6: 生成健康看板报告
echo "[6/6] 生成健康看板报告..."
python3 "$VAULT_SCRIPTS/vault_health_report.py" --vault "$VAULT" 2>&1

# Step 7: 推送通知
echo "[√] 推送..."
echo "知识库维护完成" | "$VAULT_SCRIPTS/notify.sh" "知识库自动维护" 2>&1 || true

echo ""
echo "=== [$NOW] 维护完成 ==="
echo "报告路径: $VAULT/📊 知识库健康报告.md"
echo "索引路径: $VAULT/🏠 知识库总索引.md"
echo "资讯索引: $VAULT/资讯/📰资讯索引.md"
echo "归档索引: $VAULT/对话归档/📅对话归档索引.md"

# 写入投递队列
QUEUE_DIR="$HOME/.hermes/delivery-queue/pending"
mkdir -p "$QUEUE_DIR"
cat > "$QUEUE_DIR/$(date +%Y%m%d-%H%M)-knowledge-maint.txt" <<EOF
📚 知识库维护完成 $NOW
索引: 总索引✅ 资讯✅ 归档✅ 过期检测: $( [ "$EXPIRED" -gt 0 ] && echo "⚠️$EXPIRED个过期" || echo "✅全部正常")
报告: $VAULT/📊 知识库健康报告.md
EOF
