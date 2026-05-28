#!/bin/bash
# export-obsidian-to-notebooklm.sh — v2
# P2: 导出后清理旧文件，只保留最近3天
# P5: NotebookLM 问答友好化（去噪声时间戳/emoji前缀）
# P6: 注入 Category 头 + 按分类分目录

set -uo pipefail

# 加载统一环境变量
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

VAULT="${OBSIDIAN_VAULT_PATH:?环境变量 OBSIDIAN_VAULT_PATH 未设置}"
EXPORT_BASE="$HOME/Desktop/NotebookLM-导出"
EXPORT_DIR="$EXPORT_BASE/$(date +%Y-%m-%d)"

# 读取配置
CONFIG="$HOME/.hermes/obsidian-categories.json"
SKIP_CATEGORIES=""

if [ -f "$CONFIG" ]; then
    # 从 JSON 中读取 notebooklm_skip_categories
    SKIP_CATEGORIES=$(python3 -c "
import json
try:
    with open('$CONFIG') as f:
        c = json.load(f)
    print(','.join(c.get('notebooklm_skip_categories', [])))
except:
    pass
" 2>/dev/null || echo "")
fi

echo "══════════ 导出到 NotebookLM v2 ══════════"
echo "跳过分类: ${SKIP_CATEGORIES:-无}"

# 清理旧导出：保留最近 3 天
cleanup_list=$(find "$EXPORT_BASE" -maxdepth 1 -type d -name "20*" | sort)
total_dirs=$(echo "$cleanup_list" | wc -l | tr -d ' ')
keep=$((total_dirs - 3))
if [ "$keep" -gt 0 ]; then
    echo "$cleanup_list" | head -n "$keep" | while read old; do
        rm -rf "$old"
        echo "  🗑️ 清理旧导出: $(basename "$old")"
    done
fi

mkdir -p "$EXPORT_DIR"
# 清空今日目录（避免残留导致重复）
rm -f "$EXPORT_DIR"/*/*.md 2>/dev/null || true

clean_note() {
    local src="$1"
    local dst="$2"
    local category="$3"

    [ -f "$src" ] || return

    local basename
    basename=$(basename "$src" .md)
    local output="$EXPORT_DIR/$dst/$basename.md"

    mkdir -p "$(dirname "$output")"

    # 写入内容（保留原始标题行作为标题，在标题后注入 Category）
    sed -n '
        /^## [🟢🟡]/d
        /^\*\*标签:\*\*/{
            s/\*\*标签:\*\*/Tags: /
            s/`#\([^`]*\)`/\1/g
            p
            d
        }
        /^---$/d
        /^_自动整理/d
        /^> 归档于/d
        /^\[\[\([^]|]*\)|\([^]]*\)\]\]/{
            s/\[\[\([^]|]*\)|\([^]]*\)\]\]/\2/
            p
            d
        }
        /^\[\[\([^]]*\)\]\]/{
            s/\[\[\([^]]*\)\]\]/\1/
            p
            d
        }
        p
    ' "$src" >> "$output"

    # 在第一行 # Title 后注入 Category
    if [ -f "$output" ]; then
        sed -i '' '1a\
> 分类: '"$category"'
' "$output" 2>/dev/null || true
    fi

    # 如果文件只有 3 行（标题+空行+Category），说明内容太少了，跳过
    local line_count
    line_count=$(wc -l < "$output")
    if [ "$line_count" -le 4 ]; then
        rm "$output"
        echo "  ⚠ 跳过空笔记: $basename"
        return
    fi

    echo "  ✓ $dst/$basename.md"
}

export_category() {
    local src="$1"
    local dst="$2"
    local cat_name="$3"

    if [ ! -d "$src" ]; then
        return
    fi

    # P7: 选择性同步
    for skip in $(echo "$SKIP_CATEGORIES" | tr ',' ' '); do
        if [ "$cat_name" = "$skip" ]; then
            echo "  ⏭️ 跳过分类: $cat_name（配置已排除）"
            return
        fi
    done

    # 递归扫描所有 .md 文件（包括子目录）
    while IFS= read -r -d '' f; do
        clean_note "$f" "$dst" "$cat_name"
    done < <(find "$src" -name '*.md' -print0)
}

export_category "$VAULT/工具笔记" "工具知识库" "工具笔记"
export_category "$VAULT/学习笔记" "学习参考" "学习笔记"
export_category "$VAULT/资讯" "资讯趋势" "资讯"
export_category "$VAULT/工作流" "工作流" "工作流"
export_category "$VAULT/概念" "概念" "概念"
export_category "$VAULT/对话归档" "对话归档" "对话归档"
export_category "$VAULT/参考" "参考" "参考"
export_category "$VAULT/课程项目" "课程项目" "课程项目"
export_category "$VAULT/学习计划" "学习计划" "学习计划"
export_category "$VAULT/资源" "资源" "资源"

total=$(find "$EXPORT_DIR" -name "*.md" | wc -l | tr -d ' ')

echo ""
echo "══════════ 导出完成 ══════════"
echo "位置: $EXPORT_DIR"
echo "共 $total 篇清洁笔记"
