#!/usr/bin/env python3
"""
知识库自动补链 — vault_autolink.py
为零入链孤岛笔记自动推荐关联笔记并补链。

策略（三级匹配）：
1. 精确匹配 — 笔记标题关键词在目标笔记中完整出现
2. 标签匹配 — 标签相同或相似的笔记
3. 语义匹配 — 通过 ollama 做向量相似度（可选，默认关闭）

用法：
  python3 vault_autolink.py                     # 扫描+推荐（不写入）
  python3 vault_autolink.py --apply             # 写入推荐链接到孤岛笔记（交互确认）
  python3 vault_autolink.py --apply --dry-run   # 显示将要写入的内容但不写入
  python3 vault_autolink.py --apply --auto      # 无人值守：自动写入匹配度≥1.5且≥2条的推荐
  python3 vault_autolink.py --target xxx --apply --auto  # 定向+自动
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
EXCLUDE_DIRS = {".obsidian", "工具笔记/skills"}
LINK_RESOLVE_DIRS = {"工具笔记/skills"}  # for link resolution only
EXCLUDE_FILES = {"_同步状态", "📊 知识库健康报告"}
MAX_RECOMMENDATIONS = 5  # 每个孤岛最多推荐数
TAG_WEIGHT = 0.5  # 标签匹配权重（名称匹配为1.0）


def is_excluded(p: Path) -> bool:
    rel = p.relative_to(VAULT).as_posix()
    if "📊 知识库健康报告" in p.name:
        return True
    return any(rel.startswith(ed) or f"/{ed}/" in rel for ed in EXCLUDE_DIRS)


def get_all_md_files():
    files = []
    for f in Path(VAULT).rglob("*.md"):
        if not is_excluded(f):
            files.append(f)
    return files


def strip_file_ext(filename):
    """去掉文件名中的扩展名 (.md) 返回裸名称"""
    return filename.replace(".md", "").strip()


def extract_links(content):
    """提取 [[wikilinks]] 引用"""
    return set(re.findall(r'\[\[([^\]#|]+?)(?:#[^\]]*?|(?:\|[^\]]*?))?\]\]', content))


def extract_tags(content):
    """提取 #tag（排除标题 ##）"""
    return set(re.findall(r'(?<!\w)#([a-zA-Z0-9_\-\u4e00-\u9fff/]+)', content))


def extract_keywords(text, stem):
    """从笔记中提取关键词用于匹配"""
    words = set()

    # 标题行
    for line in text.split("\n"):
        if line.startswith("#"):
            # 去除 # 和 [[]] 标记
            clean = re.sub(r'[#\[\]]', '', line).strip()
            for w in re.split(r'[/\s,，。；;：:、()（）""「」]', clean):
                w = w.strip()
                if len(w) >= 2 and w != stem:
                    words.add(w)

    # 所有 [[]] 中的链接名（出链关键词）
    for link in re.findall(r'\[\[([^\]#|]+?)(?:\|[^\]]*?)?\]\]', text):
        words.add(link.strip())

    return words


def get_inbound_count(files, stem):
    """统计入链数"""
    count = 0
    for f in files:
        content = f.read_text(encoding="utf-8", errors="ignore")
        pattern = re.escape(stem)
        if re.search(rf'\[\[{pattern}(?:\|[^\]]*)?\]\]', content):
            count += 1
    return count


def find_recommendations(orphan_path, files, all_data):
    """为孤岛笔记寻找推荐关联"""
    content = orphan_path.read_text(encoding="utf-8", errors="ignore")
    orphan_stem = orphan_path.stem
    orphan_tags = extract_tags(content)
    orphan_keywords = extract_keywords(content, orphan_stem)

    scores = []  # [(file_path, score, match_type, detail)]

    for f in files:
        if f == orphan_path:
            continue

        target_content = f.read_text(encoding="utf-8", errors="ignore")
        target_stem = f.stem
        target_tags = extract_tags(target_content)
        target_rel = f.relative_to(VAULT).as_posix()

        score = 0.0
        match_details = []

        # 1. 精确名称匹配：孤岛名称出现在目标笔记中
        if orphan_stem in target_content:
            score += 1.0
            match_details.append("名称匹配")

        # 2. 关键词匹配
        kw_matches = [kw for kw in orphan_keywords if len(kw) >= 2 and kw in target_content]
        if kw_matches:
            kw_score = min(len(kw_matches) * 0.3, 0.9)
            score += kw_score
            match_details.append(f"关键词×{len(kw_matches)}")

        # 3. 标签匹配
        common_tags = orphan_tags & target_tags
        if common_tags:
            tag_score = len(common_tags) * TAG_WEIGHT
            score += tag_score
            match_details.append(f"标签#{','.join(common_tags)}")

        if score >= 0.5:  # 匹配阈值
            scores.append((target_rel, round(score, 2), match_details))

    scores.sort(key=lambda x: -x[1])
    return scores[:MAX_RECOMMENDATIONS]


