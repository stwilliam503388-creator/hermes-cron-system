#!/usr/bin/env python3
"""自动同步 📅对话归档索引.md — 只添加新条目，不修改已有手动摘要"""
import re
from pathlib import Path
from datetime import datetime

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
ARCHIVE_DIR = VAULT / "对话归档"
INDEX_FILE = ARCHIVE_DIR / "📅对话归档索引.md"

DATE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
DATE_ROW_PATTERN = re.compile(r"\|\s*\[\[(\d{4}-\d{2}-\d{2})\]\]")


def extract_summary(filepath: Path) -> str:
    """从归档文件提取摘要：取第一个 🟢 或 🟡 条目标题"""
    try:
        content = filepath.read_text(encoding="utf-8")
        # 找第一个 ## 🟢 或 ## 🟡 条目
        m = re.search(r"^##\s+[🟢🟡]\s+(.+)$", content, re.MULTILINE)
        if m:
            title = m.group(1).strip()
            # 去掉时间前缀 "HH:MM "
            title = re.sub(r"^\d{1,2}:\d{2}\s+", "", title)
            # 截断过长的标题
            if len(title) > 60:
                title = title[:57] + "..."
            return title
        # Fallback: 用第一个 # heading
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()[:60]
    except Exception:
        pass
    return "待补充"


def get_existing_dates(lines: list[str]) -> set[str]:
    """从索引中提取已有日期"""
    dates = set()
    for line in lines:
        m = DATE_ROW_PATTERN.search(line)
        if m:
            dates.add(m.group(1))
    return dates


def get_existing_topics(lines: list[str]) -> set[str]:
    """从索引中提取已有专题"""
    topics = set()
    in_topic = False
    for line in lines:
        if line.startswith("## 📌"):
            in_topic = True
            continue
        if in_topic and line.startswith("## "):
            break
        if in_topic:
            m = re.search(r"\[\[([^\]]+)\]\]", line)
            if m:
                topics.add(m.group(1))
    return topics


def scan_new_files():
    """扫描新文件：返回 (new_dates, new_topics)"""
    all_dates = {}
    all_topics = {}

    for f in sorted(ARCHIVE_DIR.glob("*.md")):
        if f.name == "📅对话归档索引.md":
            continue
        m = DATE_PATTERN.match(f.name)
        if m:
            date_str = m.group(1)
            all_dates[date_str] = f
        else:
            stem = f.stem
            all_topics[stem] = f

    if not INDEX_FILE.exists():
        return all_dates, all_topics

    lines = INDEX_FILE.read_text(encoding="utf-8").split("\n")
    existing_dates = get_existing_dates(lines)
    existing_topics = get_existing_topics(lines)

    new_dates = {d: f for d, f in all_dates.items() if d not in existing_dates}
    new_topics = {t: f for t, f in all_topics.items() if t not in existing_topics}
    return new_dates, new_topics


def generate_date_rows(dates: dict[str, Path]) -> list[str]:
    """生成日期表行，按日期排序"""
    rows = []
    for date_str in sorted(dates.keys()):
        summary = extract_summary(dates[date_str])
        rows.append(f"| [[{date_str}]] | {summary} |")
    return rows


def generate_topic_rows(topics: dict[str, Path]) -> list[str]:
    """生成专题表行"""
    rows = []
    for stem in sorted(topics.keys()):
        summary = extract_summary(topics[stem])
        rows.append(f"| [[{stem}]] | {summary} |")
    return rows


def update_index(new_dates: dict, new_topics: dict) -> bool:
    """更新索引文件，只在有新内容时写入"""
    if not new_dates and not new_topics:
        return False

    if not INDEX_FILE.exists():
        content = [
            "# 📅 对话归档索引",
            "",
            "> 按日归档的完整 Hermes Agent 对话记录，以及专题归档。",
            "",
            "## 📆 日报",
            "",
            "| 日期 | 要点 |",
            "|------|------|",
            *generate_date_rows(new_dates),
            "",
            "## 📌 专题归档",
            "",
            "| 笔记 | 内容概要 |",
            "|------|----------|",
            *generate_topic_rows(new_topics),
            "",
            "---",
            "",
            f"> 总计 {len(new_dates) + len(new_topics)} 篇 | [[🏠 知识库总索引]] 返回总目录",
        ]
    else:
        lines = INDEX_FILE.read_text(encoding="utf-8").split("\n")

        # ── 插入日期行 ──
        if new_dates:
            new_rows = generate_date_rows(new_dates)
            # 找到日期表末尾（下一个 ## 或空行后的 ##）
            insert_pos = None
            in_date_section = False
            for i, line in enumerate(lines):
                if line.startswith("## 📆"):
                    in_date_section = True
                    continue
                if in_date_section:
                    if line.startswith("## "):
                        insert_pos = i
                        break
                    # 如果是日期表最后一行（后面是空行+下一个section）
                    if line.startswith("|") and i + 1 < len(lines):
                        if not lines[i + 1].strip().startswith("|"):
                            insert_pos = i + 1
                            break
            if insert_pos is None:
                # 没找到插入点，追加到文件末尾
                lines.append("")
                lines.extend(new_rows)
            else:
                for row in reversed(new_rows):
                    lines.insert(insert_pos, row)

        # ── 插入专题行 ──
        if new_topics:
            new_rows = generate_topic_rows(new_topics)
            insert_pos = None
            in_topic_section = False
            for i, line in enumerate(lines):
                if line.startswith("## 📌"):
                    in_topic_section = True
                    continue
                if in_topic_section:
                    if line.startswith("## ") or line.startswith("---"):
                        insert_pos = i
                        break
                    if line.startswith("|") and i + 1 < len(lines):
                        if not lines[i + 1].strip().startswith("|"):
                            insert_pos = i + 1
                            break
            if insert_pos is None:
                lines.append("")
                lines.extend(new_rows)
            else:
                for row in reversed(new_rows):
                    lines.insert(insert_pos, row)

        # ── 更新总计计数 ──
        total_dates = len(get_existing_dates(lines)) + len(new_dates)
        total_topics = len(get_existing_topics(lines)) + len(new_topics)
        total = total_dates + total_topics
        for i, line in enumerate(lines):
            m = re.search(r">\s*总计\s+\d+\s*篇", line)
            if m:
                lines[i] = f"> 总计 {total} 篇 | [[🏠 知识库总索引]] 返回总目录"
                break

        content = "\n".join(lines) + "\n"

    INDEX_FILE.write_text(content, encoding="utf-8")
    return True


def main():
    print("扫描对话归档...")
    new_dates, new_topics = scan_new_files()

    print(f"  新日期文件: {len(new_dates)} 个")
    if new_dates:
        for d in sorted(new_dates.keys()):
            summary = extract_summary(new_dates[d])
            print(f"    → [[{d}]]: {summary}")

    print(f"  新专题文件: {len(new_topics)} 个")
    if new_topics:
        for t in sorted(new_topics.keys()):
            summary = extract_summary(new_topics[t])
            print(f"    → [[{t}]]: {summary}")

    if update_index(new_dates, new_topics):
        print(f"\n✅ 索引已更新: {INDEX_FILE}")
    else:
        print("\n✅ 索引已是最新，无需更新")


if __name__ == "__main__":
    main()
