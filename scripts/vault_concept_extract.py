#!/usr/bin/env python3
"""
vault_concept_extract.py — 从资讯日报中提取富概念卡片
=========================================================
扫描 GitHub趋势日报 + AI面试日报，提取高频术语并聚合其上下文，
生成包含实际知识内容的概念卡片，而非仅有来源链接的空壳。

策略升级 (v2)：
1. 解析日报正文，提取术语 + 其上下文段落/表格行
2. 跨文件聚合同一术语的所有上下文
3. 按主题分类上下文片段 → 生成知识密集的章节
4. 自动关联同主题概念
5. 保持技术细节（数据、配置、架构描述）

用法:
  python3 vault_concept_extract.py              # 扫描所有日报，生成富概念卡
  python3 vault_concept_extract.py --dry-run    # 预览，不写入
  python3 vault_concept_extract.py --min-freq 2 # 调节最低出现频次
  python3 vault_concept_extract.py --target 2026-05-16  # 只扫某一天
"""

import os, sys, re, glob
from collections import Counter, defaultdict
from datetime import datetime

# ── 路径配置 ──
VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")
CONCEPT_DIR = os.path.join(VAULT, "概念")
GITHUB_DIR = os.path.join(VAULT, "资讯/GitHub日报")
AI_DIR = os.path.join(VAULT, "资讯/AI面试日报")

# ── 停用词 ──
STOP_WORDS = {
    "一个", "一种", "这个", "那个", "这些", "那些", "什么", "怎么", "如何", "为什么",
    "可以", "需要", "应该", "能够", "可能", "已经", "没有", "不是", "但是", "不过",
    "如果", "虽然", "所以", "因为", "因此", "而且", "或者", "以及",
    "我们", "他们", "她们", "你们", "它们", "自己", "大家", "所有", "每个", "一些",
    "目前", "现在", "今天", "昨天", "明天", "以后", "以前", "之后", "之前",
    "这里", "那里", "上面", "下面", "里面", "外面", "非常", "比较", "最大", "最小",
    "越多", "越少", "更", "最", "很", "都", "也", "就", "才", "刚", "在", "到",
    "从", "把", "被", "让", "给", "向", "对", "与", "和", "或", "的", "了", "是",
    "有", "会", "能", "要", "来", "去", "做", "用", "说", "看", "想", "知道",
    "通过", "进行", "使用", "实现", "提供", "支持", "包括", "成为", "作为",
    "这", "那", "它", "他", "她", "你", "我",
    "今日", "速览", "焦点", "趋势", "观察", "全榜", "回答", "核心", "要点",
    "问题", "难度", "通俗", "理解", "面试", "方向", "误区", "加分", "追问",
    "问", "注意", "白话", "开场", "机制", "角落", "项目", "语言", "简介",
    "一句话", "本周", "主题", "系列", "信号", "特征",
    "star", "stars", "⭐", "github", "http", "https", "com",
    "日报", "aiinterview", "ai-interview", "github-trending",
    "concept", "auto-extracted",
    "agent", "agents", "model", "models", "tool", "tools", "api", "app", "apps",
    "data", "code", "file", "files", "user", "users", "server", "client",
    "web", "open", "source", "free", "fast", "simple", "easy", "new",
    "local", "cloud", "desktop", "mobile", "online", "offline",
    "test", "build", "run", "use", "make", "set", "get", "add",
    "research", "development", "production", "deploy", "hello",
    "deep", "live", "real", "time", "support", "service", "services",
    "system", "platform", "framework", "library", "package",
    "base", "based", "core", "main", "full", "stack", "first",
    "next", "gen", "generation", "powered", "driven", "native",
    "type", "types", "check", "checker", "lint", "formatter",
    "config", "settings", "setup", "install",
    "note", "notes", "doc", "docs", "readme", "license",
    "vibe", "vibing", "cursor", "flow", "mode",
    "project", "projects", "version", "release", "update",
    "custom", "default", "simple", "basic", "advanced",
    "financial", "economic", "business", "enterprise",
    "standard", "protocol", "format", "interface",
    "analysis", "analytics", "insight", "report",
    "management", "manager", "engine", "backend", "frontend",
    "easy", "hard", "good", "bad", "best", "better",
    "one", "two", "three", "first", "second",
    "中国团队", "开源项目", "热门项目", "本周最热", "核心功能",
    "技术架构", "应用场景", "发展趋势", "未来展望",
    # 常见问题/疑问短语 — 非概念
    "是什么", "有什么区别", "有什么区别呢", "有什么", "有哪些", "为什么",
    "怎么办", "怎么做", "怎么用", "怎么看", "怎么实现", "怎么配置",
    "能不能", "要不要", "会不会", "谁更",
    # 日常对话虚词（非知识实体）
    "一句话", "一句话概括", "一句话简介", "一句话总结", "总结来说",
    "总的来说", "简单来说", "本质上是", "本质上",
    "实际上", "实用技巧", "在实际应用中",
    # 无意义的截断短语
    "终端里的", "从零构建智能体教", "终端里",
    "实现基于", "来实现", "帮助你",
    "生命体征监测",
    "系统设计", "面试中", "面试官",
    "上下文", "更多", "上次",
    "工作流程", "工作流", "自动化", "配置方法",
    "角色定位", "市场定位",
}

