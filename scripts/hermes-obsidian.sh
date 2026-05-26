#!/bin/bash
# hermes-obsidian.sh — 追加格式化条目到 Obsidian 每日归档笔记
# 用法:
#   hermes-obsidian add <title> <tags> [content_file]
#     - title: 条目标题
#     - tags: 逗号分隔的关键词
#     - content_file: 包含条目正文的文件路径，留空则从 stdin 读取
#
#   条目正文格式（Markdown）:
#     ## 简介
#     ...
#     ## 操作摘要
#     ...
#     ## 知识点
#     ...
#     ## 相关链接
#     ...

set -euo pipefail

# 加载统一环境变量
SOURCE_SCRIPT="$(dirname "$0")/setenv.sh"
[ -f "$SOURCE_SCRIPT" ] && source "$SOURCE_SCRIPT"

VAULT="${OBSIDIAN_VAULT_PATH:?环境变量 OBSIDIAN_VAULT_PATH 未设置}"
ARCHIVE_DIR="$VAULT/对话归档"
TODAY=$(date "+%Y-%m-%d")
NOW=$(date "+%H:%M")
DAILY_FILE="$ARCHIVE_DIR/$TODAY.md"

ensure_daily_file() {
    if [ ! -f "$DAILY_FILE" ]; then
        cat > "$DAILY_FILE" << EOF
# $TODAY 对话归档

---
EOF
        echo "Created $DAILY_FILE"
    fi
}

add_entry() {
    local title="$1"
    local tags="$2"
    local content_file="${3:-}"
    local body=""

    if [ -n "$content_file" ] && [ -f "$content_file" ]; then
        body=$(cat "$content_file")
    else
        body=$(cat)
    fi

    ensure_daily_file

    # Build tag line
    local tag_line=""
    IFS=',' read -ra TAG_ARRAY <<< "$tags"
    for tag in "${TAG_ARRAY[@]}"; do
        trimmed_tag=$(echo "$tag" | xargs | tr ' ' '-')
        tag_line+="#$trimmed_tag "
    done

    {
        echo ""
        echo "---"
        echo ""
        echo "## 🟢 $NOW $title"
        echo "**标签:** $tag_line"
        echo ""
        echo "$body"
    } >> "$DAILY_FILE"

    echo "✓ 已写入: $DAILY_FILE"
}

show_help() {
    echo "用法: hermes-obsidian <command> [args]"
    echo ""
    echo "命令:"
    echo "  add <标题> <标签(逗号分隔)> [内容文件]"
    echo "      追加一个新条目到今日归档"
    echo "      内容文件可选，留空则从 stdin 读取"
    echo ""
    echo "  today"
    echo "      打开今日归档笔记（输出路径 + macOS 上直接启动 Obsidian 打开）"
    echo ""
    echo "  help"
    echo "      显示此帮助"
}

case "${1:-help}" in
    add)
        shift
        add_entry "$1" "$2" "${3:-}"
        ;;
    today)
        echo "$DAILY_FILE"
        # macOS 上直接打开 Obsidian
        if command -v open &>/dev/null; then
            if [ -f "$DAILY_FILE" ]; then
                open -a Obsidian "$DAILY_FILE"
            elif [ -f "$DAILY_FILE.md" ]; then
                open -a Obsidian "$DAILY_FILE.md"
            else
                echo "⚠️ 文件不存在，请先添加条目: $DAILY_FILE"
            fi
        fi
        ;;
    help|*)
        show_help
        ;;
esac
