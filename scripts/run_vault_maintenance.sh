#!/bin/bash
# 知识库自动维护流水线 — run_vault_maintenance.sh v2
# 定时调度：先自动补链 → 再生成健康报告 → 更新所有索引 → 检测过期索引
# v2: 移除 set -e，每步独立容错 + 超时保护

# 加载统一环境变量
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

# 兜底硬编码（cron 环境 setenv.sh 可能未被 source）
export HOME="${HOME:-/Users/liuwei}"
VAULT="${OBSIDIAN_VAULT_PATH:-/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault}"
VAULT_SCRIPTS="${HERMES_SCRIPTS:-$HOME/.hermes/scripts}"
NOW=$(date "+%Y-%m-%d %H:%M:%S")

echo "=== [$NOW] 知识库自动维护开始 === VAULT=$VAULT"

STEP_TIMEOUT=120  # 每步最多 120 秒
errors=0

run_step() {
    local label="$1"
    shift
    echo "[$label] 开始..."
    if timeout $STEP_TIMEOUT "$@" 2>&1; then
        echo "[$label] ✅"
        return 0
    else
        local rc=$?
        if [ $rc -eq 124 ]; then
            echo "[$label] ⚠️ 超时 (${STEP_TIMEOUT}s)，跳过"
        else
            echo "[$label] ❌ 失败 (exit=$rc)"
        fi
        errors=$((errors + 1))
        return $rc
    fi
}

# Step 1: 自动补链
run_step "1/5 自动补链" python3 "$VAULT_SCRIPTS/vault_autolink.py" --apply <<< "y" || true

# Step 2: 健康巡检（容易超时，单独保护）
run_step "2/5 健康巡检" python3 "$VAULT_SCRIPTS/vault_health.py" || true

# Step 3: 更新知识库总索引
run_step "3/5 知识库总索引" python3 "$VAULT_SCRIPTS/vault_master_index_update.py" || true

# Step 4: 更新资讯索引
run_step "4/5 资讯索引" python3 "$VAULT_SCRIPTS/vault_news_index_update.py" || true

# Step 5a: 更新对话归档索引
run_step "5a/5 对话归档索引" python3 "$VAULT_SCRIPTS/vault_conversation_index_update.py" || true

# Step 5b: 检测手工维护的索引是否过期
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
    mtime=$(stat -f "%m" "$file" 2>/dev/null || echo 0)
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

echo "[5b/5] 手工索引过期检测..."
check_index_stale "$VAULT/工具笔记/🔧工具笔记索引.md" "🔧工具笔记索引"
check_index_stale "$VAULT/工具笔记/skills/🛠Skills文档索引.md" "🛠Skills文档索引"

if [ "$EXPIRED" -gt 0 ]; then
    echo "  ⚠️  发现 $EXPIRED 个过期索引"
else
    echo "  ✅ 所有手工索引均在有效期内"
fi

echo ""
echo "=== [$NOW] 维护完成 (错误数: $errors) ==="

# 写入投递队列
QUEUE_DIR="$HOME/.hermes/delivery-queue/pending"
mkdir -p "$QUEUE_DIR"
cat > "$QUEUE_DIR/$(date +%Y%m%d-%H%M)-knowledge-maint.txt" <<EOF
📚 知识库维护完成 $NOW
错误: $errors 个步骤失败
报告: $VAULT/📊 知识库健康报告.md
EOF

exit $errors
