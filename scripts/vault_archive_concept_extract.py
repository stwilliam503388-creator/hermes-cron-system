#!/usr/bin/env python3
"""
vault_archive_concept_extract.py — 对话归档富概念萃取 (v2)
===========================================================
扫描 对话归档/ 中的 🟢 条目，提取跨对话的重复主题，
聚合全部知识点和简介内容，生成信息密集的概念卡片。

策略升级 (v2)：
1. 解析每条 🟢 条目 → 提取标题、标签、简介、知识点
2. 统计术语频次 + 聚合每个术语在不同条目中的全部知识点
3. 为每个概念生成综合知识段落（而非仅有来源表格）
4. 跨条目同义合并

用法：
  python3 vault_archive_concept_extract.py              # 扫描并生成
  python3 vault_archive_concept_extract.py --dry-run     # 预览
  python3 vault_archive_concept_extract.py --min-freq 2  # 调高最低频次
"""

import os
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

# 优先读取环境变量，兼容 pipeline 中 setenv.sh 加载
VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
ARCHIVE_DIR = Path(VAULT) / "对话归档"
CONCEPT_DIR = Path(VAULT) / "概念"
MIN_FREQ = 2

# ── 停用词 ──
STOP_WORDS = {
    "我们", "可以", "这个", "一个", "没有", "不是", "什么", "他们", "自己",
    "如果", "因为", "所以", "但是", "然后", "已经", "这些", "那些", "就是",
    "还是", "只是", "这样", "那样", "可能", "应该", "需要", "知道", "觉得",
    "问题", "方法", "方式", "情况", "过程", "结果", "内容", "部分", "方面",
    "一种", "一下", "一些", "一点", "很多", "非常", "比较", "直接", "通过",
    "进行", "使用", "提供", "支持", "实现", "完成", "处理", "包括", "涉及",
    "目前", "当前", "其中", "以下", "以上", "本次", "本次对话", "这次",
    "the", "and", "for", "with", "this", "that", "from", "have", "are",
    "was", "not", "but", "can", "all", "has", "been", "will", "they",
    "its", "also", "when", "which", "there", "about", "more", "other",
    "using", "used", "into", "than", "some", "each", "such", "your",
    "only", "most", "well", "just", "very", "like", "over", "out",
    "github", "https", "http", "com", "org", "api", "pdf", "ai",
    "obsidian", "hermes", "agent",
    # 对话中的日常用语 — 并非知识概念
    "一句话总结", "一句话概括", "一句话简介", "总体而言", "总的来说",
    "简单来说", "本质上来", "本质上", "从根本上", "从本质",
    "根据以上", "综上所述", "基于以上", "如上所述", "综上所述",
    "趋势日报", "今日速览", "今日热点", "周报", "月报", "年报",
    "是什么", "有什么区别", "为什么", "怎么做", "怎么用", "如何实现",
    "从零构建", "完全可以", "最后", "上次", "下次", "第一次",
    "一个方面", "另一个", "一方面", "另一方面",
    "比如说", "举个例子", "换句话说", "也就是说",
    "但实际上", "现实上", "实践上", "理论上",
}


def load_existing_concept_titles():
    """返回 {标题/文件名: 文件大小(B)} 的字典"""
    existing = {}
    if not CONCEPT_DIR.exists():
        return existing
    for f in CONCEPT_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            existing[m.group(1).strip()] = f.stat().st_size
        existing[f.stem] = existing.get(f.stem, f.stat().st_size)
    return existing


def parse_entries(filepath):
    """解析一个归档文件中的所有 🟢 条目"""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    file_date = filepath.stem.replace(".md", "")

    entries = []
    sections = re.split(r"\n(?=## 🟢\s)", text)

    for section in sections:
        m = re.match(r"## 🟢\s+(.+)$", section, re.MULTILINE)
        if not m:
            continue
        title = m.group(1).strip()

        # 标签
        tags_match = re.search(r"\*\*标签:\*\*\s*(.+)$", section, re.MULTILINE)
        tags = []
        if tags_match:
            tags_str = tags_match.group(1)
            tags = [t.strip("#` ") for t in re.findall(r"#?`?([a-zA-Z0-9_\-/\u4e00-\u9fff]+)`?", tags_str)]

        # 简介
        intro_match = re.search(r"### 简介\s*\n(.+?)(?:\n###|\Z)", section, re.DOTALL)
        intro = intro_match.group(1).strip() if intro_match else ""

        # 知识点
        knowledge_match = re.search(r"### 知识点\s*\n(.+?)(?:\n###|\Z)", section, re.DOTALL)
        knowledge = knowledge_match.group(1).strip() if knowledge_match else ""

        # 链接
        links = re.findall(r"\[\[([^\]|#]+?)(?:\|[^\]]*?)?\]\]", section)

        entries.append({
            "date": file_date,
            "title": title,
            "tags": tags,
            "intro": intro[:500],
            "knowledge": knowledge[:3000],
            "links": links,
        })

    return entries


