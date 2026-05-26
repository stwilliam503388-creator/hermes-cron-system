#!/bin/bash
# =============================================================
# system-alert.sh — 磁盘/内存/CPU 告警监视器
# no_agent 模式: 仅当阈值触发时才输出（非空 stdout = 告警）
# 调度: 每小时运行一次
# =============================================================
# 阈值
DISK_WARN=85   # 磁盘使用率 > 85% 告警
MEM_WARN=20     # 空闲内存 < 20% 告警
LOAD_WARN=8     # 1分钟负载 > 8 告警

ALERTS=""

# 磁盘检查
DISK_PCT=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt "$DISK_WARN" ]; then
    DISK_INFO=$(df -h / | awk 'NR==2{print $2, $3, $4}')
    ALERTS="${ALERTS}⚠️ 磁盘告警: 已用 ${DISK_PCT}% (总量 $DISK_INFO)\n"
fi

# 内存检查 (macOS memory_pressure)
MEM_FREE=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk '{print $5}' | tr -d '%')
if [ -n "$MEM_FREE" ] && [ "$MEM_FREE" -lt "$MEM_WARN" ]; then
    MEM_TOTAL=$(sysctl hw.memsize | awk '{print $2/1073741824" GB"}')
    ALERTS="${ALERTS}⚠️ 内存告警: 空闲仅 ${MEM_FREE}% (总量 $MEM_TOTAL)\n"
fi

# 负载检查
LOAD_1=$(sysctl -n vm.loadavg | awk '{print $2}')
LOAD_CMP=$(echo "$LOAD_1 >= $LOAD_WARN" | bc -l 2>/dev/null)
if [ "$LOAD_CMP" = "1" ]; then
    ALERTS="${ALERTS}⚠️ 负载告警: 1min 负载 $LOAD_1 (阈值 $LOAD_WARN)\n"
fi

# 温度检查 (如果可用)
TEMP=$(pmset -g therm 2>/dev/null | grep "CPU_Scheduler_Limit" | awk '{print $3}')
if [ -n "$TEMP" ] && [ "$TEMP" -lt 50 ]; then
    ALERTS="${ALERTS}🔥 CPU 过热限制: 调度限制 ${TEMP}%\n"
fi

# 输出：有告警才发
if [ -n "$ALERTS" ]; then
    HOST=$(scutil --get ComputerName 2>/dev/null || echo "MacBook")
    echo "━━━ Hermes 系统告警 ━━━━"
    echo "主机: $HOST"
    echo "时间: $(date '+%Y-%m-%d %H:%M')"
    echo ""
    echo -e "$ALERTS"
    echo "━━━━━━━━━━━━━━━━━━━━"
    echo "可以调用: python3 ~/.hermes/scripts/email-broadcast.py '系统告警'"
    echo "或直接查看: ssh $HOST"
fi