def scan_vault(target_file=None):
    """扫描返回所有孤岛笔记的信息。若 target_file 指定，只分析该文件。"""
    files = get_all_md_files()

    # 构建所有笔记的元数据
    all_data = {}
    for f in files:
        content = f.read_text(encoding="utf-8", errors="ignore")
        rel = f.relative_to(VAULT).as_posix()
        all_data[f] = {
            "path": rel,
            "stem": f.stem,
            "tags": extract_tags(content),
            "keywords": extract_keywords(content, f.stem),
        }

    # 确定要检查的候选文件
    candidates = files
    if target_file:
        target_path = Path(VAULT) / target_file
        if not target_path.exists():
            print(f"错误: 文件不存在 — {target_file}")
            return []
        candidates = [target_path]
        print(f"定向检查: {target_file}")

    # 找出孤岛
    orphans = []
    for f in candidates:
        if is_excluded(f):
            continue
        stem = f.stem
        if get_inbound_count(files, stem) == 0 and stem not in ("🏠 知识库总索引",) and stem not in EXCLUDE_FILES:
            recs = find_recommendations(f, files, all_data)
            rel = f.relative_to(VAULT).as_posix()
            orphans.append({
                "path": rel,
                "stem": stem,
                "recommendations": recs,
            })

    orphans.sort(key=lambda x: x["stem"])
    return orphans


def format_recommendations_block(orphan, style="report"):
    """生成推荐块文本，report 或 obisidan-link 格式"""
    recs = orphan["recommendations"]
    if not recs:
        return None

    lines = []
    if style == "obsidian":
        lines.append("\n## 关联笔记\n")
        for target, score, details in recs:
            target_stem = Path(target).stem
            detail_str = " · ".join(details)
            lines.append(f"- [[{target_stem}]] — {detail_str} (匹配度: {score})")
        return "\n".join(lines)
    else:
        lines.append(f"  **{orphan['stem']}** (`{orphan['path']}`)")
        if not recs:
            lines.append("    无推荐")
        else:
            for target, score, details in recs:
                target_stem = Path(target).stem
                detail_str = " · ".join(details)
                lines.append(f"    → [[{target_stem}]] ({detail_str}, 匹配度{score})")
        return "\n".join(lines)


def main():
    apply_mode = "--apply" in sys.argv
    dry_run = "--dry-run" in sys.argv
    auto_mode = "--auto" in sys.argv
    target_file = None
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            target_file = sys.argv[i + 1]
            break

    if target_file:
        print(f"定向模式: {target_file}")
    print("扫描知识库...")
    orphans = scan_vault(target_file=target_file)

    # 统计
    total_orphans = len(orphans)
    total_recs = sum(len(o["recommendations"]) for o in orphans)
    orphans_with_recs = sum(1 for o in orphans if o["recommendations"])

    print(f"\n孤岛笔记: {total_orphans} 篇")
    print(f"有推荐关联的: {orphans_with_recs} 篇")
    print(f"推荐总数: {total_recs} 条")
    print()

    if apply_mode:
        if not dry_run and not auto_mode:
            confirm = input("即将写入关联笔记到孤岛文件，继续? (y/N): ")
            if confirm.lower() != "y":
                print("已取消")
                return

        AUTO_MIN_SCORE = 1.5   # auto 模式下最低匹配度
        AUTO_MIN_RECS = 2       # auto 模式下最少推荐数

        written = 0
        skipped_low = 0   # auto 模式下因置信度不足跳过
        skipped_has_section = 0
        for o in orphans:
            rec_block = format_recommendations_block(o, style="obsidian")
            if not rec_block:
                continue

            filepath = Path(VAULT) / o["path"]
            content = filepath.read_text(encoding="utf-8", errors="ignore")

            # 检查是否已有 ## 关联笔记
            if "## 关联笔记" in content:
                skipped_has_section += 1
                if dry_run or auto_mode:
                    print(f"[SKIP] {o['stem']} — 已有关联笔记章节")
                continue

            # auto 模式：置信度过滤
            if auto_mode:
                recs = o["recommendations"]
                high_conf_recs = [(t, s, d) for t, s, d in recs if s >= AUTO_MIN_SCORE]
                if len(high_conf_recs) < AUTO_MIN_RECS:
                    skipped_low += 1
                    print(f"[AUTO-SKIP] {o['stem']} — 匹配度≥{AUTO_MIN_SCORE}仅{len(high_conf_recs)}条 (需要≥{AUTO_MIN_RECS})")
                    continue
                # 重建推荐块（仅高置信度条）
                o_trimmed = {**o, "recommendations": high_conf_recs}
                rec_block = format_recommendations_block(o_trimmed, style="obsidian")

            if dry_run:
                print(f"[DRY-RUN] 写入 {o['stem']}:")
                for line in rec_block.split("\n"):
                    print(f"  | {line}")
                print()
                written += 1
            else:
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write("\n" + rec_block + "\n")
                print(f"[OK] 写入 {o['stem']} → {len(o['recommendations'])} 条推荐")
                written += 1

        mode_tag = "auto" if auto_mode else ("dry-run" if dry_run else "apply")
        print(f"\n操作完成 [{mode_tag}]: 写入 {written} 篇")
        if auto_mode:
            print(f"  低置信度跳过: {skipped_low} 篇")
            print(f"  已有关联章节跳过: {skipped_has_section} 篇")

    else:
        # 报告模式
        print("=" * 60)
        print(f"共 {total_orphans} 篇孤岛笔记, {orphans_with_recs} 篇有推荐关联")
        print("=" * 60)
        print()

        for o in orphans:
            block = format_recommendations_block(o, style="report")
            if block:
                print(block)
                print()

        print("=" * 60)
        print(f"提示: 运行 python3 vault_autolink.py --dry-run 查看即将写入的内容")
        print(f"      运行 python3 vault_autolink.py --apply 实际写入 (带确认)")
        print(f"      运行 python3 vault_autolink.py --apply --auto 无人值守自动写入")
        print("=" * 60)


if __name__ == "__main__":
    main()