def extract_terms(text):
    """从文本中提取候选术语"""
    terms = []
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", text):
        word = m.group(0)
        if len(word) >= 3:
            terms.append(word)
    for m in re.finditer(r"\b[A-Z][a-zA-Z0-9]+(?:[- ][A-Z][a-zA-Z0-9]+)*\b", text):
        word = m.group(0).strip()
        if len(word) >= 4 and word.lower() not in STOP_WORDS:
            terms.append(word)
    for m in re.finditer(r"\b[a-z][a-z0-9_\-]{5,}\b", text):
        word = m.group(0)
        if word.lower() not in STOP_WORDS:
            terms.append(word)
    return terms


def is_valid_term(term):
    term_lower = term.lower()
    if term_lower in STOP_WORDS or term in STOP_WORDS:
        return False
    if re.match(r"^\d+$", term):
        return False
    if re.match(r"^\d{4}-\d{2}-\d{2}", term):
        return False
    if re.match(r"^\d{2}:\d{2}", term):
        return False
    return True


def generate_rich_concept_card(term, entries_data, existing_titles):
    """
    生成包含实际聚合内容的富概念卡片。
    entries_data: 包含此术语的所有条目（含完整 intro 和 knowledge）
    """
    now = datetime.now().strftime("%Y-%m-%d")

    source_dates = sorted(set(e["date"] for e in entries_data))
    sources = ", ".join(source_dates)

    # ── 聚合知识点 ──
    all_knowledge = []
    all_intros = []
    all_tags = []
    all_links = []

    for e in entries_data:
        if e["knowledge"]:
            all_knowledge.append(e["knowledge"])
        if e["intro"]:
            all_intros.append(e["intro"])
        all_tags.extend(e["tags"])
        all_links.extend(e["links"])

    # ── 消除知识点中的重复行（去重但保留顺序） ──
    unique_knowledge_lines = []
    seen_lines = set()
    for k in all_knowledge:
        for line in k.split("\n"):
            stripped = line.strip()
            if stripped and stripped not in seen_lines:
                seen_lines.add(stripped)
                unique_knowledge_lines.append(stripped)

    # ── 聚合简介 → 一句话描述 ──
    summary_intro = all_intros[0] if all_intros else f"在 {len(source_dates)} 次对话中被反复讨论。"
    if all_intros:
        summary_intro = " | ".join(all_intros[:3])

    # ── 标签统计 ──
    tag_counter = Counter(all_tags)
    top_tags = [t for t, _ in tag_counter.most_common(8)]
    if not top_tags:
        top_tags = ["概念萃取", "对话归档"]

    # ── 关联链接 ──
    unique_links = list(dict.fromkeys(all_links))

    # ── 生成文件名 ──
    safe_name = term.replace("/", "-").replace(":", "：").replace("|", "-")

    # ── 组合知识点段落 ──
    knowledge_section = ""
    if unique_knowledge_lines:
        # 按内容类型分组：有 "https" 或 "http://" 的是资源链接
        resource_lines = [l for l in unique_knowledge_lines if "http" in l.lower() or "https" in l.lower() or "github.com" in l.lower()]
        technical_lines = [l for l in unique_knowledge_lines if l not in resource_lines and len(l) >= 10]
        # 太短或纯标点的去掉
        technical_lines = [l for l in technical_lines if len(l.strip("-*# `")) >= 8]

        if technical_lines:
            knowledge_section += "\n## 综合知识\n\n从 " + "、".join(source_dates[:5]) + " 等次对话中聚合的知识点：\n\n"
            for line in technical_lines[:15]:
                # 如果是 - 开头的项目符号保留格式
                knowledge_section += f"{line}\n"
        if resource_lines:
            knowledge_section += "\n## 资源链接\n\n"
            for line in resource_lines[:5]:
                knowledge_section += f"- {line}\n"
    else:
        knowledge_section = "\n## 综合知识\n\n_暂无自动聚合的知识点，建议手动补充。_\n"

    content = f"""---
tags: [{', '.join(top_tags)}, 概念萃取, 对话归档]
created: {now}
source: 对话归档
source_dates: [{sources}]
---

# 🏷️ {term}

> **一句话总结**：{summary_intro[:200]}（出现在 {len(source_dates)} 次对话中）

## 对话背景

该概念跨越 {len(source_dates)} 个不同日期，共 {len(entries_data)} 个 🟢 条目，以下是各次讨论的概要：

| 日期 | 条目标题 | 关键标签 |
|------|---------|---------|
"""
    for e in entries_data:
        tags_str = ", ".join(e["tags"][:3]) if e["tags"] else "—"
        content += f"| {e['date']} | {e['title']} | {tags_str} |\n"

    content += knowledge_section

    if unique_links:
        content += "\n## 相关链接\n\n"
        for link in unique_links[:8]:
            content += f"- [[{link}]]\n"

    content += "\n## 来源归档\n\n"
    for d in source_dates:
        content += f"- [[对话归档/{d}]]\n"

    content += f"""
---

*此卡片由 vault_archive_concept_extract.py v2 自动生成，知识内容从对话归档中聚合而来。建议人工审阅补充。*
"""
    return safe_name, content