# ── 辅助函数 ──
def normalize_concept_name(term: str) -> str:
    term = term.strip().strip("()（）[]【】{}《》\"'“”‘’「」『』·•/\\")
    term = re.sub(r'[^\w\s\u4e00-\u9fff\-]', '', term)
    term = re.sub(r'\s+', ' ', term).strip()
    return term

def is_valid_term(term: str) -> bool:
    t = term.strip()
    if len(t) < 2 or len(t) > 40:
        return False
    if t.lower() in STOP_WORDS:
        return False
    if re.match(r'^\d+$', t):
        return False
    if re.match(r'^[\d\s,.+\-*/=<>:]+$', t):
        return False
    digit_ratio = sum(c.isdigit() for c in t) / max(len(t), 1)
    if digit_ratio > 0.5:
        return False
    return True

def is_substantial(term: str) -> bool:
    zh_chars = sum(1 for c in term if '\u4e00' <= c <= '\u9fff')
    if zh_chars >= 3:
        return True
    if term.isupper() and len(term) >= 3:
        return True
    if re.match(r'^[A-Z][a-z]+(?:[A-Z][a-z]+)+$', term) and len(term) >= 4:
        return True
    if re.search(r'[\.]', term) and len(term) >= 4:
        return True
    return False


# ── 上下文感知提取 ──

def extract_context_snippets(text: str, term: str) -> list[str]:
    """
    从文本中提取包含 term 的上下文片段（段落/要点行）。
    返回清洗后的纯文本片段列表。
    """
    snippets = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("|--") or stripped.startswith("# "):
            continue

        # 检查该行是否包含目标术语
        if term.lower() in stripped.lower():
            # 收集上下文：当前行 + 前1行 + 后1行（非空）
            ctx_lines = []
            for j in range(max(0, i-1), min(len(lines), i+2)):
                l = lines[j].strip()
                if l and not l.startswith("|--") and not l.startswith("# "):
                    ctx_lines.append(l)
            snippet = " | ".join(ctx_lines)
            if snippet not in snippets:
                snippets.append(snippet)

    return snippets[:6]  # 最多6段上下文


