#!/bin/bash
# run-obsidian-pipeline.sh — Obsidian 凌晨自动化完整流水线
#
# 链式步骤（乐观执行：失败不阻塞后续）:
#   0️⃣  ensure-clashx-us-node    — 确保 US/JP 代理节点
#   1️⃣  midnight-cleanup          — 整理昨日对话归档 → 分类拆分 + MOC Dashboard
#   2️⃣  export-obsidian-to-notebooklm — 导出清洁笔记到桌面
#   3️⃣  notebooklm-sync            — 上传清洁笔记到 NotebookLM
#   4️⃣  推送汇总报告（通过飞书 + send_message）
#
# 用法: bash run-obsidian-pipeline.sh [--date YYYY-MM-DD]
#   默认处理昨日 (macOS date -v-1d)

set -uo pipefail

# 加载统一环境变量
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

VAULT="${OBSIDIAN_VAULT_PATH:-/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault}"
HERMES="${HERMES_SCRIPTS:-$HOME/.hermes/scripts}"
NOTEBOOKLM_VENV="${NOTEBOOKLM_VENV:-/Users/liuwei/.hermes/notebooklm_venv/bin/python}"

# 计算日期
if [[ "$1" == "--date" && -n "$2" ]]; then
    TARGET_DATE="$2"
    shift 2
else
    TARGET_DATE=$(date -v-1d "+%Y-%m-%d")
fi

NOW=$(date "+%H:%M:%S")

echo "╔════════════════════════════════════════╗"
echo "║  Obsidian 自动化流水线                  ║"
echo "║  处理日期: $TARGET_DATE"
echo "║  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "╚════════════════════════════════════════╝"
echo ""

STEPS=(
    "0️⃣  ClashX 节点检查"
    "1️⃣  对话归档整理"
    "1b️⃣ 概念萃取+去重"
    "2️⃣  导出清洁笔记"
)
RESULTS=()
RETCODES=()

# ── Step 0: 确保 ClashX 在 US/JP 节点（重试3次） ──
echo "━━━ ${STEPS[0]} ━━━"
CLASHX_OK=false
for attempt in 1 2 3; do
  echo "  → 尝试第 $attempt/3 次..."
  if bash "$HERMES/ensure-clashx-us-node.sh" 2>&1; then
    CLASHX_OK=true
    echo "  → US/JP 节点已确保"
    break
  fi
  [ "$attempt" -lt 3 ] && echo "  → 等待 30 秒后重试..." && sleep 30
done
if [ "$CLASHX_OK" = true ]; then
    RESULTS+=("✅ 成功")
else
    RESULTS+=("⚠️ 跳过（3次重试均失败，继续后续步骤）")
fi
RETCODES+=(0)
echo ""

# ── Step 1: midnight-cleanup ──
echo "━━━ ${STEPS[1]} ━━━"
cd "$VAULT"
output=$(python3 "$HERMES/midnight-cleanup.py" --date "$TARGET_DATE" 2>&1)
ret=$?
echo "$output"
if [ $ret -eq 0 ]; then
    RESULTS+=("✅ 成功")
    CLEANUP_RESULT=$(echo "$output" | tail -1)
else
    RESULTS+=("❌ 失败 (exit=$ret)")
fi
RETCODES+=($ret)
echo ""

# ── Step 1b: 概念萃取 + 即时去重（归档整理完成后立即触发） ──
echo "━━━ ${STEPS[2]} ━━━"
CONCEPT_OK=true

# 先萃取
echo "  → 概念萃取..."
extract_output=$(python3 "$HERMES/vault_archive_concept_extract.py" 2>&1) || true
echo "$extract_output" | head -5

# 再触发去重（即时，非阻塞）
echo "  → 即时去重检测..."
dedup_output=$(python3 "$HERMES/vault_concept_dedup.py" 2>&1) || true
echo "$dedup_output" | head -5

RESULTS+=("✅ 完成")
RETCODES+=(0)
echo ""

# ── Step 2: 导出清洁笔记 ──
echo "━━━ ${STEPS[3]} ━━━"
output=$(bash "$HERMES/export-obsidian-to-notebooklm.sh" 2>&1)
ret=$?
echo "$output"
if [ $ret -eq 0 ]; then
    EXPORT_COUNT=$(echo "$output" | grep -E '共.*篇' | tail -1)
    RESULTS+=("✅ 成功")
else
    RESULTS+=("❌ 失败 (exit=$ret)")
fi
RETCODES+=($ret)
echo ""

# ── Step 4: 汇总报告 ──
echo "━━━ 汇总报告 ━━━"
SUMMARY="【Obsidian 流水线 · ${TARGET_DATE} · ${NOW}】"
echo "$SUMMARY"
echo ""
for i in "${!STEPS[@]}"; do
    echo "  ${STEPS[$i]}: ${RESULTS[$i]}"
done
echo ""
echo "详情:"
echo "  归档文件: $VAULT/对话归档/$TARGET_DATE.md"
echo "  导出目录: $HOME/Desktop/NotebookLM-导出/$(date +%Y-%m-%d)"
echo ""

# 所有步骤退出码的汇总（非致命）
overall=0
for r in "${RETCODES[@]}"; do
    [ "$r" -ne 0 ] && overall=1
done
exit $overall