def main():
    import argparse
    parser = argparse.ArgumentParser(description="从对话归档自动萃取富概念卡片")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入")
    parser.add_argument("--min-freq", type=int, default=MIN_FREQ, help="最低出现频次（按条目数）")
    parser.add_argument("--force", action="store_true", help="强制重建已有瘦卡（跳过已≥3KB的）")
    args = parser.parse_args()

    dry_run = args.dry_run
    min_freq = args.min_freq
    force_regen = args.force

    if not ARCHIVE_DIR.exists():
        print(f"❌ 对话归档/ 目录不存在: {ARCHIVE_DIR}")
        return

    # 1. 解析所有 🟢 条目
    all_entries = []
    archive_files = sorted(ARCHIVE_DIR.glob("*.md"))
    print(f"📂 扫描对话归档: {len(archive_files)} 个文件")

    for f in archive_files:
        entries = parse_entries(f)
        all_entries.extend(entries)

    print(f"📝 解析到 🟢 条目: {len(all_entries)} 条\n")

    if len(all_entries) < 2:
        print("🟢 条目少于2条，不足以萃取概念")
        return

    # 2. 提取术语并按条目归并
    term_entries = defaultdict(list)
    term_intro_knowledge = defaultdict(list)

    for entry in all_entries:
        combined = f"{entry['title']} {entry['intro']} {entry['knowledge']}"
        terms = extract_terms(combined)

        seen_in_entry = set()
        for t in terms:
            t_clean = t.strip()
            if not is_valid_term(t_clean):
                continue
            if t_clean in seen_in_entry:
                continue
            seen_in_entry.add(t_clean)
            term_entries[t_clean].append(entry)

    # 3. 过滤
    existing_titles = load_existing_concept_titles()
    candidates = []

    for term, entries in term_entries.items():
        freq = len(entries)
        distinct_dates = len(set(e["date"] for e in entries))

        if freq < min_freq:
            continue
        if distinct_dates < 2:
            continue
        if term in existing_titles:
            if force_regen and existing_titles[term] < 3000:
                pass  # 瘦卡，允许重建
            else:
                continue

        # 至少要有一些内容可聚合
        has_substance = any(e["knowledge"] or e["intro"] for e in entries)
        if not has_substance:
            continue

        candidates.append({
            "term": term,
            "freq": freq,
            "distinct_dates": distinct_dates,
            "entries": entries,
        })

    candidates.sort(key=lambda x: (-x["freq"], -x["distinct_dates"]))

    print(f"🎯 候选概念: {len(candidates)} 个 (频次≥{min_freq}, 跨日≥2)\n")

    if not candidates:
        print("没有发现可萃取的新概念")
        return

    # 4. 显示候选
    print(f"{'术语':<30} {'频次':<6} {'跨日':<6}  {'知识点行数':<10}")
    print("-" * 54)
    for c in candidates[:20]:
        kc = sum(1 for e in c["entries"] if e["knowledge"])
        print(f"{c['term']:<30} {c['freq']:<6} {c['distinct_dates']:<6}  {kc} 条含知识点")

    print(f"\n{'... 等' if len(candidates) > 20 else ''}")

    if dry_run:
        print("\n⚠️  [Dry-run] 以下卡片将被生成:")
        for c in candidates[:10]:
            print(f"  → 概念/{c['term']}.md (频次{c['freq']}, 跨{c['distinct_dates']}日)")
        return

    # 5. 写入富概念卡片
    written = 0
    for c in candidates:
        safe_name, content = generate_rich_concept_card(
            c["term"], c["entries"], existing_titles
        )
        filepath = CONCEPT_DIR / f"{safe_name}.md"

        if filepath.exists() and not (force_regen and filepath.stat().st_size < 3000):
            print(f"[SKIP] {safe_name}.md — 已存在 (≥3KB)")
            continue

        filepath.write_text(content, encoding="utf-8")
        # 统计聚合了多少知识点
        kc_total = sum(1 for e in c["entries"] if e["knowledge"])
        ic_total = sum(1 for e in c["entries"] if e["intro"])
        print(f"[OK] 概念/{safe_name}.md — 频次{c['freq']}, 跨{c['distinct_dates']}日, "
              f"聚合{kc_total}条知识点+{ic_total}条简介")
        written += 1

    print(f"\n✅ 完成: 生成 {written} 张富概念卡片")


if __name__ == "__main__":
    main()
