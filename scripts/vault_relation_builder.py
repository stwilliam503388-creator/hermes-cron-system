#!/usr/bin/env python3
"""
vault_relation_builder.py — 概念间关联关系图谱构建器
====================================================
扫描 概念/ 目录，提取所有卡片标签/来源/名称信息，
为每张卡片推导关联概念并更新其 "关联概念" 章节。

关联维度：
1. 标签重叠 —— 共享标签越多，关联越强
2. 同源文件 —— 出现在同一批源文件中的概念
3. 名称重叠 —— 概念名互为子串
4. 共有关键词 —— 摘录中的高频词重叠

用法：
  python3 vault_relation_builder.py                            # 完整构建
  python3 vault_relation_builder.py --dry-run                  # 仅报告不写入
  python3 vault_relation_builder.py --min-tag-overlap 1        # 最低标签共享数
  python3 vault_relation_builder.py --force                    # 强制回写所有卡片
"""
import os
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
CONCEPT_DIR = Path(VAULT) / "概念"
MIN_TAG_OVERLAP = 1  # 最低共享标签数才算关联
MAX_RELATED = 6       # 每张卡最多显示几个关联
STOP_TAGS = {"concept", "auto-extracted", "对话归档", "概念萃取", "每日一书"}


def parse_yaml_meta(text: str):
    """从卡片文本提取 YAML 元数据"""
    meta = {"tags": set(), "title": "", "source_type": "", "source_files": [], "aliases": set()}

    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return meta
    yaml_block = m.group(1)

    # 标题
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if title_m:
        meta["title"] = title_m.group(1).strip()

    # 文件名首行也可能有
    if not meta["title"]:
        meta["title"] = "(未命名)"

    # 标签 — 支持 tags: [tag1, tag2] 和 tags:\n  - tag1\n  - tag2
    tags = set()
    bracket_m = re.search(r"tags:\s*\[([^\]]+)\]", yaml_block)
    if bracket_m:
        raw = bracket_m.group(1)
        tags = {t.strip().strip("'\"") for t in raw.split(",") if t.strip()}
    else:
        list_m = re.findall(r"^\s+-\s+(.+)$", yaml_block, re.MULTILINE)
        if list_m:
            tags = {t.strip().strip("'\"") for t in list_m}
    meta["tags"] = {t for t in tags if t.lower() not in STOP_TAGS}

    # 来源类型
    src_m = re.search(r"source_type:\s*(.+)", yaml_block)
    if src_m:
        meta["source_type"] = src_m.group(1).strip()

    # 来源日期
    src_dates = set()
    for line in yaml_block.split("\n"):
        if line.strip().startswith("source_dates:"):
            m2 = re.search(r"\[(.*?)\]", line)
            if m2:
                src_dates = {d.strip().strip("'\"") for d in m2.group(1).split(",") if d.strip()}
    meta["source_dates"] = src_dates

    # aliases
    alias_re = re.findall(r"aliases:\s*\n((?:\s+-\s+.+\n?)+)", yaml_block)
    if alias_re:
        for block in alias_re:
            for line in block.strip().split("\n"):
                a = line.strip().strip("- ").strip("'\"")
                if a:
                    meta["aliases"].add(a)

    return meta


def extract_keywords_from_card(text: str, title: str):
    """从卡片正文中提取关键词（用于共现匹配）"""
    # 获取 # 章节标题
    sections = re.findall(r"^##\s+(.+)$", text, re.MULTILINE)
    # 获取 [[]] 内部链接
    wikilinks = re.findall(r"\[\[(.+?)\]\]", text)
    # 获取加粗关键词
    bold_terms = re.findall(r"\*\*(.+?)\*\*", text)
    return set(sections + wikilinks + bold_terms)


