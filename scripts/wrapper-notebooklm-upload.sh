#!/bin/bash
# wrapper-notebooklm-upload.sh — 按分类上传到 NotebookLM（凌晨 02:00）v2
# 导出由 Obsidian 流水线 01:20 完成。本脚本仅做上传。
# 7 个分类 → 7 个独立 Notebook，Session 过期时静默跳过。
# v3: macOS bash 3.2 兼容（移除 declare -A 中文 key）
# v4: Session 阈值从 120h 降到 20h，增加 keepalive_state 检查

set -euo pipefail

NOTEBOOKLM_VENV="/Users/liuwei/.hermes/notebooklm_venv/bin/python"
SYNC_SCRIPT="/Users/liuwei/.hermes/scripts/notebooklm-sync.py"
CONTEXT_FILE="/Users/liuwei/.hermes/notebooklm_session/context.zip"
KEEPALIVE_STATE="/Users/liuwei/.hermes/notebooklm_session/keepalive_state.json"
EXPORT_DIR="/Users/liuwei/Desktop/NotebookLM-导出/$(date +%Y-%m-%d)"

echo "══════════ NotebookLM 上传 (02:00) ══════════"

# Session 预检（v4: 多重检查）
if [ ! -f "$CONTEXT_FILE" ]; then
    echo "❌ context.zip 不存在，跳过上传"
    exit 0
fi

AGE_HOURS=$(python3 -c "
import os, time
mtime = os.path.getmtime('$CONTEXT_FILE')
age = (time.time() - mtime) / 3600
print(int(age))
" 2>/dev/null || echo "999")

# v4: 严格检查 - 超过 20h 就跳过
if [ "$AGE_HOURS" -gt 20 ]; then
    echo "⚠️  Session 可能已过期 (${AGE_HOURS}h > 20h)，跳过上传"
    echo "   keepalive 每 6h 运行，如持续过期需手动重新登录"
    exit 0
fi

# 检查 keepalive 最近一次状态
if [ -f "$KEEPALIVE_STATE" ]; then
    STATUS=$(python3 -c "
import json
with open('$KEEPALIVE_STATE') as f:
    s = json.load(f)
print(s.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "expired" ]; then
        echo "❌ keepalive 标记 session 为 expired，跳过上传（需手动重新登录）"
        exit 0
    fi
fi

echo "Session 有效 (${AGE_HOURS}h 前)"

if [ ! -d "$EXPORT_DIR" ]; then
    echo "⏭️ 导出目录不存在: $EXPORT_DIR"
    exit 0
fi

# ── 7 个分类逐一上传（显式调用，兼容 macOS bash 3.2）──

upload_category() {
    local CAT_DIR="$1"
    local NOTEBOOK_NAME="$2"

    FILE_COUNT=$(find "$EXPORT_DIR/$CAT_DIR" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
    if [ "$FILE_COUNT" -eq 0 ]; then
        echo "  ⏭️  ${CAT_DIR}: 无文件，跳过"
        return 0
    fi

    echo ""
    echo "── ${CAT_DIR} → ${NOTEBOOK_NAME} (${FILE_COUNT} 文件) ──"

    "$NOTEBOOKLM_VENV" "$SYNC_SCRIPT" \
        --notebook "$NOTEBOOK_NAME" \
        --category "$CAT_DIR" 2>&1 | grep -E '✅|❌|📭|📄|上传|⚠️|📊|📓|═══|✓|新 Notebook|UUID|分类'

    return ${PIPESTATUS[0]}
}

FAILED=0
UPLOADED=0

upload_category "工具知识库" "AI 知识库 · 工具笔记" && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "学习参考"   "AI 知识库 · 学习笔记" && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "资讯趋势"   "AI 知识库 · 资讯"     && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "工作流"     "AI 知识库 · 工作流"   && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "概念"       "AI 知识库 · 概念"     && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "对话归档"   "AI 知识库 · 对话归档" && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "参考"       "AI 知识库 · 参考"     && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "课程项目"   "AI 知识库 · 课程项目" && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "学习计划"   "AI 知识库 · 学习计划" && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))
upload_category "资源"       "AI 知识库 · 资源"     && UPLOADED=$((UPLOADED + 1)) || FAILED=$((FAILED + 1))

echo ""
echo "══════════ 上传完成 ══════════"
echo "成功: ${UPLOADED} 个分类"
if [ $FAILED -gt 0 ]; then
    echo "失败: ${FAILED} 个分类"
    exit 1
fi