def extract_project_details(text: str, term: str):  # -> Optional[str], 3.9 compat
    """
    如果 term 出现在 GitHub 趋势日报的表格中，提取项目详情行。
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 7 and term.lower() in cells[2].lower() if len(cells) > 2 else "":
            return line.strip()
    return None


# ── GitHub 日报解析 ──

def parse_github_daily(filepath: str) -> dict:
    """
    解析一篇 GitHub 趋势日报，返回结构化内容。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    result = {
        "path": filepath,
        "terms": [],
        "contexts": defaultdict(list),   # term → [snippet, ...]
        "projects": {},                  # term → project table row
        "overview": "",
        "trend_analysis": "",
        "all_text": text,
    }

    # 提取今日速览
    overview = re.search(r'### 今日速览\s*\n+(.*?)(?=\n####|\n##|\n#)', text, re.DOTALL)
    if overview:
        result["overview"] = overview.group(1).strip()

    # 提取趋势观察
    trend = re.search(r'### 趋势观察\s*\n+(.*?)(?=\n####|\n##|\n#)', text, re.DOTALL)
    if trend:
        result["trend_analysis"] = trend.group(1).strip()

    # 解析表格和正文提取术语
    extracted_terms = []

    # (A) 表格行中的项目名
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 7:
            project = cells[2].strip() if len(cells) > 2 else ""
            desc = cells[6].strip() if len(cells) > 6 else ""

            if "/" in project:
                parts = project.split("/")
                repo_name = parts[-1]
                words = re.split(r'[-_]', repo_name)
                for w in words:
                    w = w.strip()
                    if len(w) >= 2 and w.lower() not in ["skills", "ai", "llm", "cli"]:
                        extracted_terms.append(w)
                        result["projects"][w] = line

            # 简介中提取术语
            zh_phrases = re.findall(r'[\u4e00-\u9fff]{2,8}', desc)
            for p in zh_phrases:
                if p not in STOP_WORDS:
                    extracted_terms.append(p)

    # (B) 速览段落中的中文短语
    if result["overview"]:
        zh_phrases = re.findall(r'[\u4e00-\u9fff]{2,8}', result["overview"])
        for p in zh_phrases:
            if p not in STOP_WORDS and len(p) >= 3:
                extracted_terms.append(p)

    # (C) 趋势观察中的粗体 + 中文短语
    if result["trend_analysis"]:
        bolded = re.findall(r'\*\*(.*?)\*\*', result["trend_analysis"])
        for b in bolded:
            b = b.strip()
            if 2 <= len(b) <= 30:
                extracted_terms.append(b)
        zh_phrases = re.findall(r'[\u4e00-\u9fff]{2,8}', result["trend_analysis"])
        for p in zh_phrases:
            if p not in STOP_WORDS and len(p) >= 3:
                extracted_terms.append(p)

    # (D) 逐段落提取上下文
    for t in extracted_terms:
        snippets = extract_context_snippets(text, t)
        result["contexts"][t] = snippets

    result["terms"] = extracted_terms
    return result


# ── AI 面试日报解析 ──

