#!/bin/bash
# =============================================================
# sleep-weekly-report.sh — 睡眠/屏幕时间 周报
# no_agent 模式: 每周一 08:00 执行，通过 email-broadcast 推送
# 数据来源: pmset 日志 + Screen Time SQLite
# =============================================================
ST_DAYS=7
END_DATE=$(date '+%Y-%m-%d')
START_DATE=$(date -j -v-${ST_DAYS}d '+%Y-%m-%d')
HOST=$(scutil --get ComputerName 2>/dev/null || echo "MacBook")

# ── 睡眠分析 ──
SLEEP_DATA=$(pmset -g log 2>/dev/null | grep "Sleep\|Wake" | tail -100)
SLEEP_COUNT=$(echo "$SLEEP_DATA" | grep -c "Sleep  " 2>/dev/null || echo 0)
WAKE_COUNT=$(echo "$SLEEP_DATA" | grep -c "Wake  " 2>/dev/null || echo 0)

# 估算睡眠时长（秒）
LAST_WAKES=$(pmset -g log 2>/dev/null | grep "Wake  " | tail -7 | awk '{print $1, $2, $3}')
LAST_SLEEPS=$(pmset -g log 2>/dev/null | grep "Sleep  " | tail -7 | awk '{print $1, $2, $3}')

# ── 屏幕时间 (macOS Screen Time SQLite) ──
ST_DB="$HOME/Library/Application Support/Knowledge/knowledgeC.db"
SCREEN_HOURS="N/A"
if [ -f "$ST_DB" ]; then
    SCREEN_HOURS=$(sqlite3 "$ST_DB" "
        SELECT ROUND(SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) / 3600.0, 1)
        FROM ZOBJECT
        WHERE ZOBJECT.ZSTREAMNAME = '/app/usage'
        AND ZOBJECT.ZSTARTDATE > ($(date -j -v-${ST_DAYS}d +%s) - 978307200)
        AND ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE > 0
    " 2>/dev/null || echo "N/A")
fi

# ── 电池健康 ──
BATTERY_CYCLES=$(system_profiler SPPowerDataType 2>/dev/null | grep "Cycle Count" | awk '{print $3}')
BATTERY_HEALTH=$(system_profiler SPPowerDataType 2>/dev/null | grep "Condition" | awk '{print $2, $3}')
LAST_CHARGE=$(pmset -g log 2>/dev/null | grep "Connected to AC\|Battery Power" | tail -1 | awk '{print $1, $2, $3}')

# ── 输出 ──
cat << REPORT
═══════════════════════════════════════════
  睡眠 & 屏幕时间周报
  ${START_DATE} ~ ${END_DATE} | ${HOST}
═══════════════════════════════════════════

💤 睡眠
  入眠次数: ${SLEEP_COUNT}
  唤醒次数: ${WAKE_COUNT}
  数据来源: pmset 日志

📱 屏幕使用
  预估总使用: ${SCREEN_HOURS} 小时（7天）
  日均: $(echo "scale=1; ${SCREEN_HOURS:-0} / 7" | bc 2>/dev/null) 小时

🔋 电池
  循环次数: ${BATTERY_CYCLES:-N/A}
  健康状态: ${BATTERY_HEALTH:-N/A}
  最近充电: ${LAST_CHARGE:-N/A}

📋 趋势说明
  超量: $(echo "${SCREEN_HOURS:-0} > 49" | bc -l 2>/dev/null | grep -q 1 && echo "📌 本周日均使用超过7小时，建议注意用眼健康" || echo "✅ 屏幕时间在合理范围内")
  健康: $(echo "${BATTERY_HEALTH:-Normal}" | grep -qi "Normal" && echo "✅ 电池状态正常" || echo "⚠️ 建议检查电池健康")

═══════════════════════════════════════════
