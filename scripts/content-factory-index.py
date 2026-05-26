#!/usr/bin/env python3
"""Content Factory Index Builder — scans content-factory/ and generates daily summaries.

Runs as no_agent cron job daily at 23:30.
Outputs summary to stdout (for WeChat) and index.md (for local tracking).
"""
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

CONTENT_ROOT = "/Users/liuwei/content-factory"
PLATFORMS = ["toutiao", "gongzhonghao", "zhihu"]

def count_words(text: str) -> int:
    """Count Chinese characters + words in a text."""
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english_words

def parse_frontmatter(content: str) -> dict:
    """Extract frontmatter from markdown."""
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
            result[key.strip()] = val.strip()
    return result

def scan_date(target_date: str) -> dict:
    """Scan all platform dirs for a given date. Returns stats dict."""
    stats = {
        "date": target_date,
        "total_articles": 0,
        "total_words": 0,
        "platforms": defaultdict(lambda: {"count": 0, "words": 0, "articles": []}),
    }
    
    for platform in PLATFORMS:
        plat_dir = os.path.join(CONTENT_ROOT, platform)
        if not os.path.isdir(plat_dir):
            continue
        
        for fname in sorted(os.listdir(plat_dir)):
            if not fname.startswith(target_date) or not fname.endswith(".md"):
                continue
            
            fpath = os.path.join(plat_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            
            fm = parse_frontmatter(content)
            word_count = count_words(content)
            title = ""
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            
            stats["total_articles"] += 1
            stats["total_words"] += word_count
            stats["platforms"][platform]["count"] += 1
            stats["platforms"][platform]["words"] += word_count
            stats["platforms"][platform]["articles"].append({
                "file": fname,
                "title": title,
                "words": word_count,
                "topic": fm.get("topic", "unknown"),
                "session": fm.get("session", "unknown"),
            })
    
    return stats

def scan_week(target_date_str: str) -> dict:
    """Scan last 7 days."""
    today = datetime.strptime(target_date_str, "%Y-%m-%d")
    weekly = {"total_articles": 0, "total_words": 0, "days": {}}
    
    for i in range(7):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_stats = scan_date(day_str)
        if day_stats["total_articles"] > 0:
            weekly["days"][day_str] = day_stats
            weekly["total_articles"] += day_stats["total_articles"]
            weekly["total_words"] += day_stats["total_words"]
    
    return weekly

def build_summary(target_date: str) -> str:
    """Build human-readable summary for stdout (WeChat delivery)."""
    today_stats = scan_date(target_date)
    weekly_stats = scan_week(target_date)
    
    lines = []
    lines.append(f"📊 内容工厂日报 {target_date}")
    lines.append("")
    
    if today_stats["total_articles"] == 0:
        lines.append("⚠️ 今日无产出（cron 任务可能未执行或搜索被拦截）")
        return "\n".join(lines)
    
    lines.append(f"今日产出: {today_stats['total_articles']} 篇, 共 {today_stats['total_words']:,} 字")
    lines.append("")
    
    plat_names = {"toutiao": "头条/百家号", "gongzhonghao": "公众号", "zhihu": "知乎"}
    for plat in PLATFORMS:
        p = today_stats["platforms"].get(plat, {})
        if not p.get("articles"):
            continue
        lines.append(f"### {plat_names.get(plat, plat)} ({p['count']}篇, {p['words']:,}字)")
        for art in p["articles"]:
            session_emoji = "☀️" if art["session"] == "morning" else "🌤"
            lines.append(f"  {session_emoji} {art['title'][:60]}")
        lines.append("")
    
    # Weekly stats
    lines.append(f"本周累计: {weekly_stats['total_articles']} 篇, {weekly_stats['total_words']:,} 字")
    
    # Reminder
    lines.append("")
    lines.append("💡 提醒: 打开对应平台，复制粘贴发布。")
    
    return "\n".join(lines)

def build_markdown_index(target_date: str) -> str:
    """Build markdown index file for archive."""
    weekly_stats = scan_week(target_date)
    
    lines = []
    lines.append(f"# 内容工厂产出索引")
    lines.append(f"")
    lines.append(f"更新: {target_date} | 自动生成")
    lines.append("")
    lines.append(f"## 本周统计 ({target_date})")
    lines.append("")
    lines.append(f"| 日期 | 头条 | 公众号 | 知乎 | 总篇数 | 总字数 |")
    lines.append(f"|------|------|--------|------|--------|--------|")
    
    for day_str in sorted(weekly_stats["days"].keys(), reverse=True):
        ds = weekly_stats["days"][day_str]
        t = ds["platforms"].get("toutiao", {}).get("count", 0)
        g = ds["platforms"].get("gongzhonghao", {}).get("count", 0)
        z = ds["platforms"].get("zhihu", {}).get("count", 0)
        lines.append(f"| {day_str} | {t} | {g} | {z} | {ds['total_articles']} | {ds['total_words']:,} |")
    
    lines.append(f"| **合计** | | | | **{weekly_stats['total_articles']}** | **{weekly_stats['total_words']:,}** |")
    
    return "\n".join(lines)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Write index file
    index_md = build_markdown_index(today)
    index_path = os.path.join(CONTENT_ROOT, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_md)
    
    # Print summary for cron stdout delivery
    summary = build_summary(today)
    print(summary)

if __name__ == "__main__":
    main()
