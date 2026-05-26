#!/usr/bin/env python3
"""
vault_concept_health.py — 概念卡片健康巡检
每周运行，报告概念目录的整体健康状况：
- 总数与趋势
- 瘦卡（<1KB）
- 未润色的 auto-extracted 卡
- 空关联概念的卡
- 老化卡（30天未修改）
"""
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

VAULT = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault",
)
CONCEPT_DIR = Path(VAULT) / "概念"

THIN_THRESHOLD = 1000       # 字节
AGING_DAYS = 30              # 天
WARN_CARDS_WITHOUT_RELATIONS = True


def extract_frontmatter_tags(text: str):
    """从 frontmatter 提取 tags 列表"""
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return []
    yaml_block = m.group(1)
    tags = []
    bracket_m = re.search(r"tags:\s*\[([^\]]+)\]", yaml_block)
    if bracket_m:
        tags = [t.strip().strip("'\"") for t in bracket_m.group(1).split(",")]
    else:
        tag_list = re.findall(r"^\s+-\s+(.+)$", yaml_block, re.MULTILINE)
        tags = [t.strip().strip("'\"") for t in tag_list]
    return tags


def has_relations_section(text: str) -> bool:
    """检查卡片是否有非空的 关联概念 章节"""
    m = re.search(r"## 关联概念\n\n(.+?)(?=\n##|\n---|\Z)", text, re.DOTALL)
    if not m:
        return False
    content = m.group(1).strip()
    # 至少要有一条明确的链接引用
    return bool(re.search(r"\[\[.+?\]\]|`.+?`", content))


def check_vault_health():
    print("=" * 60)
    print("  📊 概念卡片健康巡检")
    print(f"  扫描目录: {CONCEPT_DIR}")
    print(f"  巡检时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print()

    if not CONCEPT_DIR.exists():
        print(f"❌ 概念目录不存在: {CONCEPT_DIR}")
        sys.exit(1)

    files = sorted(CONCEPT_DIR.glob("*.md"))
    total = len(files)
    if total == 0:
        print("⚠️  概念目录为空")
        sys.exit(0)

    # 分类统计
    auto_extracted = 0
    llm_polished = 0
    both_tags = 0
    thin_cards = []
    aging_cards = []
    no_relations = []
    not_polished = []  # auto-extracted 但未 llm-polished
    unknown_tags = []

    now = datetime.now(timezone.utc).timestamp()

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        size = len(text)
        tags = extract_frontmatter_tags(text)
        mtime = f.stat().st_mtime
        days_since_mod = (now - mtime) / 86400

        has_auto = "auto-extracted" in tags
        has_llm = "llm-polished" in tags

        if has_auto:
            auto_extracted += 1
        if has_llm:
            llm_polished += 1
        if has_auto and has_llm:
            both_tags += 1

        # 瘦卡
        if size < THIN_THRESHOLD:
            thin_cards.append((f.stem, size))

        # 老化卡
        if days_since_mod > AGING_DAYS:
            aging_cards.append((f.stem, int(days_since_mod)))

        # 未润色的 auto-extracted 卡
        if has_auto and not has_llm and size >= THIN_THRESHOLD:
            not_polished.append((f.stem, size))

        # 空关联概念
        if not has_relations_section(text):
            no_relations.append(f.stem)

        # 未知标签
        known = {"auto-extracted", "llm-polished", "concept", "对话归档",
                 "概念萃取", "每日一书", "vault-restructure", "GitHub趋势"}
        unknown = [t for t in tags if t.lower() not in known]
        if unknown:
            unknown_tags.extend([(f.stem, t) for t in unknown])

    # ========== 输出报告 ==========
    print(f"📁 概念卡总数: {total}")
    print(f"   ├─ auto-extracted:  {auto_extracted} 张")
    print(f"   ├─ llm-polished:    {llm_polished} 张")
    print(f"   ├─ 已润色(两者兼有): {both_tags} 张")
    print(f"   └─ 非萃取卡片:       {total - auto_extracted} 张")
    print()

    # 健康指标
    issues = []

    # 1️⃣ 未润色的 auto-extracted 卡
    if not_polished:
        print(f"⚠️  待 LLM 润色（auto-extracted 未润色）: {len(not_polished)} 张")
        for name, size in not_polished:
            print(f"   · {name} ({size}B)")
        issues.append(f"{len(not_polished)} 张待润色")
    else:
        print("✅ 所有 auto-extracted 卡片已润色")
    print()

    # 2️⃣ 瘦卡
    if thin_cards:
        print(f"⚠️  瘦卡 (<{THIN_THRESHOLD}B): {len(thin_cards)} 张")
        threshold_500 = [n for n, s in thin_cards if s < 500]
        for name, size in thin_cards:
            flag = " 🚨" if size < 500 else ""
            print(f"   · {name} ({size}B){flag}")
        if threshold_500:
            issues.append(f"{len(threshold_500)} 张极瘦卡(<500B)")
        else:
            issues.append(f"{len(thin_cards)} 张瘦卡")
    else:
        print("✅ 无瘦卡")
    print()

    # 3️⃣ 老化卡
    if aging_cards:
        print(f"⚠️  老化卡（{AGING_DAYS}+ 天未修改）: {len(aging_cards)} 张")
        for name, days in aging_cards:
            print(f"   · {name} ({days}天)")
        issues.append(f"{len(aging_cards)} 张老化卡")
    else:
        print("✅ 无老化卡")
    print()

    # 4️⃣ 空关联概念
    if no_relations:
        print(f"ℹ️  无关联概念章节: {len(no_relations)} 张")
        # 每周重建后会减少，只是参考信息
    print()

    # 5️⃣ 整体评价
    print("—" * 40)
    if issues:
        print(f"⚠️  需关注 ({len(issues)} 项): {', '.join(issues)}")
    else:
        print("✅ 概念卡片目录健康")
    print()

    print()
    return len(issues) > 0  # True = 有问题


if __name__ == "__main__":
    has_issues = check_vault_health()
    sys.exit(1 if has_issues else 0)
