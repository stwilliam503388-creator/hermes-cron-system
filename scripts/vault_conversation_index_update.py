#!/usr/bin/env python3
"""
vault_conversation_index_update.py — 动态重建 📅 对话归档索引

功能：
  1. 扫描 对话归档/ 目录下的所有日归档笔记（日期格式）
  2. 自动更新日报列表，保留手工写的要点描述
  3. 保留📌专题归档区域（手工维护）

用法: python3 vault_conversation_index_update.py [--dry-run]
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
INDEX_FILE = VAULT / "对话归档" / "📅对话归档索引.md"
DRY_RUN = "--dry-run" in sys.argv


def log(msg):
    print(f"  {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")


def get_date_from_filename(name: str) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""


def extract_summary_from_note(filepath: Path) -> str:
    """从笔记中提取简短摘要（第一段非标题内容），用于归档索引的'要点'"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                # 清理markdown符号
                text = re.sub(r'[>#*_`\[\]]', '', stripped)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 60:
                    text = text[:57] + "..."
                if text:
                    return text
    except Exception:
        pass
    return ""


def extract_topic_archive(content: str) -> str:
    """从现有索引中提取📌专题归档区域"""
    # 查找 ## 📌 专题归档 到文件末尾或 ---
    m = re.search(r"(## 📌 专题归档[\s\S]*?)(?=\n---|\n$|$)", content)
    if m:
        return m.group(1).strip()
    return ""


def scan_daily_archives(subdir: str) -> list[tuple[str, str, Path]]:
    """扫描对话归档目录，返回按日期排序的日归档列表"""
    results = []
    dirpath = VAULT / subdir
    if not dirpath.exists():
        warn(f"目录不存在: {dirpath}")
        return results
    for f in sorted(dirpath.glob("*.md")):
        name = f.stem
        # 跳过非日归档文件（如标签索引、总索引等）
        if any(skip in name for skip in ("标签索引", "对话归档索引")):
            continue
        date = get_date_from_filename(name)
        if not date:
            continue  # 跳过非日期文件（专题归档）
        results.append((date, name, f))
    results.sort(key=lambda x: x[0])
    return results


def extract_existing_summaries(content: str) -> dict[str, str]:
    """从现有索引中提取已有条目的要点描述"""
    summaries = {}
    # 查找日报table中的条目
    table_section = re.search(r"## 📆 日报\n(.*?)(?=\n##|\n---|$)", content, re.DOTALL)
    if table_section:
        table_text = table_section.group(1)
        for line in table_text.split("\n"):
            m = re.match(r"\|\s*\[\[([^\]]+)\]\]\s*\|\s*(.+?)\s*\|", line)
            if m:
                name = m.group(1).strip()
                summary = m.group(2).strip()
                if summary:
                    summaries[name] = summary
    return summaries


def build_conversation_index(existing_content: str) -> str:
    """生成完整对话归档索引"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 提取手工区域
    topic_archive = extract_topic_archive(existing_content)
    existing_summaries = extract_existing_summaries(existing_content)

    # 扫描归档
    archives = scan_daily_archives("对话归档")

    lines = [
        "# 📅 对话归档索引",
        "",
        "> 按日归档的完整 Hermes Agent 对话记录，以及专题归档。",
        "",
        "## 📆 日报",
        "",
        "| 日期 | 要点 |",
        "|------|------|",
    ]

    for date, name, fpath in archives:
        summary = existing_summaries.get(name, "")
        if not summary:
            summary = extract_summary_from_note(fpath)
        lines.append(f"| [[{name}]] | {summary} |")

    lines.append("")

    # 专题归档
    if topic_archive:
        lines.append(topic_archive)
        lines.append("")

    # Footer
    total_daily = len(archives)
    total_text = "总计"
    if topic_archive:
        # 从专题区域中计数表格行
        ta_lines = topic_archive.split("\n")
        topic_count = sum(1 for l in ta_lines if l.strip().startswith("| [[") and not "笔记" in l)
        total_text = f"总计 {total_daily + topic_count} 篇"

    lines.append("---")
    lines.append("")
    lines.append(f"> {total_text} | 自动更新: {now} | [[🏠 知识库总索引]] 返回总目录")
    lines.append("")

    return "\n".join(lines)


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"  对话归档索引自动更新 — {ts}")
    if DRY_RUN:
        print(f"  ⚠️  干运行模式")
    print(f"{'=' * 50}")

    existing_content = ""
    if INDEX_FILE.exists():
        existing_content = INDEX_FILE.read_text(encoding="utf-8")
        log(f"读取现有索引: {INDEX_FILE}")

    new_content = build_conversation_index(existing_content)

    # 统计
    daily_count = len(re.findall(r"\| \[\[", new_content.split("## 📆 日报")[1].split("##")[0] if "##" in new_content else ""))
    log(f"日归档笔记: 根据扫描统计")
    log(f"新索引大小: {len(new_content)} 字符")

    if DRY_RUN:
        ok("干运行完成，未写入文件")
        for line in new_content.split("\n"):
            if line.startswith("##"):
                print(f"    {line}")
            if "总计" in line:
                print(f"    {line.strip()}")
        return

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(new_content, encoding="utf-8")
    ok(f"对话归档索引已更新: {INDEX_FILE}")
    log(f"  大小: {len(new_content)} 字符")


if __name__ == "__main__":
    main()
