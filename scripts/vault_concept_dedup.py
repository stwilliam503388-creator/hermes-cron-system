#!/usr/bin/env python3
"""
vault_concept_dedup.py — 概念同义去重与合并 (v2)
===============================================
扫描 概念/ 目录，检测潜在重复概念卡片并自动合并高置信度重复。

v2 升级：
- 置信度 ≥0.8 的重复自动合并到保留方
- 0.4~0.8 的报告提示人工确认
- 合并时自动聚合所有知识内容和引用链接

用法：
  python3 vault_concept_dedup.py                        # 完整扫描+自动合并
  python3 vault_concept_dedup.py --dry-run              # 只报告，不操作
  python3 vault_concept_dedup.py --threshold 0.5        # 自定义阈值
  python3 vault_concept_dedup.py --auto-merge-threshold 0.8  # 自动合并阈值
"""

import os
import re
import sys
from pathlib import Path
from collections import Counter

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
CONCEPT_DIR = Path(VAULT) / "概念"
SIMILARITY_THRESHOLD = 0.4
AUTO_MERGE_THRESHOLD = 0.8
TAG_BOILERPLATE = {"auto-extracted", "concept"}


def extract_yaml_tags(text):
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return set()
    fm = m.group(1)
    tags_match = re.search(r"tags:\s*\[([^\]]+)\]", fm)
    if tags_match:
        tags_str = tags_match.group(1)
        return {t.strip().strip("'\"") for t in tags_str.split(",") if t.strip()}
    tags_match = re.search(r"tags:\s*\n((?:\s*-\s*.+\n?)+)", fm)
    if tags_match:
        return {t.strip("- ") for t in tags_match.group(1).strip().split("\n") if t.strip()}
    return set()


def extract_title(text):
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def extract_key_phrases(text, title):
    body = text.split("---", 2)[-1] if text.count("---") >= 2 else text
    body = body[:2000]

    boilerplate = {
        "关联概念", "关联笔记", "关联工作流", "关联工具",
        "来源文章", "关联归档", "相关链接", "一句话总结",
        "🏠 知识库总索引", "🔧工具笔记索引", "GSD工作流快速参考",
        "2026年5月GitHub热点趋势", "AI Agent面试知识体系",
        "auto-extracted", "concept",
        "来源背景", "跨会话使用模式", "来源归档", "概念萃取", "对话归档",
    }

    phrases = set()
    for m in re.finditer(r"^##\s+(.+)$", body, re.MULTILINE):
        sub = m.group(1).strip()
        if len(sub) >= 4 and sub != title and sub not in boilerplate:
            phrases.add(sub)
    for m in re.finditer(r"\*\*(.+?)\*\*", body):
        bold = m.group(1).strip()
        if len(bold) >= 4 and bold != title and bold not in boilerplate:
            phrases.add(bold)
    for m in re.finditer(r"\[\[([^\]|#]+?)(?:\|[^\]]*?)?\]\]", body):
        link = m.group(1).strip()
        if len(link) >= 3 and link not in boilerplate:
            phrases.add(link)

    return phrases


def extract_body_sections(text):
    """提取正文中所有 ## 章节标题及其内容块"""
    body = text.split("---", 2)[-1] if text.count("---") >= 2 else text
    sections = {}
    current_heading = "_preamble"
    current_lines = []
    for line in body.split("\n"):
        if re.match(r"^##\s+", line):
            if current_lines:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = re.sub(r"^##\s+", "", line).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_heading] = "\n".join(current_lines).strip()
    return sections


