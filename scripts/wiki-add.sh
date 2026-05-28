#!/bin/bash
# wiki-add.sh — 添加内容到 Karpathy LLM Wiki 知识库
# 用法:
#   wiki-add article <标题> [content_file]       → raw/articles/
#   wiki-add note <标题> [content_file]           → raw/notes/
#   wiki-add archive <标题> [content_file]         → raw/archives/daily/
#   wiki-add repo <owner/repo> [url]               → raw/repos/github/
#   wiki-add link <标题> <url>                     → raw/articles/（带来源URL）
#
# 标题：自定义
# content_file：包含正文的文件路径，留空则从 stdin 读取
#
set -euo pipefail

VAULT="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
TODAY=$(date "+%Y-%m-%d")
NOW=$(date "+%H:%M")

usage() {
  echo "用法:"
  echo "  wiki-add article <标题> [content_file]"
  echo "  wiki-add note <标题> [content_file]"
  echo "  wiki-add archive <标题> [content_file]"
  echo "  wiki-add repo <owner/repo> [url]"
  echo "  wiki-add link <标题> <url>"
  exit 1
}

[ $# -lt 2 ] && usage

TYPE="$1"
TITLE="$2"
shift 2

case "$TYPE" in
  article)
    DIR="$VAULT/raw/articles/note"
    ;;
  note)
    DIR="$VAULT/raw/notes"
    ;;
  archive)
    DIR="$VAULT/raw/archives/daily"
    ;;
  repo)
    DIR="$VAULT/raw/repos/github"
    REPO_NAME="$TITLE"
    TITLE="$REPO_NAME"
    URL="${1:-}"
    ;;
  link)
    DIR="$VAULT/raw/articles/link"
    URL="$1"
    shift
    ;;
  *)
    echo "未知类型: $TYPE（支持: article/note/archive/repo/link）"
    exit 1
    ;;
esac

# Read content
if [ $# -ge 1 ] && [ -f "$1" ]; then
  CONTENT_FILE="$1"
  CONTENT=$(cat "$CONTENT_FILE")
else
  CONTENT=$(cat)
fi

# Generate filename
SAFE_TITLE=$(echo "$TITLE" | sed 's/[\/:*?"<>|]/_/g' | tr -s ' ')
FILENAME="$TODAY-${SAFE_TITLE:0:50}.md"
FILEPATH="$DIR/$FILENAME"

mkdir -p "$DIR"

# Build content with variables
FULL_CONTENT="---
title: $TITLE
created: $TODAY
updated: $TODAY
tags: [auto-added, $TYPE]
source_type: $TYPE
---

# $TITLE

> 自动添加于 $TODAY $NOW

$CONTENT

---
_自动通过 wiki-add 添加 | ${TODAY} ${NOW}_
"

echo "$FULL_CONTENT" > "$FILEPATH"

echo "✅ 已保存: $FILEPATH"
echo "   ($(wc -c < "$FILEPATH") bytes)"

# Update log
echo "- $TODAY wiki-add | $TITLE → ${TYPE}s/" >> "$VAULT/log.md" 2>/dev/null || true
