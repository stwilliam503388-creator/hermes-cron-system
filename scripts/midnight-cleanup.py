#!/usr/bin/env python3
"""
凌晨整理脚本 v3
P3: 目录平铺超过20文件自动建子目录（按首字母）
P4: 归档索引页升级为 MOC Dashboard（分类计数+最新更新）
P6: 自动生成标签索引 标签索引.md
"""

import os
import re
import json
import sys
from datetime import datetime
from pathlib import Path

VAULT = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
)

CONFIG_PATH = "/Users/liuwei/.hermes/obsidian-categories.json"

# 默认配置
DEFAULT_CONFIG = {
    "skip_keywords": [],
    "max_files_per_dir": 20,
    "categories": [
        {"dir": "工具笔记", "keywords": ["工具", "安装", "配置", "CLI", "桌面应用", "AI编码", "macOS", "brew", "npm", "pip"]},
        {"dir": "学习笔记", "keywords": ["教程", "学习", "概念", "原理", "算法", "编程", "面试"]},
        {"dir": "资讯",     "keywords": ["GitHub", "开源", "趋势", "资讯", "项目"]},
        {"dir": "工作流",   "keywords": ["工作流", "自动化", "对接", "环境", "知识管理", "Obsidian"]},
    ]
}

FILENAME_SAFE = re.compile(r'[^\u4e00-\u9fff\w\-]+')


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                elif isinstance(data, list):
                    return {**DEFAULT_CONFIG, "categories": data}
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULT_CONFIG)


def get_today_path(target_date=None) -> Path:
    if target_date:
        today = target_date
    else:
        today = datetime.now().strftime("%Y-%m-%d")
    return Path(VAULT) / "对话归档" / f"{today}.md"


def parse_entries(content: str) -> list[dict]:
    blocks = re.split(r"\n---\n", content)
    entries = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("# ") and not block.startswith("##"):
            continue

        title_match = re.search(r"^##\s*(🟢|🟡)\s+(\d{2}:\d{2})\s+(.+?)$", block, re.MULTILINE)
        if not title_match:
            continue

        level = title_match.group(1)
        time_str = title_match.group(2)
        title = title_match.group(3).strip()

        tag_match = re.search(r'\*{2}标签:\*{2}\s+([^\n]+)', block)
        tags = []
        if tag_match:
            tags = re.findall(r'`#([^`]+)`', tag_match.group(1))

        sections = {}
        for m in re.finditer(r"^(?:###|##)\s+(.+?)$\n(.*?)(?=^(?:###|##)\s|\Z)", block, re.MULTILINE | re.DOTALL):
            sec_name = m.group(1).strip()
            # 跳过条目标题行 `## 🟢/🟡 HH:MM Title` 和非目标章节
            if not sec_name.startswith("🟢") and not sec_name.startswith("🟡"):
                sections[sec_name] = m.group(2).strip()

        entries.append({
            "level": level, "time": time_str, "title": title,
            "tags": tags, "sections": sections, "raw": block,
        })
    return entries


def should_skip(title: str, tags: list[str], config: dict) -> bool:
    """P7: 检查是否应该跳过此条目"""
    skip_kw = config.get("skip_keywords", [])
    combined = title + " " + " ".join(tags)
    for kw in skip_kw:
        if kw in combined:
            return True
    return False


def categorize(tags: list[str], title: str, config: dict) -> str:
    cats = config.get("categories", [])
    all_text = " ".join(tags + [title])
    for cat in cats:
        for kw in cat["keywords"]:
            if kw in all_text:
                return cat["dir"]
    return "对话归档"


def sanitize_filename(title: str) -> str:
    name = FILENAME_SAFE.sub("-", title.strip())
    name = re.sub(r'-+', '-', name).strip('-')
    return (name[:60]) or "未命名"


