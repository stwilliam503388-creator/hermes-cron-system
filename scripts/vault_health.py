#!/usr/bin/env python3
"""
知识库健康巡检 — vault_health.py
扫描 Obsidian vault 输出健康报告，检测：
- 零入链孤岛笔记
- 老化笔记（30天未改 + 入链少）
- 悬浮索引链接（MOC 指向不存在的文件）
- 主题密度分布
"""

import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
EXCLUDE_DIRS = {".obsidian", "工具笔记/skills"}
EXCLUDE_FILES = {"_同步状态", "📊 知识库健康报告"}
# Directories excluded from orphan/aging analysis but included for link resolution
LINK_RESOLVE_DIRS = {"工具笔记/skills"}
AGING_DAYS = 30
AGING_LOW_LINKS = 2  # 入链少于这个值且超期算老化
REPORT_FILE = os.path.join(VAULT, "参考", "📊 知识库健康报告.md")

NOW = datetime.now()


def is_excluded(p: Path) -> bool:
    """检查路径是否应该被排除"""
    rel = p.relative_to(VAULT).as_posix()
    if "📊 知识库健康报告" in p.name:
        return True
    return any(rel.startswith(ed) or f"/{ed}/" in rel for ed in EXCLUDE_DIRS)


def get_all_md_files():
    """获取所有 .md 文件（排除排除目录）"""
    files = []
    for f in Path(VAULT).rglob("*.md"):
        if not is_excluded(f):
            files.append(f)
    return files


def get_inbound_links(files, basename_no_ext):
    """统计某个笔记被多少其他笔记引用（[[basename]] 模式）"""
    count = 0
    referrers = []
    for f in files:
        content = f.read_text(encoding="utf-8", errors="ignore")
        # 匹配 [[文件名]] 或 [[文件名|显示文本]]
        pattern = re.escape(basename_no_ext)
        if re.search(rf'\[\[{pattern}(?:\|[^\]]*)?\]\]', content):
            count += 1
            referrers.append(f.relative_to(VAULT).as_posix())
    return count, referrers


def get_outbound_links(content):
    # 先移除代码块（```...```），再移除内联反引号（`...`），然后提取 [[link]]
    import re
    cleaned = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    cleaned = re.sub(r'`[^`]*`', '', cleaned)
    return re.findall(r'\[\[([^\]#|]+?)(?:#[^\]]*?|(?:\|[^\]]*?))?\]\]', cleaned)


def extract_tags(content):
    """提取笔记中的标签 #tag"""
    # 排除 markdown 标题中的 #
    return re.findall(r'(?<!\w)#([a-zA-Z0-9_\-\u4e00-\u9fff/]+)', content)


def scan():
    files = get_all_md_files()
    # 排除报告自身，避免健康报告内的引用干扰统计
    files = [f for f in files if f.stem not in EXCLUDE_FILES]
    file_count = len(files)
    print(f"扫描到 {file_count} 个 .md 文件")

    # Build basename -> path mapping
    basename_map = {}  # basename_no_ext -> Path
    for f in files:
        basename_map[f.stem] = f

    # Also include LINK_RESOLVE_DIRS for broken link detection
    for rd in LINK_RESOLVE_DIRS:
        link_dir = Path(VAULT) / rd
        if link_dir.exists():
            for f in link_dir.rglob("*.md"):
                basename_map[f.stem] = f

    results = []
    orphan_notes = []
    aging_notes = []
    broken_links = []
    tag_count = defaultdict(int)
    folder_dist = defaultdict(int)

    for f in files:
        rel = f.relative_to(VAULT).as_posix()
        folder = os.path.dirname(rel)
        folder_dist[folder] += 1

        stats = f.stat()
        mtime = datetime.fromtimestamp(stats.st_mtime)
        days_since_mod = (NOW - mtime).days
        size_kb = stats.st_size / 1024
        content = f.read_text(encoding="utf-8", errors="ignore")
        tags = extract_tags(content)
        for t in tags:
            tag_count[t] += 1

        # 入链统计
        in_count, referrers = get_inbound_links(files, f.stem)

        # 出链统计
        out_links = get_outbound_links(content)

        # 悬浮链接检测
        file_broken = []
        for link in out_links:
            link_name = link.strip()
            if link_name not in basename_map:
                # 检查是否指向被排除目录中的文件（skills/）
                candidate_path = Path(VAULT) / f"{link_name}.md"
                if candidate_path.exists():
                    continue  # 文件存在但被排除了，不算悬浮
                # 检查是否指向 skills/ 下的文件（常见情况）
                skills_path = Path(VAULT) / "工具笔记" / "skills" / f"{link_name}.md"
                if skills_path.exists():
                    continue
                # 跳过外部链接、图片、锚点
                if not link_name.startswith("http") and not link_name.endswith(".png") and not link_name.endswith(".jpg"):
                    file_broken.append(link_name)
        if file_broken:
            broken_links.append((rel, file_broken))

        entry = {
            "path": rel,
            "folder": folder,
            "stem": f.stem,
            "size_kb": round(size_kb, 1),
            "mtime": mtime,
            "days_since_mod": days_since_mod,
            "inbound_links": in_count,
            "referrers": referrers,
            "outbound_links": len(out_links),
            "tags": tags,
            "broken_outbound": file_broken,
        }
        results.append(entry)

        # 判定孤岛：零入链（排除索引文件自身）
        if in_count == 0 and f.stem not in ("🏠 知识库总索引",) and f.stem not in EXCLUDE_FILES:
            orphan_notes.append(entry)

        # 判定老化：超30天 + 入链<=AGING_LOW_LINKS（排除归档）
        if days_since_mod > AGING_DAYS and in_count <= AGING_LOW_LINKS and "对话归档" not in f.stem and ".obsidian" not in rel:
            aging_notes.append(entry)

    return {
        "file_count": file_count,
        "results": results,
        "orphan_notes": sorted(orphan_notes, key=lambda x: x["mtime"]),
        "aging_notes": sorted(aging_notes, key=lambda x: x["days_since_mod"], reverse=True),
        "broken_links": broken_links,
        "tag_count": dict(sorted(tag_count.items(), key=lambda x: -x[1])),
        "folder_dist": dict(sorted(folder_dist.items(), key=lambda x: -x[1])),
    }


