#!/usr/bin/env python3
"""
Revenue Dashboard — combined weekly report for Content Factory + Xianyu Arbitrage.
Runs Sunday 22:00. Generates a summary of both monetization pipelines.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts dir to path so we can import from sibling scripts
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

def get_week_dates() -> list:
    """Return list of 7 date strings (YYYY-MM-DD), Mon-Sun."""
    today = datetime.now()
    # Find this Monday
    monday = today - timedelta(days=today.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

def scan_content_factory():
    """Count files in content-factory for this week."""
    content_root = "/Users/liuwei/content-factory"
    week_dates = get_week_dates()
    platforms = ["toutiao", "gongzhonghao", "zhihu"]
    
    total = 0
    plat_counts = {"toutiao": 0, "gongzhonghao": 0, "zhihu": 0}
    
    for plat in platforms:
        plat_dir = os.path.join(content_root, plat)
        if not os.path.isdir(plat_dir):
            continue
        for fname in os.listdir(plat_dir):
            for d in week_dates:
                if fname.startswith(d):
                    plat_counts[plat] += 1
                    total += 1
                    break
    
    return {"total": total, "platforms": plat_counts}

def scan_xianyu():
    """Count Xianyu listings for this week."""
    listings_dir = "/Users/liuwei/xianyu-arbitrage/listings"
    week_dates = get_week_dates()
    
    count = 0
    if os.path.isdir(listings_dir):
        for fname in os.listdir(listings_dir):
            for d in week_dates:
                if fname.startswith(d):
                    count += 1
                    break
    
    return count

def estimate_revenue(content_count: int, xianyu_count: int) -> dict:
    """Conservative revenue estimates."""
    # Content: assume 1000 reads/article/day, ¥2 CPM on average platform
    # One article might earn ¥2/day, 21 articles/week -> ¥42/week
    content_weekly = content_count * 2  # ¥2 per article per day estimate
    
    # Xianyu: assume 30% of listings get at least 1 sale/day, avg profit ¥10/order
    xianyu_weekly = xianyu_count * 0.3 * 10 * 7  # ¥21 per listing per week
    
    return {
        "content_weekly": content_weekly,
        "xianyu_weekly": xianyu_weekly,
        "total_weekly": content_weekly + xianyu_weekly,
        "total_monthly": (content_weekly + xianyu_weekly) * 4,
    }

def main():
    week_dates = get_week_dates()
    week_start = week_dates[0]
    week_end = week_dates[-1]
    
    cf = scan_content_factory()
    xy = scan_xianyu()
    est = estimate_revenue(cf["total"], xy)
    
    lines = []
    lines.append(f"💰 变现管道周报 | {week_start} ~ {week_end}")
    lines.append("=" * 40)
    lines.append("")
    
    lines.append("## 📝 内容工厂")
    lines.append(f"本周产出: {cf['total']} 篇文章")
    lines.append(f"  头条/百家号: {cf['platforms']['toutiao']} 篇")
    lines.append(f"  公众号: {cf['platforms']['gongzhonghao']} 篇")
    lines.append(f"  知乎: {cf['platforms']['zhihu']} 篇")
    lines.append(f"预估周收入: ¥{est['content_weekly']:.0f}")
    lines.append("")
    
    lines.append("## 🛒 闲鱼选品")
    lines.append(f"本周推荐: {xy} 个选品")
    lines.append(f"预估周收入: ¥{est['xianyu_weekly']:.0f}")
    lines.append("")
    
    lines.append("## 📊 汇总")
    lines.append(f"预估周收入: ¥{est['total_weekly']:.0f}")
    lines.append(f"预估月收入: ¥{est['total_monthly']:.0f}")
    gap = 5000 - est["total_monthly"]
    status = "✅ 达标" if est["total_monthly"] >= 5000 else f"还差 ¥{gap:.0f}"
    lines.append(f"距目标 (¥5,000): {status}")
    
    # Recommendations
    lines.append("")
    lines.append("## 💡 优化建议")
    if cf["total"] < 14:
        lines.append("  ⚠️ 内容产出低于预期（应 ≥14 篇/周），检查 cron 任务是否正常执行")
    if xy < 7:
        lines.append("  ⚠️ 选品推荐偏少（应 ≥1 个/天），可能搜索被 CAPTCHA 拦截")
    if est["total_weekly"] < 1000:
        lines.append("  📌 当前量级不够，建议增加内容分发平台（多注册一个号）")
    
    print("\n".join(lines))
    
    # Also write to file
    report_path = "/Users/liuwei/revenue-dashboard-weekly.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
