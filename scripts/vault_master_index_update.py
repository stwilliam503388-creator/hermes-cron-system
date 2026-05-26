#!/usr/bin/env python3
"""
vault_master_index_update.py — 动态重建 知识库总索引 (🏠 知识库总索引.md)

功能：
  1. 扫描 vault 所有笔记，按目录分类统计
  2. 自动更新各分类下的笔记列表（按日期排序）
  3. 保留原有手动写的摘要描述（对已存在的笔记）
  4. 移除已删除笔记的条目
  5. 更新总笔记数、各分类计数、最后更新时间

用法: python3 vault_master_index_update.py [--dry-run]
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ── 路径 ──
HOME = "/Users/liuwei"
VAULT = Path(
    os.environ.get(
        "OBSIDIAN_VAULT_PATH",
        f"{HOME}/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault",
    )
)
INDEX_FILE = VAULT / "🏠 知识库总索引.md"

DRY_RUN = "--dry-run" in sys.argv

# ── 目录分类配置 ──
# (section_name, section_heading, vault_subdir, is_dated_list, max_items)
SECTIONS = [
    # 有专门索引的区域 → 链接到索引，只更新计数
    ("toolnotes", "🔧 工具笔记", "工具笔记", False, 0),
    ("archive", "📅 对话归档", "对话归档", False, 0),
]

# 需要独立列表的区域
LIST_SECTIONS = [
    ("concepts", "🧠 概念 — 知识卡片", "概念"),
    ("learnnotes", "📖 学习笔记 — 实战清单", "学习笔记"),
    ("learnplans", "🎯 学习计划 — 学习路线图", "学习计划"),
    ("workflows", "⚙️ 工作流", "工作流"),
    ("refs", "📚 参考", "参考"),
    ("resources", "📦 资源", "资源"),
]

# 资讯子区域 (显示在 📰 资讯 下的子列表)
NEWS_SUBSECTIONS = [
    ("github_trends", "GitHub 趋势日报", "资讯/GitHub日报", True),
    ("ai_interview", "AI 面试日报", "资讯/AI面试日报", True),
    ("ai_agent_daily", "AI Agent 日报", "资讯/AI Agent日报", True),
    ("douban_daily", "豆瓣每日一书", "资讯/豆瓣每日一书", True),
]

# 根目录的资讯笔记（非日报类）
ROOT_NEWS_NOTES = [
    "GitHub热门项目盘点",
    "GitHub热门Skills推荐与OpenClaw探索",
    "Build-Your-Own-X热门项目详解",
]


def log(msg):
    print(f"  {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")


def get_note_summary(filepath: Path) -> str:
    """从笔记中提取摘要（第一段非空内容，去掉标题行）"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        first_heading = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                first_heading = stripped.lstrip("# ").strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---") and not stripped.startswith(">"):
                # 清理多余空白
                text = re.sub(r'\s+', ' ', stripped)
                if len(text) > 80:
                    text = text[:77] + "..."
                return text if text.strip("📝📌🌟✅❌⚠️📊🔍") else ""
        # fallback: 用第一个 heading
        if first_heading:
            return f"「{first_heading}」"
    except Exception:
        pass
    return ""