def parse_ai_daily(filepath: str) -> dict:
    """
    解析一篇 AI 面试日报，返回结构化内容。
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    result = {
        "path": filepath,
        "terms": [],
        "contexts": defaultdict(list),
        "qa_pairs": [],
        "all_text": text,
    }

    # 按题目分割
    q_sections = re.split(r'\n(?=##\s*❓)', text)
    for section in q_sections:
        if not section.strip():
            continue
        q_title_match = re.match(r'##\s*❓\s*(Q\d+):\s*(.+?)(?:\n|$)', section)
        if not q_title_match:
            continue
        q_id = q_title_match.group(1)
        q_title = q_title_match.group(2).strip()

        # 提取核心回答
        answer_match = re.search(r'\*\*回答核心要点\*\*\s*\n(.*?)(?=\n\*\*|\n##|$)', section, re.DOTALL)
        answer_text = answer_match.group(1).strip() if answer_match else ""

        result["qa_pairs"].append({
            "q_id": q_id,
            "q_title": q_title,
            "answer": answer_text,
        })

        # 从题目中提取术语
        for segment in re.split(r'[，,、/\\]', q_title):
            segment = segment.strip()
            en_terms = re.findall(r'[A-Za-z][A-Za-z0-9\-_\.\+]{2,}', segment)
            for e in en_terms:
                e = e.strip()
                if e.lower() not in ["the", "and", "for", "with", "from", "that"]:
                    if is_valid_term(e) and e not in STOP_WORDS:
                        result["terms"].append(e)

            zh_phrases = re.findall(r'[\u4e00-\u9fff]{2,8}', segment)
            for p in zh_phrases:
                if p not in STOP_WORDS and len(p) >= 2:
                    result["terms"].append(p)

        # 从回答中提取粗体术语
        if answer_text:
            bolded = re.findall(r'\*\*(.*?)\*\*', answer_text)
            for b in bolded:
                b = b.strip().strip("()（）")
                if 2 <= len(b) <= 30 and is_valid_term(b):
                    result["terms"].append(b)

        # 从 yaml frontmatter 提取 tags
        fm_tags = re.findall(r'tags:\s*\[(.*?)\]', section)
        for tag_str in fm_tags:
            for tag in tag_str.split(","):
                tag = tag.strip().strip("\"'")
                if len(tag) >= 2 and tag not in ["interview", "ai-agent", "concept"]:
                    result["terms"].append(tag)

    # 去重
    result["terms"] = list(set(result["terms"]))

    # 提取上下文
    for t in result["terms"]:
        snippets = extract_context_snippets(text, t)
        result["contexts"][t] = snippets

    return result


# ── 概念卡片深层生成 ──

def get_existing_concepts() -> dict[str, str]:
    """返回 {friendly_name: full_path} 映射，用于跳过已存在的概念"""
    concepts = {}
    if os.path.isdir(CONCEPT_DIR):
        for fname in os.listdir(CONCEPT_DIR):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(CONCEPT_DIR, fname)
            base = os.path.splitext(fname)[0]
            concepts[base] = fpath
            # 从文件内容中提取标题，也作为索引
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    text = f.read(500)  # 只读前500字符就够了
                m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                if m:
                    title = m.group(1).strip().strip("#🏷️ ")
                    concepts[title] = fpath
            except Exception:
                pass
    return concepts


def find_related_concepts(term: str, existing: dict[str, str]) -> list[str]:
    related = []
    term_lower = term.lower()
    for name in existing.keys():
        if term_lower in name.lower() or name.lower() in term_lower:
            if name != term:
                related.append(name)
    return related


def generate_rich_card(term: str, source_files: list[str], freq: int,
                       all_contexts: list[str], project_details: list[str],
                       existing: dict[str, str]) -> str:
    """
    生成包含实际内容的富概念卡片。
    """
    date_str = datetime.now().strftime("%Y-%m-%d")

    # ── 判断来源类型 ──
    source_names = [os.path.splitext(os.path.basename(f))[0] for f in source_files[:5]]
    is_github = any("GitHub" in s for s in source_names)
    is_ai = any("AI面试" in s for s in source_names)

    # ── 上下文聚合 ──
    unique_contexts = list(dict.fromkeys(all_contexts))  # 去重但保持有序

    # ── 生成摘要 ──
    if is_github:
        summary_parts = []
        if unique_contexts:
            # 从上下文中提取最像一句话定义/描述的句子
            best_lines = []
            for ctx in unique_contexts[:4]:
                for part in ctx.split(" | "):
                    part = part.strip()
                    # 保长带实质内容的句子
                    if len(part) >= 10 and term in part:
                        best_lines.append(f"- {part}")
                        break
            if best_lines:
                summary_parts = best_lines[:3]
        if not summary_parts:
            summary_parts = [f"- 出现在 {len(source_files)} 篇 GitHub 趋势日报中（{freq} 次），是 {datetime.now().year} 年 {datetime.now().month} 月开源社区的热点方向之一。"]

        desc = "".join(summary_parts)
    elif is_ai:
        # AI面试日报 —— 提取回答要点
        answer_points = []
        for ctx in unique_contexts[:4]:
            for part in ctx.split(" | "):
                part = part.strip()
                if len(part) >= 15 and term in part:
                    answer_points.append(f"- {part}")
                    break
        if answer_points:
            desc = "".join(answer_points)
        else:
            desc = f"- 出现在 {len(source_files)} 篇 AI 面试问答中（{freq} 次），是 AI Agent 领域的高频面试考点。"
    else:
        desc = f"- 从资讯日报中提取的高频术语（出现 {freq} 次）。"

    # ── 知识点段落 ──
    knowledge_points = []
    technical_details = []

    for ctx in unique_contexts:
        parts = ctx.split(" | ")
        # 过滤掉太短的
        meaningful_parts = [p.strip() for p in parts if len(p.strip()) >= 12]
        for p in meaningful_parts:
            # 跳过来源链接行
            if p.startswith("[[") or p.startswith("- [[") or p.startswith("| ---"):
                continue
            # 有技术细节（数字、配置、架构词语）的归类到技术细节
            if re.search(r'[\d.]+%|http|\bAPI\b|\bSDK\b|\bCLI\b|\bGPU\b|\bCPU\b|\bRAM\b|\bGB\b', p):
                if p not in technical_details:
                    technical_details.append(p)
            elif len(p) >= 12 and p not in knowledge_points:
                knowledge_points.append(p)

    # ── 关联已有概念 ──
    related = find_related_concepts(term, existing)
    related_links = "\n".join([f"- [[{c}|{c}]]" for c in related[:5]])

    # ── 来源链接 ──
    def source_to_obsidian_link(fpath: str) -> str:
        base = os.path.splitext(os.path.basename(fpath))[0]
        if "GitHub" in fpath:
            return f"[[资讯/GitHub日报/{base}|{base}]]"
        elif "AI面试" in fpath or "ai-interview" in fpath:
            return f"[[资讯/AI面试日报/{base}|{base}]]"
        else:
            return f"[[{base}|{base}]]"

    sources_links = "\n".join([f"- {source_to_obsidian_link(f)}" for f in source_files[:8]])

    # ── 项目详情（GitHub 项目） ──
    projects_section = ""
    if project_details:
        projects_section = "\n## 相关项目\n\n"
        for pd in project_details[:5]:
            projects_section += f"> {pd}\n\n"

    # ── 拼装卡片 ──
    content = f"""---
