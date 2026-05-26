#!/usr/bin/env python3
"""Xianyu Arbitrage Tracker — scans listing files and builds daily/weekly summary.

Runs as no_agent cron job daily at 23:45.
"""
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

ARB_ROOT = "/Users/liuwei/xianyu-arbitrage"
LISTINGS_DIR = os.path.join(ARB_ROOT, "listings")

def parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            # Strip quotes and whitespace
            val = val.strip().strip('"').strip("'")
            result[key.strip()] = val
    return result

def scan_date(target_date: str) -> list:
    """Return list of listing dicts for a given date."""
    listings = []
    if not os.path.isdir(LISTINGS_DIR):
        return listings
    
    for fname in sorted(os.listdir(LISTINGS_DIR)):
        if not fname.startswith(target_date) or not fname.endswith(".md"):
            continue
        
        fpath = os.path.join(LISTINGS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        
        fm = parse_frontmatter(content)
        profit = 0
        try:
            profit = float(fm.get("profit_per_unit", "0").replace("元", ""))
        except ValueError:
            pass
        
        # Extract product name from title
        title = ""
        for line in content.split("\n"):
            if line.startswith("# 闲鱼商品："):
                title = line.replace("# 闲鱼商品：", "").strip()
                break
        
        listings.append({
            "file": fname,
            "title": title,
            "source_price": fm.get("source_price", "?"),
            "xianyu_price": fm.get("xianyu_price", "?"),
            "profit": profit,
            "category": fm.get("category", "unknown"),
            "source_platform": fm.get("source_platform", "unknown"),
            "status": fm.get("status", "ready"),
        })
    
    return listings

def scan_week(target_date_str: str) -> dict:
    today = datetime.strptime(target_date_str, "%Y-%m-%d")
    weekly = {"total_listings": 0, "total_potential_profit": 0, "days": {}}
    
    for i in range(7):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_listings = scan_date(day_str)
        if day_listings:
            day_profit = sum(l["profit"] for l in day_listings)
            weekly["days"][day_str] = {
                "count": len(day_listings),
                "profit": day_profit,
                "listings": day_listings,
            }
            weekly["total_listings"] += len(day_listings)
            weekly["total_potential_profit"] += day_profit
    
    return weekly

def build_summary(target_date: str) -> str:
    today_listings = scan_date(target_date)
    weekly = scan_week(target_date)
    
    lines = []
    lines.append(f"🛒 闲鱼选品日报 {target_date}")
    lines.append("")
    
    if not today_listings:
        lines.append("⚠️ 今日无选品推荐（cron 任务可能未执行）")
    else:
        today_profit = sum(l["profit"] for l in today_listings)
        lines.append(f"今日推荐: {len(today_listings)} 个选品, 单件利润合计 {today_profit:.0f} 元")
        lines.append("")
        for i, l in enumerate(today_listings, 1):
            lines.append(f"{i}. {l['title'][:40]}")
            lines.append(f"   进货{l['source_price']} → 卖{l['xianyu_price']} | 利润{l['profit']:.0f}元/单 | {l['source_platform']}")
        lines.append("")
    
    lines.append(f"本周累计: {weekly['total_listings']} 个选品, 潜在利润 {weekly['total_potential_profit']:.0f} 元/单")
    lines.append("")
    lines.append("💡 操作提醒:")
    lines.append("  1. 打开 /Users/liuwei/xianyu-arbitrage/listings/ 查看完整文案")
    lines.append("  2. 复制到闲鱼上架（2-3分钟/品）")
    lines.append("  3. 有人下单 → 去1688代发（复制地址即可）")
    
    return "\n".join(lines)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    summary = build_summary(today)
    print(summary)

if __name__ == "__main__":
    main()