def trigram_similarity(a, b):
    def trigrams(s):
        s = s.lower()
        return {s[i:i+3] for i in range(len(s)-2)} if len(s) >= 3 else {s}
    ta = trigrams(a)
    tb = trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def jaccard_similarity(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def auto_merge_concepts(file_a, file_b, concepts_d, dry_run=False):
    """自动合并两个概念卡片，保留较丰富的一方"""
    a_text = concepts_d[file_a]["text"]
    b_text = concepts_d[file_b]["text"]

    a_title = concepts_d[file_a]["title"]
    b_title = concepts_d[file_b]["title"]
    a_size = len(a_text)
    b_size = len(b_text)

    # 保留较大（更丰富）的一方
    if a_size >= b_size:
        keeper, deleter = file_a, file_b
        keeper_title, deleter_title = a_title, b_title
        keeper_text, deleter_text = a_text, b_text
    else:
        keeper, deleter = file_b, file_a
        keeper_title, deleter_title = b_title, a_title
        keeper_text, deleter_text = b_text, a_text

    # 合并 tags
    keeper_tags = concepts_d[keeper]["tags"] - TAG_BOILERPLATE
    deleter_tags = concepts_d[deleter]["tags"] - TAG_BOILERPLATE
    merged_tags = keeper_tags | deleter_tags

    # 合并 sections
    keeper_sections = extract_body_sections(keeper_text)
    deleter_sections = extract_body_sections(deleter_text)

    # 从保留方的 frontmatter 中提取 created 日期
    created_match = re.search(r"created:\s*(\d{4}-\d{2}-\d{2})", keeper_text)
    created_date = created_match.group(1) if created_match else "2026-01-01"

    # 从删除方的 frontmatter 提取 created 日期（选更早的）
    deleter_created = re.search(r"created:\s*(\d{4}-\d{2}-\d{2})", deleter_text)
    if deleter_created and deleter_created.group(1) < created_date:
        created_date = deleter_created.group(1)

    # 构建合并后的内容
    merged_content = f"""---
created: {created_date}
tags: [{', '.join(sorted(merged_tags))}, concept]
aliases:
  - {keeper_title}
  - {deleter_title}
---

# {keeper_title}

> 自动合并来自 `{deleter_title}` 的内容

"""

    # 合并各章节，避免重复
    all_section_keys = list(dict.fromkeys(list(keeper_sections.keys()) + list(deleter_sections.keys())))
    for sk in all_section_keys:
        if sk == "_preamble":
            continue
        k_content = keeper_sections.get(sk, "")
        d_content = deleter_sections.get(sk, "")
        if k_content and d_content and k_content != d_content:
            # 合并去重：排除已在保留方出现的行
            d_lines = d_content.split("\n")
            k_lines = k_content.split("\n")
            k_set = set(k_lines)
            new_lines = [l for l in d_lines if l.strip() not in k_set and l not in k_lines]
            if new_lines:
                merged_content += f"\n## {sk}\n\n{k_content}\n{chr(10).join(new_lines)}\n"
            else:
                merged_content += f"\n## {sk}\n\n{k_content}\n"
        elif k_content:
            merged_content += f"\n## {sk}\n\n{k_content}\n"
        elif d_content:
            merged_content += f"\n## {sk}\n\n{d_content}\n"

    # 保留来源文章（合并）
    k_sources = re.findall(r"- \[\[([^\]]+)\]\]", keeper_text)
    d_sources = re.findall(r"- \[\[([^\]]+)\]\]", deleter_text)
    all_sources = list(dict.fromkeys(k_sources + d_sources))

    if all_sources:
        merged_content += "\n## 来源文章\n\n"
        for s in all_sources:
            merged_content += f"- [[{s}]]\n"

    merged_content += "\n---\n*此卡片由 vault_concept_dedup.py 自动合并生成*"

    keeper_path = CONCEPT_DIR / keeper

    if dry_run:
        print(f"\n  [dry-run] 将合并: {deleter_title} → {keeper_title}")
        print(f"    标签合并: {len(keeper_tags)} + {len(deleter_tags)} = {len(merged_tags)}")
        print(f"    章节合并: {len(keeper_sections)} → 整合")
        print(f"    来源合并: {len(k_sources)} + {len(d_sources)} = {len(all_sources)}")
        return keeper_path, merged_content, deleter
    else:
        # 写回保留方
        keeper_path.write_text(merged_content, encoding="utf-8")
        # 删除方（重命名为 .deprecated.md 而非直接删除，以便人工确认）
        deleter_path = CONCEPT_DIR / deleter
        deprecated_path = CONCEPT_DIR / deleter.replace(".md", ".deprecated.md")
        deleter_path.rename(deprecated_path)
        print(f"\n  ✅ 合并: {deleter_title} → {keeper_title}")
        print(f"     保留: {keeper}")
        print(f"     废弃: {deprecated_path.name}")
        return keeper_path, merged_content, deleter


def detect_and_merge():
    dry_run = "--dry-run" in sys.argv
    threshold = SIMILARITY_THRESHOLD
    auto_merge_threshold = AUTO_MERGE_THRESHOLD

    for i, arg in enumerate(sys.argv):
        if arg == "--threshold" and i + 1 < len(sys.argv):
            threshold = float(sys.argv[i + 1])
        if arg == "--auto-merge-threshold" and i + 1 < len(sys.argv):
            auto_merge_threshold = float(sys.argv[i + 1])

    if not CONCEPT_DIR.exists():
        print("❌ 概念/ 目录不存在")
        return

    # 读取所有概念笔记（排除 .deprecated.md）
    concepts = []
    concept_map = {}
    for f in sorted(CONCEPT_DIR.glob("*.md")):
        if f.name.endswith(".deprecated.md"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        title = extract_title(text)
        tags = extract_yaml_tags(text)
        phrases = extract_key_phrases(text, title)
        concept = {
            "file": f.name,
            "title": title,
            "tags": tags,
            "phrases": phrases,
            "text": text,
            "size": len(text),
        }
        concepts.append(concept)
        concept_map[f.name] = concept

    if len(concepts) < 2:
        print("概念笔记少于2篇，无需去重")
        return

    # 两两比较
    pairs = []
    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            a, b = concepts[i], concepts[j]
            title_sim = trigram_similarity(a["title"], b["title"])
            meaningful_tags_a = a["tags"] - TAG_BOILERPLATE
            meaningful_tags_b = b["tags"] - TAG_BOILERPLATE
            tag_sim = jaccard_similarity(meaningful_tags_a, meaningful_tags_b)
            phrase_sim = jaccard_similarity(a["phrases"], b["phrases"])
            combined = title_sim * 0.5 + tag_sim * 0.25 + phrase_sim * 0.25

            if combined >= threshold:
                pairs.append({
                    "file_a": a["file"], "title_a": a["title"], "size_a": a["size"],
                    "file_b": b["file"], "title_b": b["title"], "size_b": b["size"],
                    "title_sim": round(title_sim, 3),
                    "tag_sim": round(tag_sim, 3),
                    "phrase_sim": round(phrase_sim, 3),
                    "combined": round(combined, 3),
                    "common_tags": a["tags"] & b["tags"],
                    "common_phrases": a["phrases"] & b["phrases"],
                })

    pairs.sort(key=lambda x: -x["combined"])

    print(f"📚 概念/ 目录: {len(concepts)} 篇活跃笔记")
    print(f"🔄 两两比较: {len(concepts) * (len(concepts) - 1) // 2} 对")
    print(f"⚙️  报告阈值: ≥{threshold} | 自动合并阈值: ≥{auto_merge_threshold}")
    print()

    if not pairs:
        print("✅ 未检测到潜在重复")
        return

    # 拆分自动合并和报告
    auto_merge_pairs = [p for p in pairs if p["combined"] >= auto_merge_threshold]
    report_pairs = [p for p in pairs if p["combined"] < auto_merge_threshold]

    # ── 自动合并 ──
    if auto_merge_pairs:
        print(f"⚡ 自动合并 ({len(auto_merge_pairs)} 对, 相似度≥{auto_merge_threshold}):")
        merged_set = set()
        for p in auto_merge_pairs:
            # 避免循环合并（A→B 后 B→C）
            if p["file_a"] in merged_set or p["file_b"] in merged_set:
                print(f"  ⏭️  跳过 (已在本次合并中): {p['title_a']} ↔ {p['title_b']}")
                continue
            keeper_path, merged_text, deleted_file = auto_merge_concepts(
                p["file_a"], p["file_b"], concept_map, dry_run=dry_run
            )
            merged_set.add(keeper_path.name)
            merged_set.add(deleted_file)

    # ── 报告潜在重复 ──
    if report_pairs:
        print(f"\n⚠️  需人工确认 ({len(report_pairs)} 对, 相似度 {threshold}~{auto_merge_threshold}):\n")
        for p in report_pairs:
            print(f"  📌 相似度 {p['combined']:.3f}")
            print(f"    A: {p['title_a']} ({p['file_a']}, {p['size_a']}B)")
            print(f"    B: {p['title_b']} ({p['file_b']}, {p['size_b']}B)")
            print(f"    标题: {p['title_sim']:.3f}  标签: {p['tag_sim']:.3f}  短语: {p['phrase_sim']:.3f}")
            if p["common_tags"]:
                print(f"    共有标签: {', '.join(sorted(p['common_tags']))}")
            if p["common_phrases"]:
                common_list = sorted(p["common_phrases"])
                print(f"    共有关键词: {', '.join(common_list[:5])}")
            print()
        print(f"💡 建议: 对相似度 ≥0.6 的配对，手动运行 `python3 vault_concept_dedup.py --auto-merge-threshold 0.6` 批量合入")

    print(f"\n{'='*50}")
    print(f"自动合并: {len(auto_merge_pairs)} 对 | 待人工确认: {len(report_pairs)} 对")


if __name__ == "__main__":
    detect_and_merge()