created: {date_str}
tags:
  - concept
  - auto-extracted
source_count: {freq}
source_type: {"GitHub趋势" if is_github else "AI面试" if is_ai else "混合"}
aliases:
  - {term}
---

# {term}

> 🏷️ 自动萃取概念 · 来源 {freq} 篇日报 · {datetime.now().strftime("%Y年%m月")} 热点

{desc}

## 核心要点

"""

    if knowledge_points:
        for kp in knowledge_points[:6]:
            content += f"- {kp}\n"
    else:
        content += f"_暂无自动提取的知识要点，建议手动补充。_\n"

    if technical_details:
        content += "\n## 技术细节\n\n"
        for td in technical_details[:6]:
            content += f"- `{td}`\n"

    content += projects_section

    if unique_contexts:
        content += "\n## 上下文片段\n\n"
        for i, ctx in enumerate(unique_contexts[:5]):
            content += f"> **来源 {i+1}**：{ctx}\n>\n"

    content += f"""
## 来源文章

{sources_links}

## 关联概念

{related_links if related_links else '_待手动关联_'}

---

*此卡片由 vault_concept_extract.py 自动萃取生成。核心要点从源文章正文中提取，建议人工审阅补充。*
"""
    return content


# ── 主流程 ──

def main(dry_run=False, min_freq=2, target_date=None, force_regen=False):
    print("🧠 vault_concept_extract.py v2 — 富概念自动萃取")
    print()

    # 1. 收集源文件
    source_files = []
    for d in [GITHUB_DIR, AI_DIR]:
        if os.path.isdir(d):
            for fname in sorted(os.listdir(d)):
                if fname.endswith(".md"):
                    if target_date:
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
                        if date_match and date_match.group(1) != target_date:
                            continue
                    source_files.append(os.path.join(d, fname))

    print(f"📂 找到 {len(source_files)} 篇日报")

    # 2. 解析每一篇 → 提取术语 + 上下文
    all_parsed = []
    for fpath in source_files:
        if "GitHub" in fpath:
            parsed = parse_github_daily(fpath)
        else:
            parsed = parse_ai_daily(fpath)
        all_parsed.append(parsed)

    # 3. 跨文件聚合：term → [source_files, contexts, project_details]
    term_files = defaultdict(list)
    term_contexts = defaultdict(list)
    term_projects = defaultdict(list)

    for parsed in all_parsed:
        for t in parsed["terms"]:
            nt = normalize_concept_name(t)
            if not nt or not is_valid_term(nt):
                continue

            term_files[nt].append(parsed["path"])

            # 收集上下文
            for ctx in parsed["contexts"].get(t, []):
                if ctx not in term_contexts[nt]:
                    term_contexts[nt].append(ctx)

            # 收集项目详情
            if t in parsed.get("projects", {}):
                pd = parsed["projects"][t]
                if pd not in term_projects[nt]:
                    term_projects[nt].append(pd)

    # 4. 同义词合并（大小写折叠）
    merged: dict[str, tuple[int, str]] = {}
    for term, files in term_files.items():
        key = term.lower()
        if key in merged:
            old_count, old_term = merged[key]
            if term[0].isupper() and old_term[0].islower():
                merged[key] = (old_count + len(set(files)), term)
            else:
                merged[key] = (old_count + len(set(files)), old_term)
            # 合并上下文
            for ctx in term_contexts.get(term, []):
                if ctx not in term_contexts.get(old_term, []):
                    term_contexts.setdefault(old_term, []).append(ctx)
            for pd in term_projects.get(term, []):
                if pd not in term_projects.get(old_term, []):
                    term_projects.setdefault(old_term, []).append(pd)
            # 合并文件
            for f in files:
                if f not in term_files.get(old_term, []):
                    term_files.setdefault(old_term, []).append(f)
        else:
            merged[key] = (len(set(files)), term)

    # 重构为最终格式
    final_candidates = []
    processed_terms = set()
    for count, term in merged.values():
        if term in processed_terms:
            continue
        processed_terms.add(term)
        all_files = list(set(term_files.get(term, [])))
        total_freq = len(all_files)

        if total_freq >= min_freq and is_substantial(term):
            final_candidates.append({
                "term": term,
                "freq": total_freq,
                "files": all_files,
                "contexts": term_contexts.get(term, []),
                "projects": term_projects.get(term, []),
            })

    final_candidates.sort(key=lambda x: (-x["freq"], x["term"]))

    print(f"🔍 候选概念: {len(final_candidates)} 个（频次≥{min_freq}）")

    if not final_candidates:
        print("✅ 无需处理。")
        return

    # 5. 检查已有概念
    existing = get_existing_concepts()
    print(f"📚 现有概念: {len(existing)} 篇")

    # 6. 生成/预览卡片
    new_count = 0
    skipped_count = 0

    for cand in final_candidates:
        term = cand["term"]
        if not force_regen and term in existing:
            skipped_count += 1
            continue

        # Force模式下跳过已存在但size≥3000B的（保留已丰富的卡）
        if force_regen and term in existing:
            existing_size = os.path.getsize(existing[term])
            if existing_size >= 3000:
                skipped_count += 1
                continue

        card = generate_rich_card(
            term,
            cand["files"],
            cand["freq"],
            cand["contexts"],
            cand["projects"],
            existing,
        )

        fpath = os.path.join(CONCEPT_DIR, f"{term}.md")

        if dry_run:
            print(f"\n  🆕 [dry-run] {term} ({cand['freq']}次)")
            print(f"     上下文: {len(cand['contexts'])} 段")
            print(f"     文件: {len(cand['files'])} 篇")
            # 预览前几行
            for line in card.split("\n")[:5]:
                print(f"       {line}")
        else:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(card)
            print(f"\n  ✅ {term} ({cand['freq']}次, {len(cand['contexts'])}段上下文)")
            print(f"     → 概念/{term}.md")

        new_count += 1

    print(f"\n📊 新建: {new_count} | 跳过已有: {skipped_count} | 候选: {len(final_candidates)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="从资讯日报自动提取富概念卡片")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入")
    parser.add_argument("--min-freq", type=int, default=2, help="最低出现频次（按文件数）")
    parser.add_argument("--target", type=str, default=None, help="限定某一天（YYYY-MM-DD）")
    parser.add_argument("--force", action="store_true", help="强制重建已有瘦卡（跳过已≥3KB的）")
    args = parser.parse_args()
    main(dry_run=args.dry_run, min_freq=args.min_freq, target_date=args.target, force_regen=args.force)
