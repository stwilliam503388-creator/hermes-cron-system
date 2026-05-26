#!/bin/bash
# notebooklm-rebuild.sh — 全量拆分重建
# 将当前所有来源按分类拆到独立 Notebook
#
# 7 个分类 → 7 个 Notebook：
#   概念        → AI 知识库 · 概念
#   对话归档    → AI 知识库 · 对话归档
#   工具知识库   → AI 知识库 · 工具笔记
#   工作流      → AI 知识库 · 工作流
#   资讯趋势    → AI 知识库 · 资讯
#   学习参考    → AI 知识库 · 学习笔记
#   参考        → AI 知识库 · 参考

set -euo pipefail

NOTEBOOKLM_VENV="/Users/liuwei/.hermes/notebooklm_venv/bin/python"
SYNC_SCRIPT="/Users/liuwei/.hermes/scripts/notebooklm-sync.py"
EXPORT_SCRIPT="/Users/liuwei/.hermes/scripts/export-obsidian-to-notebooklm.sh"
EXPORT_BASE="/Users/liuwei/Desktop/NotebookLM-导出"
VAULT="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
TODAY=$(date +%Y-%m-%d)

declare -A CATEGORIES=(
    ["概念"]="AI 知识库 · 概念"
    ["对话归档"]="AI 知识库 · 对话归档"
    ["工具知识库"]="AI 知识库 · 工具笔记"
    ["工作流"]="AI 知识库 · 工作流"
    ["资讯趋势"]="AI 知识库 · 资讯"
    ["学习参考"]="AI 知识库 · 学习笔记"
    ["参考"]="AI 知识库 · 参考"
)

echo "══════════ NotebookLM 全量拆分重建 ══════════"
echo "日期: $TODAY"
echo "分类数: ${#CATEGORIES[@]}"
echo ""

# ── Step 0: 全局导出（一次性导出所有分类） ──
echo "━━━ Step 0: 全局导出 ━━━"
bash "$EXPORT_SCRIPT" 2>&1
echo ""

EXPORT_DIR="$EXPORT_BASE/$TODAY"
if [ ! -d "$EXPORT_DIR" ]; then
    echo "❌ 导出目录不存在: $EXPORT_DIR"
    exit 1
fi

# ── Step 1-7: 逐个分类上传 ──
TOTAL=${#CATEGORIES[@]}
CURRENT=0
FAILED=()

for CAT_DIR in "${!CATEGORIES[@]}"; do
    CURRENT=$((CURRENT + 1))
    NOTEBOOK_NAME="${CATEGORIES[$CAT_DIR]}"
    
    echo "━━━ [$CURRENT/$TOTAL] $CAT_DIR → $NOTEBOOK_NAME ━━━"
    
    # 检查该分类在导出目录里是否有文件
    FILE_COUNT=$(find "$EXPORT_DIR/$CAT_DIR" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
    if [ "$FILE_COUNT" -eq 0 ]; then
        echo "  ⏭️ 无文件，跳过"
        echo ""
        continue
    fi
    
    echo "  文件数: $FILE_COUNT"
    
    # 上传（指定 notebook 名称 + 分类过滤）
    "$NOTEBOOKLM_VENV" "$SYNC_SCRIPT" \
        --notebook "$NOTEBOOK_NAME" \
        --category "$CAT_DIR" 2>&1
    
    RET=$?
    if [ $RET -ne 0 ]; then
        FAILED+=("$CAT_DIR")
        echo "  ⚠️ 上传异常 (exit=$RET)"
    fi
    echo ""
done

# ── 汇总 ──
echo "══════════ 重建完成 ══════════"
echo "成功: $((TOTAL - ${#FAILED[@]}))/$TOTAL"
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "失败: ${FAILED[*]}"
fi
echo ""
echo "❗ 接下来请手动在 NotebookLM 中删除旧的 2 个 notebook："
echo "   - Hermes-知识归档 (302 来源)"
echo "   - Hermes-知识归档-2 (67 来源)"
echo ""
echo "操作步骤："
echo "   1. 打开 https://notebooklm.google.com"
echo "   2. 在左侧列表找到这两个 notebook"
echo "   3. 点击 ⋮ → 删除"