def get_target_filepath(target_dir: Path, fname: str, config: dict) -> Path:
    """P3: 目录文件数超过阈值时，自动按首字母建子目录"""
    existing = list(target_dir.glob("*.md"))
    # 排除已有的子目录
    subdirs = [d for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

    max_files = config.get("max_files_per_dir", 20)
    flat_files = [f for f in existing if f.parent == target_dir]

    if len(flat_files) >= max_files:
        # 按首字母分到子目录
        first_char = fname[0].upper() if fname and fname[0].isascii() else "其他"
        sub_dir = target_dir / first_char
        sub_dir.mkdir(parents=True, exist_ok=True)
        return sub_dir / f"{fname}.md"
    return target_dir / f"{fname}.md"


def find_existing_note(target_dir: Path, title: str):
    safe = sanitize_filename(title)
    exact = target_dir / f"{safe}.md"
    if exact.exists():
        return exact
    # 递归搜索子目录
    for f in target_dir.rglob("*.md"):
        f_stem = f.stem.lower()
        title_kw = set(re.findall(r'[\u4e00-\u9fff\w]+', title.lower()))
        f_kw = set(re.findall(r'[\u4e00-\u9fff\w]+', f_stem))
        overlap = title_kw & f_kw
        if len(overlap) >= max(2, min(len(title_kw), len(f_kw)) // 2):
            return f
    return None


def merge_into_existing(existing_path: Path, entry: dict, date_str: str):
    with open(existing_path, "r", encoding="utf-8") as f:
        content = f.read()
    link_line = f"- {date_str} {entry['time']} — {entry['title']}"
    if "## 相关会话" in content:
        if link_line not in content:
            content += f"\n{link_line}\n"
    else:
        content += f"\n---\n## 相关会话\n\n{link_line}\n"
    with open(existing_path, "w", encoding="utf-8") as f:
        f.write(content)


def write_individual_note(filepath: Path, entry: dict, date_str: str):
    note_lines = [
        f"# {entry['title']}",
        "",
        f"> 归档于 {date_str} {entry['time']} | 标签: {' '.join(f'#{t}' for t in entry['tags'])}",
        "",
    ]
    for sec in ["简介", "操作摘要", "知识点", "相关链接"]:
        body = entry["sections"].get(sec, "")
        if body:
            note_lines.append(f"## {sec}")
            note_lines.append("")
            note_lines.append(body)
            note_lines.append("")
    note_lines.append("---")
    note_lines.append(f"来源: [[{date_str}]]")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(note_lines))


def build_moc_dashboard(entries: list[dict], date_str: str, config: dict) -> str:
    """P4: MOC Dashboard 风格的索引页"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# {date_str} 对话归档", ""]

    # 统计
    total = len(entries)
    green = sum(1 for e in entries if e["level"] == "🟢")
    yellow = sum(1 for e in entries if e["level"] == "🟡")
    lines.append(f"> 共 {total} 条 · 🟢 {green} 条完整 · 🟡 {yellow} 条简记 · 自动整理于 {now}")
    lines.append("")

    # 按分类汇总
    cat_map = {}
    for e in entries:
        # 扫描条目用预存分类，避免无标签导致重算回落"对话归档"
        if e.get("_from_scan") and e.get("_category"):
            c = e["_category"]
        else:
            c = categorize(e["tags"], e["title"], config)
        cat_map.setdefault(c, []).append(e)

    for cat, items in cat_map.items():
        lines.append(f"## 📂 {cat}")
        for e in items:
            fname = sanitize_filename(e["title"])
            lines.append(f"- {e['time']} — [[{cat}/{fname}|{e['title']}]]  {e['level']}")
        lines.append("")

    lines.append("---")
    lines.append(f"_自动整理于 {now}_")
    return "\n".join(lines)


def build_tag_index(entries: list[dict], date_str: str) -> str:
    """P6: 生成标签索引"""
    tag_map = {}
    for e in entries:
        for t in e["tags"]:
            tag_map.setdefault(t, []).append(e["title"])

    lines = [f"# 标签索引 ({date_str})", ""]
    if not tag_map:
        lines.append("（本日无标签）")
        return "\n".join(lines)

    for tag in sorted(tag_map.keys()):
        linked_entries = tag_map[tag]
        lines.append(f"- **#{tag}** — {len(linked_entries)} 条")
        for et in linked_entries:
            lines.append(f"  - {et}")
        lines.append("")

    lines.append("---")
    lines.append(f"_自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    return "\n".join(lines)


def find_notes_by_date(date_str: str) -> list[dict]:
    """扫描所有分类目录，找到引用指定日期的个体笔记（来源: [[date]]），
    反向重建 Dashboard 条目，实现幂等增量。"""
    entries = []
    vault = Path(VAULT)
    # 需要跳过的文件名模式
    skip_patterns = [
        re.compile(r"^\d{4}-\d{2}-\d{2}\.md$"),  # 日期 Dashboard
        re.compile(r"^对话归档-索引\.md$"),        # 归档索引
        re.compile(r"^标签索引-\d{4}-\d{2}-\d{2}\.md$"),  # 标签索引
    ]

    for md_file in vault.rglob("*.md"):
        parts = md_file.relative_to(vault).parts
        # 跳过隐藏目录
        if any(p.startswith(".") for p in parts):
            continue
        # 跳过 _ 开头的文件（如 _同步状态.md）
        if md_file.name.startswith("_"):
            continue
        # 跳过索引/日期 Dashboard 文件
        if any(pat.match(md_file.name) for pat in skip_patterns):
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # 检查是否引用指定日期
        if f"[[{date_str}]]" not in text:
            continue

        # 提取标题（第一行 # Title）
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if not title_match:
            continue
        title = title_match.group(1).strip()

        # 提取时间（归档于 YYYY-MM-DD HH:MM）
        time_str = "00:00"
        time_match = re.search(r"归档于\s+\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2})", text)
        if time_match:
            time_str = time_match.group(1)

        # 提取分类（从路径推断）
        config = load_config()
        cat = categorize([], title, config)
        if cat == "对话归档":
            cat = parts[0] if parts else "对话归档"

        entries.append({
            "level": "🟢",
            "time": time_str,
            "title": title,
            "tags": [],
            "sections": {},
            "raw": "",
            "_from_scan": True,
            "_category": cat,  # 预存分类，避免 Dashboard 重算
        })

    return entries


def merge_entries(raw_entries: list[dict], scanned: list[dict]) -> list[dict]:
    """合并原始条目和扫描条目，去重（标题匹配）。"""
    seen = set()
    merged = []

    # 先放原始条目（更新鲜的数据）
    for e in raw_entries:
        merged.append(e)
        seen.add(e["title"])

    # 再放扫描条目（跳过已有的）
    for e in scanned:
        if e["title"] not in seen:
            merged.append(e)
            seen.add(e["title"])

    # 按时间排序
    merged.sort(key=lambda e: e["time"])
    return merged


def update_main_index(date_str: str, entry_count: int, titles: list[str]):
    index_path = Path(VAULT) / "对话归档-索引.md"
    if not index_path.exists():
        return

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 去重检测
    existing_dates = set()
    for m in re.finditer(r"^\|\s*\[\[(\d{4}-\d{2}-\d{2})\]\]", content, re.MULTILINE):
        existing_dates.add(m.group(1))
    if date_str in existing_dates:
        return

    summary = f"| [[{date_str}]] | {entry_count} | {'; '.join(titles[:3])}{'...' if len(titles) > 3 else ''} |"
    lines = content.split("\n")
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if line.strip().startswith("|---") and not inserted:
            new_lines.append(summary)
            inserted = True
    if not inserted:
        new_lines.extend(["", summary])

    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="目标日期 YYYY-MM-DD，默认今天")
    args = parser.parse_args()

    config = load_config()
    today_path = get_today_path(args.date)
    if not today_path.exists():
        print(f"今日归档文件不存在: {today_path}")
        return

    date_str = today_path.stem

    with open(today_path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = parse_entries(content)

    # P8: 幂等增量——从个体笔记反向扫描已处理条目，合并后避免覆盖
    scanned = find_notes_by_date(date_str)
    all_entries = merge_entries(entries, scanned)
    if len(scanned) > 0 and len(entries) == 0:
        print(f"无可处理的新条目，但发现 {len(scanned)} 条已归档笔记，从个体笔记重建 Dashboard...")
        # 无需拆分新条目，直接用合并结果构建 Dashboard
        moc = build_moc_dashboard(all_entries, date_str, config)
        with open(today_path, "w", encoding="utf-8") as f:
            f.write(moc)
        print(f"  ✓ {today_path.name} → MOC Dashboard（从 {len(scanned)} 条个体笔记重建）")
        return
    elif len(scanned) > 0:
        print(f"发现 {len(scanned)} 条已归档笔记将合并到 Dashboard")

    # 只处理真正的原始新条目（_from_scan 标记的跳过拆分）
    new_entries = [e for e in entries if not e.get("_from_scan")]

    # P7: 过滤跳过的条目（仅对新条目）
    before = len(new_entries)
    new_entries = [e for e in new_entries if not should_skip(e["title"], e["tags"], config)]
    skipped = before - len(new_entries)
    if skipped:
        print(f"跳过 {skipped} 个条目（匹配 skip_keywords）")

    # 如果没有新条目，但已扫描到旧条目，重建 Dashboard
    if not new_entries:
        if len(all_entries) > 0:
            moc = build_moc_dashboard(all_entries, date_str, config)
            with open(today_path, "w", encoding="utf-8") as f:
                f.write(moc)
            print(f"  ✓ {today_path.name} → MOC Dashboard（{len(all_entries)} 条）")
        else:
            print("无可处理的条目")
        return

    print(f"处理 {len(new_entries)} 个新条目 + {len(all_entries) - len(new_entries)} 个已有条目...")

    all_tags = set()
    for entry in new_entries:
        cat = categorize(entry["tags"], entry["title"], config)
        target_dir = Path(VAULT) / cat
        target_dir.mkdir(parents=True, exist_ok=True)

        fname = sanitize_filename(entry["title"])

        # P3: 目录分片
        filepath = get_target_filepath(target_dir, fname, config)

        # P2: 已有笔记检测
        existing = find_existing_note(target_dir, entry["title"])
        if existing and existing.name != filepath.name:
            merge_into_existing(existing, entry, date_str)
            rel = str(existing.relative_to(Path(VAULT)))
            print(f"  ~ 合并至 {rel}")
        elif existing:
            merge_into_existing(existing, entry, date_str)
            print(f"  ~ 追加已有 {existing.name}")
        else:
            write_individual_note(filepath, entry, date_str)
            rel = str(filepath.relative_to(Path(VAULT)))
            print(f"  ✓ {rel}")

        all_tags.update(entry["tags"])

    # P4: MOC 索引页（使用合并后的全量条目）
    moc = build_moc_dashboard(all_entries, date_str, config)
    with open(today_path, "w", encoding="utf-8") as f:
        f.write(moc)
    print(f"  ✓ {today_path.name} → MOC Dashboard")

    # P6: 标签索引
    # 收集所有条目的标签
    for e in all_entries:
        all_tags.update(e["tags"])
    if all_tags:
        tag_content = build_tag_index(all_entries, date_str)
        tag_path = Path(VAULT) / "对话归档" / f"标签索引-{date_str}.md"
        with open(tag_path, "w", encoding="utf-8") as f:
            f.write(tag_content)
        print(f"  ✓ 标签索引-{date_str}.md ({len(all_tags)} 个标签)")

    update_main_index(date_str, len(all_entries), [e["title"] for e in all_entries])
    print(f"  ✓ 对话归档-索引.md 已更新")

    print(f"\n整理完成！{len(new_entries)} 个新条目已拆分，Dashboard 共 {len(all_entries)} 条。")


if __name__ == "__main__":
    main()