def build_card_index():
    """扫描概念目录，构建 {文件名: {meta}} 索引"""
    if not CONCEPT_DIR.exists():
        print(f"❌ 概念/ 目录不存在: {CONCEPT_DIR}")
        sys.exit(1)

    index = {}
    for f in sorted(CONCEPT_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        meta = parse_yaml_meta(text)
        meta["keywords"] = extract_keywords_from_card(text, meta["title"])
        meta["filepath"] = f
        meta["stem"] = f.stem
        index[f.stem] = meta

    return index


def compute_relation_score(card_a, card_b, stem_a, stem_b):
    """
    计算两张卡之间的关联分数（多维度）
    返回 (score, reasons)
    """
    score = 0.0
    reasons = []

    # 1. 标签重叠
    shared_tags = card_a["tags"] & card_b["tags"]
    tag_overlap = len(shared_tags)
    if tag_overlap >= 1:
        score += tag_overlap * 1.5
        reasons.append(f"标签重叠(×{tag_overlap}): {', '.join(sorted(shared_tags)[:3])}")

    # 2. 来源日期重叠
    shared_dates = card_a.get("source_dates", set()) & card_b.get("source_dates", set())
    if shared_dates:
        date_score = len(shared_dates) * 1.0
        score += date_score
        reasons.append(f"同源(×{len(shared_dates)})")

    # 3. 名称重叠
    title_a = card_a.get("aliases", set()) | {stem_a, card_a["title"]}
    title_b = card_b.get("aliases", set()) | {stem_b, card_b["title"]}
    for ta in title_a:
        for tb in title_b:
            if ta != tb:
                if ta.lower() in tb.lower() or tb.lower() in ta.lower():
                    score += 0.5
                    reasons.append(f"名称关联: {ta}")
                    break

    # 4. 关键词重叠（wikilink 互引 + 章节标题匹配）
    shared_keywords = card_a["keywords"] & card_b["keywords"]
    if shared_keywords:
        keyword_score = len(shared_keywords) * 0.3
        # 降低权重避免过分膨胀
        score += min(keyword_score, 1.5)
        reasons.append(f"关键词(×{len(shared_keywords)})")

    # 5. 互引检测
    if stem_a in card_b["keywords"] or stem_b in card_a["keywords"]:
        score += 1.0
        reasons.append("互相关链")

    return round(score, 1), reasons


def build_relations(index, dry_run=False, force=False, min_score=0.5):
    """
    为每张卡生成关联概念列表，更新卡片文件。
    """
    concept_list = list(index.keys())
    print(f"📚 概念卡: {len(concept_list)} 张")
    print(f"⚖️  最低关联分: {min_score}")
    print()

    updated = 0
    skipped = 0
    total_pairs = 0

    for stem_a in concept_list:
        card_a = index[stem_a]
        filepath = card_a["filepath"]
        text = filepath.read_text(encoding="utf-8", errors="ignore")

        # 为每张卡计算与其他卡的关联分数
        relations = []
        for stem_b in concept_list:
            if stem_a == stem_b:
                continue
            card_b = index[stem_b]
            score, reasons = compute_relation_score(card_a, card_b, stem_a, stem_b)
            if score >= min_score:
                relations.append((score, stem_b, reasons))

        # 按分数排序取 TOP N
        relations.sort(key=lambda x: -x[0])
        top = relations[:MAX_RELATED]

        if not top:
            # 没有任何关联的卡，现有卡片可能是手动创建的
            continue

        # 构建关联概念章节文字
        strong = [r for r in top if r[0] >= 2.0]
        weak = [r for r in top if r[0] < 2.0]

        relation_lines = []
        if strong:
            relation_lines.append("### 强关联\n")
            for score, stem, reasons in strong:
                display_name = index[stem]["title"]
                if not display_name.strip():
                    display_name = stem
                label = reasons[0] if reasons else ""
                relation_lines.append(f"- `{display_name}` ⚡{score} — {label}")
            relation_lines.append("")

        if weak:
            relation_lines.append("### 弱关联\n")
            for score, stem, reasons in weak:
                display_name = index[stem]["title"]
                if not display_name.strip():
                    display_name = stem
                label = reasons[0] if reasons else ""
                relation_lines.append(f"- `{display_name}` 🔗{score} — {label}")
            relation_lines.append("")

        if not relation_lines:
            continue

        total_pairs += len(strong) + len(weak)

        new_relation_section = "\n".join(relation_lines)
        total_pairs += len(strong) + len(weak)

        # 替换或追加 关联概念 章节
        old_section_pattern = r"## 关联概念\n\n.*?(?=\n---|\n\*此卡片|\Z)"
        replacement = f"## 关联概念\n\n{new_relation_section}"

        if re.search(old_section_pattern, text, re.DOTALL):
            new_text = re.sub(old_section_pattern, replacement, text, count=1, flags=re.DOTALL)
        else:
            # 没有关联概念章节，在 --- 前追加
            new_text = text.rstrip()
            if new_text.endswith("---"):
                new_text = new_text[:-3].rstrip()
            new_text += f"\n\n## 关联概念\n\n{new_relation_section}\n---\n"
            # 追回结尾注释（如果有）
            if "*此卡片" in text:
                footer_m = re.search(r"(\*此卡片.*\*)$", text, re.MULTILINE)
                if footer_m:
                    new_text += f"\n{footer_m.group(1)}\n"

        if dry_run:
            print(f"  📋 [{stem_a}] 关联: {len(strong)}强 + {len(weak)}弱")
            if strong:
                for sc, sb, sr in strong:
                    print(f"       ↑ {sb} (分{sc}): {sr[0]}")
            print()
        else:
            if new_text.strip() != text.strip() or force:
                filepath.write_text(new_text, encoding="utf-8")
                updated += 1
                print(f"  ✅ [{stem_a}] 更新关联: {len(strong)}强 + {len(weak)}弱")
            else:
                skipped += 1

    print()
    if dry_run:
        print(f"📊 Dry-run: {total_pairs} 对关系, {len(concept_list)} 张卡参与")
    else:
        print(f"📊 更新: {updated} 张 | 跳过(无变化): {skipped} | 关系对: {total_pairs}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="概念间关联关系图谱构建器")
    parser.add_argument("--dry-run", action="store_true", help="仅报告不写入")
    parser.add_argument("--min-score", type=float, default=0.5, help="最低关联分数 (default: 0.5)")
    parser.add_argument("--force", action="store_true", help="强制回写所有卡片")
    args = parser.parse_args()

    print("🔗 vault_relation_builder.py — 概念间关联关系图谱")
    print()

    index = build_card_index()
    if not index:
        print("❌ 概念/ 目录为空")
        return

    # 打印标签云
    all_tags = Counter()
    for stem, meta in index.items():
        all_tags.update(meta["tags"])

    print("🏷️  标签云（按出现频次）：")
    for tag, cnt in all_tags.most_common(15):
        print(f"  • {tag} (×{cnt})")
    print()

    build_relations(index, dry_run=args.dry_run, force=args.force, min_score=args.min_score)


if __name__ == "__main__":
    main()
