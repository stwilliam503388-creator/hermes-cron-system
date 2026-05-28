#!/bin/bash
# =============================================================
# Hermes 12自动化任务 — 一键诊断脚本
# 运行: bash ~/.hermes/scripts/task-all.sh
# =============================================================
# 数据源
VAULT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
WORKSPACE="$HOME/workspace"
SCRIPTS="$HOME/.hermes/scripts"
JOBSFILE=$(mktemp)

echo "════════════════════════════════════════════"
echo "   Hermes 自动化任务体系 — 状态总览"
echo "   用户: 刘伟 | 时间: $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════"
echo ""

# 检查 cron 状态
echo "▶ 检查 Hermes cron jobs..."
cron_list=$(hermes cron list 2>/dev/null)
total_jobs=$(echo "$cron_list" | grep -c "job_id")
echo "  现有 cron jobs: $total_jobs"
echo ""

# 检查各任务依赖
echo "▶ 依赖项检查..."
echo -n "  git         → "; which git        &>/dev/null && echo "✓ $(git --version | head -c20)" || echo "✗"
echo -n "  ffmpeg      → "; which ffmpeg     &>/dev/null && echo "✓" || echo "✗"
echo -n "  osascript   → "; which osascript  &>/dev/null && echo "✓" || echo "✗"
echo -n "  python3     → "; which python3    &>/dev/null && echo "✓ $(python3 --version)" || echo "✗"
echo -n "  faster-whisper → "; pip3 show faster-whisper &>/dev/null && echo "✓" || echo "✗"
echo -n "  ComfyUI     → "; test -d ~/ComfyUI && echo "✓" || echo "✗"
echo -n "  邮件广播脚本 → "; test -f "$SCRIPTS/email-broadcast.py" && echo "✓" || echo "✗"
echo ""

# 检查 Obsidian 仓库状态
echo "▶ Obsidian Vault 状态..."
if [ -d "$VAULT" ]; then
    echo "  ✓ 仓库存在: $VAULT"
    concept_count=$(find "$VAULT/概念" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    notes_count=$(find "$VAULT/学习笔记" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    echo "  概念卡片: $concept_count | 学习笔记: $notes_count"
else
    echo "  ✗ 仓库路径不可用"
fi
echo ""

# 检查工作区 git 仓库
echo "▶ Git 仓库（工作区）..."
for repo in "$WORKSPACE"/*/; do
    if [ -d "$repo/.git" ]; then
        name=$(basename "$repo")
        commits_7d=$(git -C "$repo" log --oneline --since="7 days ago" 2>/dev/null | wc -l | tr -d ' ')
        echo "  $name → $commits_7d commits(7天)"
    fi
done
echo ""

# 系统健康
echo "▶ 系统健康..."
disk=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
mem=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk '{print $5}' | tr -d '%')
echo "  磁盘: ${disk}% | 内存空闲: ${mem:-N/A}%"
echo ""

echo "════════════════════════════════════════════"
echo "   诊断完毕 | $total_jobs 个 cron 运行中"
echo "════════════════════════════════════════════"
rm -f "$JOBSFILE"