def format_report(data):
    now_str = NOW.strftime("%Y-%m-%d %H:%M")
    lines = ["# 📊 知识库健康报告", "", f"> 生成时间: {now_str} · 共 {data['file_count']} 篇笔记", "", "---", ""]

    # 1. 主题密度分布
    lines.append("## 📂 主题密度分布")
    lines.append("")
    lines.append("| 目录 | 笔记数 |")
    lines.append("|------|-------:|")
    for d, c in data["folder_dist"].items():
        label = d if d != "." else "根目录"
        lines.append(f"| {label} | {c} |")
    lines.append("")

    # 2. 孤岛笔记
    lines.append("## 🏝️ 零入链孤岛笔记")
    lines.append("")
    orphans = data["orphan_notes"]
    if not orphans:
        lines.append("✅ 无零入链笔记 🎉")
    else:
        lines.append(f"> 共 {len(orphans)} 篇笔记没有任何其他笔记引用它们")
        lines.append("")
        for o in orphans:
            mtime_str = o["mtime"].strftime("%m-%d")
            size_str = f"{o['size_kb']}KB" if o['size_kb'] < 1000 else f"{o['size_kb']/1024:.1f}MB"
            lines.append(f"- **[[{o['stem']}]]** — `{o['path']}` · {size_str} · 最后修改 {mtime_str}")
    lines.append("")

    # 3. 老化笔记
    lines.append("## ⏰ 老化笔记")
    lines.append("")
    aging = data["aging_notes"]
    if not aging:
        lines.append("✅ 无非归档老化笔记 🎉")
    else:
        lines.append(f"> 超过 {AGING_DAYS} 天未修改且入链 ≤ {AGING_LOW_LINKS} 的笔记，共 {len(aging)} 篇")
        lines.append("")
        for a in aging[:30]:  # 最多显示30条
            lines.append(f"- **[[{a['stem']}]]** — `{a['path']}` · {a['days_since_mod']} 天未动 · 入链 {a['inbound_links']}")
    lines.append("")

    # 4. 悬浮链接
    lines.append("## 🔗 悬浮链接（指向不存在文件）")
    lines.append("")
    broken = data["broken_links"]
    if not broken:
        lines.append("✅ 无悬浮链接 🎉")
    else:
        lines.append(f"> 共 {sum(len(b[1]) for b in broken)} 条链接指向不存在的文件")
        lines.append("")
        for src, links in broken[:20]:
            links_str = ", ".join(f"`{l}`" for l in links[:5])
            if len(links) > 5:
                links_str += f" ...（共 {len(links)} 条）"
            lines.append(f"- `{src}` → {links_str}")
    lines.append("")

    # 5. 热门标签
    lines.append("## 🏷️ 标签热度")
    lines.append("")
    lines.append("| 标签 | 出现次数 |")
    lines.append("|------|--------:|")
    for tag, count in list(data["tag_count"].items())[:20]:
        lines.append(f"| #{tag} | {count} |")
    lines.append("")

    # 6. 笔记入链排行 TOP 10
    lines.append("## 🔗 入链排行 TOP 10")
    lines.append("")
    sorted_by_in = sorted(data["results"], key=lambda x: -x["inbound_links"])
    lines.append("| 笔记 | 入链数 | 出链数 | 大小 |")
    lines.append("|------|------:|------:|-----:|")
    for r in sorted_by_in[:10]:
        if r["stem"] in ("🏠 知识库总索引",):
            continue
        lines.append(f"| [[{r['stem']}]] | {r['inbound_links']} | {r['outbound_links']} | {r['size_kb']}KB |")
    lines.append("")

    lines.append("---")
    lines.append(f"_自动生成于 {now_str}_")
    return "\n".join(lines)


def write_report(report):
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已写入: {REPORT_FILE}")
    return REPORT_FILE


if __name__ == "__main__":
    import sys
    data = scan()
    report = format_report(data)
    path = write_report(report)

    # 打印摘要到 stdout
    print("\n=== 巡检摘要 ===")
    print(f"  总笔记数: {data['file_count']}")
    print(f"  孤岛笔记: {len(data['orphan_notes'])}")
    print(f"  老化笔记: {len(data['aging_notes'])}")
    print(f"  悬浮链接: {sum(len(b[1]) for b in data['broken_links'])} 条")
    print(f"  报告路径: {path}")