def get_date_from_filename(name: str) -> str:
    """从文件名提取日期"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""


def scan_directory(subdir: str) -> list[tuple[str, str, Path]]:
    """扫描子目录，返回 [(sort_key, display_name, filepath)]"""
    results = []
    dirpath = VAULT / subdir
    if not dirpath.exists():
        # 尝试在子目录中递归搜索
        for f in sorted(VAULT.rglob(f"{subdir}/*.md")):
            if f.name == "🏠 知识库总索引.md":
                continue
            name = f.stem
            date = get_date_from_filename(name)
            sort_key = date or name
            results.append((sort_key, name, f))
        return results

    for f in sorted(dirpath.glob("*.md")):
        name = f.stem
        if name in ("🏠 知识库总索引.md", "🔧工具笔记索引", "📰资讯索引", "📅对话归档索引",
                     "🛠Skills文档索引"):
            continue
        # 跳过子目录索引
        if name.endswith("索引"):
            continue
        date = get_date_from_filename(name)
        sort_key = date or name
        results.append((sort_key, name, f))

    # 按 sort_key 排序（日期优先）
    results.sort(key=lambda x: x[0])
    return results


def extract_existing_entries(content: str, section_heading: str) -> dict[str, str]:
    """从现有 index 中提取某个 section 的已有条目 (name → description)"""
    entries = {}
    # 定位到 section
    section_pattern = rf"##\s+{re.escape(section_heading)}"
    m = re.search(section_pattern, content)
    if not m:
        return entries

    start = m.end()
    # 找到下一个 ## 或文件末尾
    end_match = re.search(r"\n##\s+", content[start:])
    if end_match:
        section_text = content[start:start + end_match.start()]
    else:
        section_text = content[start:]

    # 提取所有 wikilink 条目：[[name]] — description
    for line in section_text.split("\n"):
        line = line.strip()
        wm = re.match(r"- \[\[([^\]]+)\]\]\s*(?:—\s*(.+))?", line)
        if wm:
            name = wm.group(1).strip()
            desc = (wm.group(2) or "").strip()
            if name:
                entries[name] = desc
        # 也匹配表格行
        tm = re.match(r"\|\s*\[\[([^\]]+)\]\]", line)
        if tm:
            name = tm.group(1).strip()
            entries[name] = entries.get(name, "")

    return entries


def extract_section_content(content: str, section_heading: str) -> tuple[str, str]:
    """提取现有 index 中某个 section 的完整内容"""
    section_pattern = rf"(##\s+{re.escape(section_heading)}\s*\n.*?)(?=\n##\s+|\n---\s*$|$)"
    m = re.search(section_pattern, content, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(1).strip()
    return "", ""


def build_list_section(section_id: str, heading: str, subdir: str,
                       existing_entries: dict[str, str]) -> str:
    """构建分类列表 section"""
    files = scan_directory(subdir)

    lines = [f"## {heading}", ""]
    if section_id == "concepts":
        lines.append("从资讯和实践中提炼的抽象模型和思维框架。")
        lines.append("")

    # 记录所有找到的文件名
    found_names = set()
    for sort_key, name, fpath in files:
        found_names.add(name)

    # 先写一条一条的列表
    for sort_key, name, fpath in files:
        desc = existing_entries.get(name, "")
        if not desc:
            desc = get_note_summary(fpath)
            if desc:
                desc = f" — {desc}"
        if section_id == "learnplans" and "每日学习" in name:
            # 把每日学习放在学习计划子目录中
            continue
        lines.append(f"- [[{subdir}/{name}]]{desc}")

    # 检查特殊子目录
    if section_id == "learnplans":
        # 把 AI Agent PM 每日学习/ 下的 DayXX 笔记也列出来
        daily_dir = VAULT / subdir / "AI Agent PM 每日学习"
        if daily_dir.exists():
            lines.append("")
            lines.append("### AI Agent PM 每日学习")
            for f in sorted(daily_dir.glob("*.md")):
                name = f.stem
                date = get_date_from_filename(name)
                desc = existing_entries.get(name, "")
                if not desc:
                    desc = get_note_summary(f)
                    if desc:
                        desc = f" — {desc}"
                lines.append(f"- [[{subdir}/AI Agent PM 每日学习/{name}]]{desc}")

    lines.append("")
    return "\n".join(lines)


def build_news_section(existing_content: str) -> str:
    """构建资讯 section（含子区域）"""
    lines = ["## 📰 资讯", ""]
    lines.append("详见：[[资讯/📰资讯索引]]")
    lines.append("")

    existing_entries = extract_existing_entries(existing_content, "📰 资讯")

    for sub_id, sub_title, sub_dir, is_dated in NEWS_SUBSECTIONS:
        files = scan_directory(sub_dir)
        lines.append(f"### {sub_title}")
        if is_dated and files:
            lines.append(f"共 {len(files)} 篇：")
            # 只显示最新的 5 篇 + 一个总数
            for sort_key, name, fpath in files[-5:]:
                desc = existing_entries.get(name, "")
                lines.append(f"- [[{sub_dir}/{name}]]")
            if len(files) > 5:
                oldest = files[0][0]
                newest = files[-1][0]
                # 找最后一条
                lines.append(f"- ... 共 {len(files)} 篇（{oldest} ~ {newest}）")
        else:
            for sort_key, name, fpath in files:
                desc = existing_entries.get(name, "")
                lines.append(f"- [[{sub_dir}/{name}]]")
        lines.append("")

    # 根目录的资讯笔记
    lines.append("### 专题资讯")
    root_files = scan_directory("资讯")
    for sort_key, name, fpath in root_files:
        # 跳过索引文件
        if name in ("📰资讯索引",):
            continue
        desc = existing_entries.get(name, "")
        if not desc:
            desc = get_note_summary(fpath)
            if desc:
                desc = f" — {desc}"
        lines.append(f"- [[{name}]]{desc}")
    lines.append("")

    return "\n".join(lines)


def build_referenced_section(subdir: str, heading: str, existing_content: str) -> str:
    """构建引用到其他索引的区域（如 工具笔记、对话归档）"""
    files = scan_directory(subdir)
    # 子目录
    subdirs = []
    if (VAULT / subdir).exists():
        for d in sorted((VAULT / subdir).iterdir()):
            if d.is_dir():
                subdirs.append(d.name)

    lines = [f"## {heading}", ""]

    if subdir == "工具笔记":
        lines.append("详见：[[工具笔记/🔧工具笔记索引]]")
        lines.append("")
        lines.append(f"工具笔记根目录 {len(files)} 篇，Skills 文档 57 篇，另有子目录：{', '.join(subdirs)}")
    elif subdir == "对话归档":
        lines.append("详见：[[对话归档/📅对话归档索引]]")
        lines.append("")
        # 显示最近 7 天
        recent = files[-7:] if len(files) > 7 else files
        lines.append(f"共 {len(files)} 篇归档（最近 {len(recent)} 篇）：")
        for sort_key, name, fpath in reversed(recent):
            summary = get_note_summary(fpath)
            if summary:
                lines.append(f"- [[{subdir}/{name}]] — {summary}")
            else:
                lines.append(f"- [[{subdir}/{name}]]")
        if len(files) > 7:
            lines.append(f"- ... 共 {len(files)} 篇")
    lines.append("")

    return "\n".join(lines)


def count_all_notes() -> dict:
    """统计所有笔记"""
    categories = {}
    total = 0

    # 所有 .md 文件（排除 .obsidian）
    all_notes = list(VAULT.rglob("*.md"))
    all_notes = [f for f in all_notes if ".obsidian" not in str(f)]

    for f in all_notes:
        rel = f.relative_to(VAULT)
        parts = rel.parts
        if len(parts) == 1:
            cat = "根目录"
        else:
            cat = parts[0]
        categories[cat] = categories.get(cat, 0) + 1
        total += 1

    return categories, total


def generate_index() -> str:
    """生成完整的知识库总索引"""
    print("扫描 vault 结构...")
    categories, total_notes = count_all_notes()
    now = datetime.now().strftime("%Y-%m-%d")

    print(f"总笔记数: {total_notes}")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} 篇")

    # 读取现有 index（保留手动摘要）
    existing_content = ""
    if INDEX_FILE.exists():
        existing_content = INDEX_FILE.read_text(encoding="utf-8")

    # ── Header ──
    lines = [
        "# 🏠 知识库总索引",
        "",
        "> 本 vault 以 **AI 编码工具** 和 **个人知识管理** 为核心，包含日常对话归档、工具使用笔记、工作流方法论、资讯日报和提炼的知识卡片。",
        f"> 共计 {total_notes} 篇笔记 | 自动更新: {now}",
        "",
        "---",
        "",
        "## 📂 目录导航",
        "",
        "| 区域 | 内容 | 数量 | 中层索引 |",
        "|------|------|------|----------|",
    ]

    # ── 导航表 ──
    nav = [
        ("#🧠 概念 — 知识卡片", "抽象概念、思维模型、生态分析", categories.get("概念", 0), "—"),
        ("#📖 学习笔记 — 实战清单", "可执行的分类清单、推荐列表", categories.get("学习笔记", 0), "—"),
        ("#🎯 学习计划 — 学习路线图", "系统性学习目标和路线", categories.get("学习计划", 0), "—"),
        ("#🔧 工具笔记", "AI 编码工具安装/配置/使用技巧 + Skills 文档", categories.get("工具笔记", 0), "✅"),
        ("#⚙️ 工作流", "写作规则、归档流水线、审计流程", categories.get("工作流", 0), "—"),
        ("#📰 资讯", "GitHub 趋势日报、AI 面试问答、工具推荐", categories.get("资讯", 0), "✅"),
        ("#📅 对话归档", "按日归档的完整对话记录", categories.get("对话归档", 0), "✅"),
        ("#📚 参考", "Obsidian 使用指南等参考文档", categories.get("参考", 0), "—"),
        ("#📦 资源", "外部资源文件索引", categories.get("资源", 0) + 8, "—"),
    ]

    for anchor, desc, count, has_index in nav:
        index_str = f" [[工具笔记/🔧工具笔记索引|✅]]" if has_index == "✅" and anchor == "#🔧 工具笔记" else (
            f" [[资讯/📰资讯索引|✅]]" if has_index == "✅" and anchor == "#📰 资讯" else (
            f" [[对话归档/📅对话归档索引|✅]]" if has_index == "✅" and anchor == "#📅 对话归档" else (
            f" ✅" if has_index == "✅" else " —"
        )))
        lines.append(f"| [[{anchor}]] | {desc} | {count} |{index_str} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 各分类内容 ──
    # 提取现有的摘要
    existing_concepts = extract_existing_entries(existing_content, "🧠 概念 — 知识卡片")
    existing_learnnotes = extract_existing_entries(existing_content, "📖 学习笔记 — 实战清单")
    existing_learnplans = extract_existing_entries(existing_content, "🎯 学习计划 — 学习路线图")
    existing_workflows = extract_existing_entries(existing_content, "⚙️ 工作流")
    existing_refs = extract_existing_entries(existing_content, "📚 参考")
    existing_resources = extract_existing_entries(existing_content, "📦 资源")

    # 概念
    lines.append(build_list_section("concepts", "🧠 概念 — 知识卡片", "概念", existing_concepts))
    # 学习笔记
    lines.append(build_list_section("learnnotes", "📖 学习笔记 — 实战清单", "学习笔记", existing_learnnotes))
    # 学习计划
    lines.append(build_list_section("learnplans", "🎯 学习计划 — 学习路线图", "学习计划", existing_learnplans))
    # 工具笔记（引用现有索引）
    lines.append(build_referenced_section("工具笔记", "🔧 工具笔记", existing_content))
    # 工作流
    lines.append(build_list_section("workflows", "⚙️ 工作流", "工作流", existing_workflows))
    # 资讯
    lines.append(build_news_section(existing_content))
    # 对话归档
    lines.append(build_referenced_section("对话归档", "📅 对话归档", existing_content))
    # 参考
    lines.append(build_list_section("refs", "📚 参考", "参考", existing_refs))
    # 资源
    lines.append(build_list_section("resources", "📦 资源", "资源", existing_resources))

    # ── Footer ──
    lines.append("---")
    lines.append("")
    lines.append("## 🔗 跨域链接图")
    lines.append("")
    lines.append("```")
    lines.append("工具笔记 ──→ 工作流 / 概念 （方法论支撑 → 抽象提炼）")
    lines.append("资讯 ──→ 概念/学习笔记（知识卡片提炼）─→ 对话归档（日报源头）")
    lines.append("学习计划 ──→ 工具笔记 / 概念（学习目标 → 资源映射）")
    lines.append("对话归档 ──→ 工具笔记/工作流（操作记录）")
    lines.append("Skills 文档 ──→ 工具笔记（技术补充）")
    lines.append("```")
    lines.append("")
    lines.append("> 提示：在 Obsidian 中打开本页，按 `Cmd+Click` 跳转到任意笔记；`Graph View`（Ctrl+G）查看全库关联图。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"> 由 Hermes Agent 自动维护 | 自动更新: {now}")

    return "\n".join(lines) + "\n"


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"  知识库总索引自动更新 — {ts}")
    if DRY_RUN:
        print(f"  ⚠️  干运行模式")
    print(f"{'=' * 50}")

    # 生成新索引
    new_content = generate_index()

    if DRY_RUN:
        print(f"\n📄 预览: 新索引将输出到 {INDEX_FILE}")
        # 显示统计摘要
        lines = new_content.split("\n")
        for line in lines:
            if "共计" in line and "篇笔记" in line:
                print(f"  {line.strip()}")
            if line.strip().startswith("| 区域 |"):
                print(f"  {line.strip()}")
                break
        # 显示导航表
        in_nav = False
        for line in lines:
            if line.strip().startswith("| 区域 |"):
                in_nav = True
                print(f"  {line.strip()}")
                continue
            if in_nav and line.strip().startswith("|"):
                print(f"  {line.strip()}")
            elif in_nav and not line.strip().startswith("|-"):
                in_nav = False
        print(f"\n  新索引大小: {len(new_content)} 字符")
        ok("干运行完成，未写入文件")
        return

    # 写入
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(new_content, encoding="utf-8")
    ok(f"索引已更新: {INDEX_FILE}")
    print(f"  大小: {len(new_content)} 字符")
    print(f"  总笔记数: {new_content.split('共计')[1].split('篇')[0].strip()}" if "共计" in new_content else "")

    # 也尝试更新 🔧工具笔记索引.md 和 📰资讯索引.md — 至少更新计数
    # (工具笔记索引和资讯索引的内容较多，先保持手动)
    # 提示：🔧工具笔记索引 和 🛠Skills文档索引 为手工维护，需关注过期警告
    print("\n提示: 🔧工具笔记索引 和 🛠Skills文档索引 为手工维护索引，过期状态已在维护流水线中检测")


if __name__ == "__main__":
    main()
