#!/usr/bin/env python3
"""
vault_news_index_update.py — 动态重建 📰 资讯索引

功能：
  1. 扫描 资讯/ 下各子目录（GitHub日报、AI面试日报、AI Agent日报、豆瓣每日一书）
  2. 自动生成文件列表、更新计数
  3. 保留手动编写的「🧠 知识延伸」区域
  4. 更新总计数和最后更新时间

用法: python3 vault_news_index_update.py [--dry-run]
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

HOME = "/Users/liuwei"
VAULT = Path(
    os.environ.get(
        "OBSIDIAN_VAULT_PATH",
        f"{HOME}/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault",
    )
)
INDEX_FILE = VAULT / "资讯" / "📰资讯索引.md"
DRY_RUN = "--dry-run" in sys.argv


def log(msg):
    print(f"  {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")


def get_date_from_filename(name: str) -> str:
    """从文件名提取日期"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""


def scan_subdir(subdir: str) -> list[tuple[str, str, Path]]:
    """扫描子目录，返回 [(sort_key, display_name, filepath)]"""
    results = []
    dirpath = VAULT / subdir
    if not dirpath.exists():
        warn(f"目录不存在: {dirpath}")
        return results
    for f in sorted(dirpath.glob("*.md")):
        name = f.stem
        if name.endswith("索引"):
            continue
        date = get_date_from_filename(name)
        sort_key = date or name
        results.append((sort_key, name, f))
    results.sort(key=lambda x: x[0])
    return results


def extract_knowledge_extension(content: str) -> str:
    """从现有索引中提取🧠知识延伸区域"""
    # 查找 ## 🧠 知识延伸 到文件末尾或 ---
    m = re.search(r"(## 🧠 知识延伸[\s\S]*?)(?=\n---|\n$|$)", content)
    if m:
        return m.group(1).strip()
    return ""


def build_header(total_count: int, now: str) -> str:
    return "\n".join([
        "# 📰 资讯索引",
        "",
        "> 每日 GitHub 趋势日报、AI 面试问答、豆瓣每日一书、专题资讯。由系统自动更新。",
        "",
        "---",
        "",
    ])


def build_subsection(title: str, subdir: str, emoji: str) -> tuple[str, int]:
    """构建单个子区域的 markdown"""
    files = scan_subdir(subdir)
    lines = [f"## {emoji} {title}", ""]
    if not files:
        lines.append("（暂无内容）")
        lines.append("")
        return "\n".join(lines), 0

    count = len(files)
    lines.append(f"共 {count} 篇：")
    lines.append("")

    for sort_key, name, fpath in files:
        date = get_date_from_filename(name)
        # 对于有日期的文件，生成简洁链接
        if date:
            # 去掉日期前缀用于显示
            display = name
            lines.append(f"- [[{subdir}/{name}|{name}]]")
        else:
            lines.append(f"- [[{subdir}/{name}]]")

    lines.append("")
    return "\n".join(lines), count


def build_news_index(existing_content: str) -> str:
    """生成完整资讯索引"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 提取手工区域
    knowledge_ext = extract_knowledge_extension(existing_content)
    has_ke = bool(knowledge_ext)

    # 定义子区域
    sections = [
        ("🌟", "GitHub 趋势日报", "资讯/GitHub日报"),
        ("🤖", "AI 面试日报", "资讯/AI面试日报"),
        ("🤖", "AI Agent 日报", "资讯/AI Agent日报"),
        ("📚", "豆瓣每日一书", "资讯/豆瓣每日一书"),
    ]

    # 构建内容
    parts = [build_header(0, now)]

    total_count = 0
    for emoji, title, subdir in sections:
        section_text, count = build_subsection(title, subdir, emoji)
        parts.append(section_text)
        total_count += count

    # 专题资讯 - 扫描根目录
    parts.append("## 📖 专题资讯")
    parts.append("")
    root_files = scan_subdir("资讯")
    # 跳过索引文件
    root_files = [(k, n, f) for k, n, f in root_files if "📰资讯索引" not in n]
    if root_files:
        parts.append("| 笔记 | 日期 |")
        parts.append("|------|------|")
        for sort_key, name, fpath in root_files:
            date = get_date_from_filename(name)
            parts.append(f"| [[{name}]] | {date if date else '-'} |")
        total_count += len(root_files)
    parts.append("")

    # 知识延伸（手工区域）
    if has_ke:
        # 过滤掉已有内容中的其他部分，只取知识延伸前
        if knowledge_ext:
            parts.append(knowledge_ext)
            parts.append("")

    # Footer
    parts.append("---")
    parts.append("")
    parts.append(f"> 总计 {total_count} 篇 | 自动更新: {now} | [[🏠 知识库总索引]] 返回总目录")
    parts.append("")

    return "\n".join(parts)


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"  资讯索引自动更新 — {ts}")
    if DRY_RUN:
        print(f"  ⚠️  干运行模式")
    print(f"{'=' * 50}")

    # 读取现有索引
    existing_content = ""
    if INDEX_FILE.exists():
        existing_content = INDEX_FILE.read_text(encoding="utf-8")
        log(f"读取现有索引: {INDEX_FILE}")

    # 生成新索引
    new_content = build_news_index(existing_content)

    # 统计信息
    total_match = re.search(r"> 总计 (\d+) 篇", new_content)
    if total_match:
        log(f"新索引总计: {total_match.group(1)} 篇")
    log(f"新索引大小: {len(new_content)} 字符")

    if DRY_RUN:
        ok("干运行完成，未写入文件")
        # 显示摘要
        for line in new_content.split("\n"):
            if line.startswith("##") and not line.startswith("## 🧠"):
                print(f"    {line}")
            if "总计" in line and "篇" in line:
                print(f"    {line.strip()}")
        return

    # 写入
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(new_content, encoding="utf-8")
    ok(f"资讯索引已更新: {INDEX_FILE}")
    log(f"  大小: {len(new_content)} 字符")
    if total_match:
        log(f"  总条目数: {total_match.group(1)} 篇")


if __name__ == "__main__":
    main()
