#!/bin/bash
# =============================================================
# price-monitor.sh — 商品价格监控框架
# 使用方法:
#   1. 在下面 PRODUCTS 数组中配置要监控的商品
#   2. 运行: bash price-monitor.sh
#   3. 有降价时自动通过 email-broadcast 通知
#
# 支持的平台: 京东(jd.com), 淘宝(tmall), 亚马逊(amazon)
# 依赖: curl, python3 (解析HTML/JSON)
# =============================================================

# ── 在这里配置你要监控的商品 ──
# 格式: "名称|平台|商品ID|URL|期望价格"
# 商品ID: 京东是数字ID, 淘宝是item_id, 亚马逊是ASIN
PRODUCTS=(
    # 示例: "Apple MacBook Air M5|jd|10012345678|https://item.jd.com/10012345678.html|8999"
    # 示例: "Kindle Paperwhite|amazon|B0ABCDEFGH|https://www.amazon.cn/dp/B0ABCDEFGH|899"
    # 请自行添加你要监控的商品 ↓
)

# ── 价格数据缓存（避免重复通知）─
CACHE_FILE="$HOME/.hermes/price_cache.txt"
[ -f "$CACHE_FILE" ] || touch "$CACHE_FILE"

ALERTS=""
NOW=$(date '+%Y-%m-%d %H:%M')

for product in "${PRODUCTS[@]}"; do
    IFS='|' read -r name platform pid url target_price <<< "$product"
    [ -z "$name" ] && continue
    
    current_price=""
    
    case "$platform" in
        jd|京东)
            # 京东价格 API（非官方，仅供参考）
            api_url="https://p.3.cn/prices/mgets?skuIds=J_${pid}"
            resp=$(curl -s --connect-timeout 10 "$api_url" 2>/dev/null)
            current_price=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('p',''))" 2>/dev/null)
            ;;
        amazon)
            # Amazon 页面抓取
            resp=$(curl -s -L --connect-timeout 10 \
                -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" \
                "https://www.amazon.cn/dp/${pid}" 2>/dev/null)
            current_price=$(echo "$resp" | grep -oP 'price_whole["\s:]+[\d.]+' | grep -oP '[\d.]+$' | head -1)
            ;;
        tmall|淘宝)
            # 淘宝（较复杂，移动端 API 可能有变化）
            current_price="N/A（需要cookie）"
            ;;
    esac
    
    # 检查是否低于期望价格
    if [ -n "$current_price" ] && [ "$current_price" != "N/A" ]; then
        cmp=$(echo "$current_price <= $target_price" | bc -l 2>/dev/null)
        if [ "$cmp" = "1" ]; then
            # 检查是否已通知过
            if ! grep -q "${pid}:${current_price}" "$CACHE_FILE" 2>/dev/null; then
                ALERTS="${ALERTS}🔔 $name 降价至 ¥$current_price（目标价 ¥$target_price）\n   $url\n"
                echo "${pid}:${current_price}" >> "$CACHE_FILE"
            fi
        fi
    fi
done

# 清理旧缓存（保留7天）
find "$CACHE_FILE" -mtime +7 -exec rm -f {} \; 2>/dev/null

# 输出告警
if [ -n "$ALERTS" ]; then
    echo "━━━ 价格监控告警 ━━━━"
    echo "时间: $NOW"
    echo ""
    echo -e "$ALERTS"
    echo "━━━━━━━━━━━━━━━━━"
    
    # 如果配置了商品且有降价，发送邮件
    if [ ${#PRODUCTS[@]} -gt 0 ]; then
        echo -e "$ALERTS" | python3 ~/.hermes/scripts/email-broadcast.py '价格监控' 2>/dev/null || true
    fi
else
    # 静默模式：无降价不输出
    if [ ${#PRODUCTS[@]} -gt 0 ]; then
        echo "✓ 已检查 ${#PRODUCTS[@]} 个商品，暂无降价"
    else
        echo "⚠️ 未配置监控商品。请编辑 PRODUCTS 数组后重新运行。"
        echo "格式: \"名称|平台|商品ID|URL|期望价格\""
    fi
fi
