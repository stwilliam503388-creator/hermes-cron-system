#!/bin/bash
# =============================================================
# browser-tabs-archive.sh — 浏览器标签页自动归档到 Obsidian
# 每天 23:00 运行，保存当前打开的标签页 URL 到 Obsidian
# 支持 Safari + Chrome
# =============================================================
VAULT="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
DATE=$(date '+%Y-%m-%d')
FILENAME="$VAULT/工具笔记/浏览器标签页归档_${DATE}.md"

# Safari 标签页
SAFARI_TABS=$(osascript -e '
tell application "System Events"
    if exists (process "Safari") then
        tell application "Safari"
            set tabList to {}
            repeat with w in windows
                repeat with t in tabs of w
                    set end of tabList to (name of t) & "|||" & (URL of t)
                end repeat
            end repeat
            return tabList
        end tell
    else
        return ""
    end if
end tell' 2>/dev/null)

# Chrome 标签页
CHROME_TABS=$(osascript -e '
tell application "System Events"
    if exists (process "Google Chrome") then
        tell application "Google Chrome"
            set tabList to {}
            repeat with w in windows
                repeat with t in tabs of w
                    set end of tabList to (title of t) & "|||" & (URL of t)
                end repeat
            end repeat
            return tabList
        end tell
    else
        return ""
    end if
end tell' 2>/dev/null)

# 如果都为空，跳过
if [ -z "$SAFARI_TABS" ] && [ -z "$CHROME_TABS" ]; then
    echo "没有打开的浏览器标签页，跳过归档" >&2
    exit 0
fi

# 生成 Markdown
{
    echo "---"
    echo "title: 浏览器标签页归档 - ${DATE}"
    echo "date: ${DATE}"
    echo "tags: [自动化, 浏览器, 归档]"
    echo "---"
    echo ""
    echo "# 浏览器标签页归档 — ${DATE}"
    echo ""
    echo "> 自动归档于 $(date '+%H:%M')"
    echo ""
    
    # Safari
    SAFARI_COUNT=$(echo "$SAFARI_TABS" | tr ',' '\n' | grep -c "|||" 2>/dev/null || echo 0)
    if [ "$SAFARI_COUNT" -gt 0 ]; then
        echo "## Safari（${SAFARI_COUNT} 个标签页）"
        echo ""
        echo "$SAFARI_TABS" | tr ',' '\n' | while IFS='|||' read -r title url; do
            [ -z "$title" ] && continue
            echo "- [${title}](${url})"
        done
        echo ""
    fi
    
    # Chrome
    CHROME_COUNT=$(echo "$CHROME_TABS" | tr ',' '\n' | grep -c "|||" 2>/dev/null || echo 0)
    if [ "$CHROME_COUNT" -gt 0 ]; then
        echo "## Google Chrome（${CHROME_COUNT} 个标签页）"
        echo ""
        echo "$CHROME_TABS" | tr ',' '\n' | while IFS='|||' read -r title url; do
            [ -z "$title" ] && continue
            echo "- [${title}](${url})"
        done
        echo ""
    fi
    
    echo "---"
    echo "_本笔记由 Hermes 浏览器标签页归档任务自动生成_"
} > "$FILENAME"

echo "✓ 已归档: $FILENAME"
echo "Safari: ${SAFARI_COUNT:-0} | Chrome: ${CHROME_COUNT:-0}"
