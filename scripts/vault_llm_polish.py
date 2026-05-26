#!/usr/bin/env python3
"""
vault_llm_polish.py — LLM 润色摘要 cron job
============================================
扫描概念目录，对 auto-extracted 的非 LLM 润色卡，
使用 hermes CLI 的 -z 模式调用 LLM 润色摘要/核心要点章节。

用法：
  python3 vault_llm_polish.py                          # 完整运行
  python3 vault_llm_polish.py --dry-run                # 预览
  python3 vault_llm_polish.py --force                  # 强制重新润色所有卡
  python3 vault_llm_polish.py --max-cards 2            # 限制润色数量（用于测试）
"""
import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
CONCEPT_DIR = Path(VAULT) / "概念"
HERMES_CLI = shutil.which("hermes") or "/Users/liuwei/.local/bin/hermes"

# 润色提示词
POLISH_PROMPT = """你是一位专业的 Obsidian 知识库编辑。请润色以下概念卡片的内容，遵循这些原则：
1. 保留所有 factual information，不编造新信息
2. 重写【核心要点】章节：用更清晰的分段表达，每个要点用一句话概括
3. 改进摘要：在开头保持一句话定义/概述
4. 保持原有的 # 标题和 ## 章节结构不变
5. 不要删除或修改关联概念/来源文章等元数据章节
6. 如果原卡片的某个章节内容太少（如 "暂无自动提取的知识要点"），添加一个 ~quote 提示"此卡片知识点较少，建议从源文档补充"
7. 返回完整的 Markdown，包含 YAML frontmatter

只返回润色后的完整卡片内容，不要添加额外说明。"""


def is_hermes_available():
    return HERMES_CLI and os.path.isfile(HERMES_CLI)


def find_cards_to_polish(force=False):
    """查找需要润色的卡片"""
    if not CONCEPT_DIR.exists():
        print(f"❌ 概念目录不存在: {CONCEPT_DIR}")
        return []

    cards = []
    for f in sorted(CONCEPT_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        frontmatter = extract_frontmatter(text)
        tags = frontmatter.get("tags", [])

        # 只润色 auto-extracted 的卡片
        if "auto-extracted" not in tags:
            continue
        # 跳过太瘦的卡片（没有实质内容可润色）
        if len(text) < 1000:
            continue
        # 如果已经润色过，不加 force 就跳过
        if "llm-polished" in tags and not force:
            continue

        cards.append({
            "path": f,
            "stem": f.stem,
            "tags": tags,
            "size": len(text),
            "text": text,
        })

    return cards


def extract_frontmatter(text):
    """提取 YAML frontmatter 成字典"""
    # 需要空行容错
    text = re.sub(r'^---\s*\n\s*\n', '---\n', text)  # 修正空行
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {"tags": []}
    yaml_block = m.group(1)

    result = {}
    # tags
    tags = []
    bracket_m = re.search(r"tags:\s*\[([^\]]+)\]", yaml_block)
    if bracket_m:
        tags = [t.strip().strip("'\"") for t in bracket_m.group(1).split(",")]
    else:
        tag_list = re.findall(r"^\s+-\s+(.+)$", yaml_block, re.MULTILINE)
        tags = [t.strip().strip("'\"") for t in tag_list]
    result["tags"] = tags
    src_m = re.search(r"source_type:\s*(.+)", yaml_block)
    if src_m:
        result["source_type"] = src_m.group(1).strip()
    return result


def update_frontmatter_tag(text, add_tag="llm-polished"):
    """在 frontmatter 的 tags 中添加新标签"""
    # 修正空行
    text = re.sub(r'^---\s*\n\s*\n', '---\n', text)
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return text
    yaml_block = m.group(1)

    # 检查是否已有这个标签
    tag_pattern = rf'(?:{re.escape(add_tag)})'
    if re.search(tag_pattern, yaml_block):
        return text  # 已有

    # 尝试在 tags: [...] 中添加
    bracket_m = re.search(r"(tags:\s*\[)([^\]]*)(\])", yaml_block)
    if bracket_m:
        existing_tags = bracket_m.group(2).strip()
        if existing_tags:
            new_tags = f"{existing_tags}, {add_tag}"
        else:
            new_tags = add_tag
        replacement = bracket_m.group(1) + new_tags + bracket_m.group(3)
        new_yaml = yaml_block[:bracket_m.start()] + replacement + yaml_block[bracket_m.end():]
        return text[:m.start()] + "---\n" + new_yaml + "\n---" + text[m.end():]

    # 尝试在 YAML 列表格式中添加
    list_m = re.search(r"(tags:\s*\n(?:^\s+-\s+.+\n?)+)", yaml_block, re.MULTILINE)
    if list_m:
        new_yaml = yaml_block[:list_m.end()] + f"  - {add_tag}\n" + yaml_block[list_m.end():]
        return text[:m.start()] + "---\n" + new_yaml + "\n---" + text[m.end():]

    return text


def call_hermes_for_polish(card_text, card_title):
    """调用 hermes CLI 润色卡片"""
    prompt = f"{POLISH_PROMPT}\n\n## 需润色的卡片：{card_title}\n\n```markdown\n{card_text}\n```"
    try:
        result = subprocess.run(
            [HERMES_CLI, "-z", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            polished = result.stdout.strip()
            # 验证返回内容至少保留了标题
            if card_title in polished or card_title.split("—")[0].strip() in polished or card_title.replace("# ", "").strip() in polished:
                return polished
            else:
                print(f"  ⚠️  润色结果异常（丢失标题），保留原文")
                return None
        else:
            print(f"  ⚠️  hermes 返回码 {result.returncode}: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  hermes 超时")
        return None
    except Exception as e:
        print(f"  ⚠️  调用异常: {e}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LLM 润色概念卡片摘要")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--force", action="store_true", help="强制重新润色所有卡")
    parser.add_argument("--max-cards", type=int, default=0, help="限制润色数量（0=无限制）")
    args = parser.parse_args()

    print("🤖 vault_llm_polish.py — LLM 润色概念卡片摘要")
    print()

    if not is_hermes_available():
        print("❌ hermes CLI 不可用，请确认 ~/.local/bin/hermes 存在")
        return

    cards = find_cards_to_polish(force=args.force)
    print(f"📚 待润色卡片: {len(cards)} 张")
    print()

    if not cards:
        print("✅ 所有概念卡片已润色完成")
        return

    if args.max_cards > 0:
        cards = cards[:args.max_cards]
        print(f"🔒 限制润色: {len(cards)} 张")

    polished_count = 0
    for i, card in enumerate(cards):
        print(f"[{i+1}/{len(cards)}] 🔄 {card['stem']} ({card['size']}B)...")
        sys.stdout.flush()

        if args.dry_run:
            print(f"  📋 将调用 hermes 润色")
            continue

        # 调用 LLM
        result = call_hermes_for_polish(card["text"], card["stem"])

        if result is None:
            print(f"  ❌ 润色失败，跳过")
            continue

        # 添加 llm-polished 标签
        result_with_tag = update_frontmatter_tag(result)

        # 写回
        card["path"].write_text(result_with_tag, encoding="utf-8")
        polished_count += 1
        new_size = len(result_with_tag)
        print(f"  ✅ 润色完成 ({new_size}B, +{new_size - card['size']}B)")
        sys.stdout.flush()

    print()
    print(f"📊 完成: 润色 {polished_count} 张 | 跳过 {len(cards) - polished_count} 张")


if __name__ == "__main__":
    main()
