#!/usr/bin/env python3
"""
AI Agent PM 学习伴侣 — 问答 Agent
===============================
基于已缓存的每日学习内容，回答学员的跟进问题。

支持两种模式：
  - 本地模式 (--local)：使用 Ollama qwen3:32b，隐私优先，无 API 费用
  - API 模式（默认）：使用 DeepSeek Chat，效果更好

用法：
  python qa-agent.py                            # 交互模式（默认 API）
  python qa-agent.py "什么是 Agent 的评估体系"   # 单次问答
  python qa-agent.py --local                    # 本地模型交互模式
  python qa-agent.py -l "RAG 是什么"             # 本地模型单次问答
  python qa-agent.py --all                      # 使用所有缓存内容（不限最近天数）
  python qa-agent.py --days 3 "面试怎么准备"     # 只看最近 3 天内容
"""

import os
import sys
import re
import json
import glob
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, date
from urllib.request import Request, urlopen
from urllib.error import URLError

# ========================= 配置（优先从 .env 读取）=========================

CACHE_DIR = os.path.expanduser("~/.hermes/learning-plans")
MAX_CONTEXT_CHARS = 5000       # 注入 LLM 的上下文最大字符数
MAX_HISTORY_TURNS = 6          # 交互模式保留的历史轮次
DEFAULT_RECENT_DAYS = 7        # 默认只看最近 N 天的内容


def _load_env_q(key: str, default: str = "") -> str:
    """从 ~/.hermes/.env 读取变量"""
    env_path = os.path.expanduser("~/.hermes/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line[len(key) + 1:].strip("\"'")
    except (FileNotFoundError, IOError):
        pass
    return default


OLLAMA_MODEL = _load_env_q("OLLAMA_MODEL", "qwen3:32b")
OLLAMA_API_URL = _load_env_q("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/chat"
DEEPSEEK_MODEL = _load_env_q("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_URL = _load_env_q("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")

# ========================= 工具函数 =========================


def load_env_api_key():
    """从 ~/.hermes/.env 读取 DeepSeek API Key"""
    env_path = os.path.expanduser("~/.hermes/.env")
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    return None


def get_cached_files(recent_days=None):
    """获取缓存的学习内容文件，按修改时间排序（最新的在前）

    Args:
        recent_days: 只返回最近 N 天的文件，None 表示全部
    """
    pattern = os.path.join(CACHE_DIR, "Day*.md")
    files = glob.glob(pattern)

    if not files:
        return []

    # 按修改时间排序
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    if recent_days is not None:
        cutoff = datetime.now().timestamp() - recent_days * 86400
        files = [f for f in files if os.path.getmtime(f) >= cutoff]

    return files


def load_cached_content(recent_days=DEFAULT_RECENT_DAYS):
    """加载缓存内容，返回 [{date, title, week, topic, content}, ...]

    Args:
        recent_days: 只看最近 N 天（默认 7）。设为 None 则全部加载。
    """
    files = get_cached_files(recent_days)
    if not files:
        return []

    contents = []
    for fp in files:
        fname = os.path.basename(fp)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
        except (IOError, UnicodeDecodeError):
            continue

        # 从文件名解析信息：Day01_Week1_2026-05-17_主题.md
        meta = {"file": fname, "content": text}
        m = re.search(r"Day(\d+)_Week(\d+)_(\d{4}-\d{2}-\d{2})_(.+)\.md$", fname)
        if m:
            meta["day"] = int(m.group(1))
            meta["week"] = int(m.group(2))
            meta["date"] = m.group(3)
            meta["topic"] = m.group(4).replace("_", " ").strip()
        else:
            meta["date"] = "unknown"
            meta["topic"] = fname

        contents.append(meta)

    return contents


def find_relevant_context(question, contents, max_chars=MAX_CONTEXT_CHARS):
    """从缓存内容中找到与问题最相关的上下文

    策略：用问题关键词在内容中找匹配度最高的文件，按匹配行数排序。
    """
    if not contents:
        return None

    # 提取问题关键词（去除停用词）
    keywords = set()
    for w in re.findall(r"[\u4e00-\u9fff\w]+", question):
        if len(w) > 1 and w not in (
            "什么", "怎么", "如何", "为什么", "这个", "那个",
            "一个", "可以", "没有", "不是", "就是", "我们",
            "他们", "你们", "自己", "因为", "所以", "但是",
            "如果", "虽然", "而且", "或者", "还是", "已经",
            "知道", "觉得", "认为", "需要", "应该", "能够",
            "请问", "你好", "谢谢", "然后", "这样", "那样",
            "the", "what", "how", "why", "which", "where",
            "this", "that", "with", "from", "have"
        ):
            keywords.add(w.lower())

    if not keywords:
        # 没有有效关键词，返回最近的内容
        keywords = {"agent"}

    # 评分：每个文件匹配了多少关键词
    scored = []
    for item in contents:
        text = item["content"].lower()
        match_count = sum(1 for k in keywords if k in text)
        if match_count > 0:
            scored.append((match_count, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 取 top 文件，拼接不超过 max_chars 的上下文
    context_parts = []
    total_chars = 0

    for _, item in scored:
        excerpt = item["content"]
        if total_chars + len(excerpt) > max_chars:
            # 截断
            remaining = max_chars - total_chars
            if remaining > 500:
                excerpt = excerpt[:remaining] + "\n... [截断]"
            else:
                break
        header = f"=== {item.get('date', '')} 第{item.get('week','?')}周: {item.get('topic','?')} ===\n"
        context_parts.append(header + excerpt)
        total_chars += len(header) + len(excerpt)

    final_context = "\n\n".join(context_parts)

    # 如果没有匹配到，回退
    if not context_parts and contents:
        item = contents[0]
        header = f"=== {item.get('date', '')} 第{item.get('week','?')}周: {item.get('topic','?')} ===\n"
        final_context = header + item["content"][:max_chars]

    return final_context


# ========================= LLM 调用 =========================

QA_SYSTEM_PROMPT = """你是一个 AI Agent 产品经理的学习教练，正在回答学员关于课程内容的跟进问题。

## 你的角色
- 你有丰富的 AI Agent 产品经理知识体系
- 你是耐心且善于启发式的导师，而不是直接给答案
- 你会引用学员已学的内容作为基础，然后进行延伸

## 回答要求
1. 优先基于下方提供的「课程上下文」来回答问题
2. 如果上下文不足以回答，再补充你自己的知识，但需标注"📚 拓展阅读"
3. 回答要结构清晰，必要时用子标题或列表
4. 结合 PM 思维：用户导向、数据驱动、优先级权衡
5. 鼓励学员结合实际工作进行思考，可追问引导
6. 如果问题不清楚，先解释你的理解再回答
7. 回答控制在 800 字以内，除非问题非常复杂

## 回答格式
- 核心回答：直接、有结构
- 如果适用，加一个「💡 思考延伸」板块提出进一步思考方向
- 如果问题涉及面试，加一个「🎯 面试官视角」板块
"""


def call_deepseek(system_prompt, user_prompt, max_tokens=2000):
    """调用 DeepSeek Chat API"""
    api_key = load_env_api_key()
    if not api_key:
        print("❌ 未找到 DEEPSEEK_API_KEY，请检查 ~/.hermes/.env")
        return None

    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")

    req = Request(
        DEEPSEEK_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except URLError as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"❌ DeepSeek API 返回异常: {e}")
        return None


def call_ollama(system_prompt, user_prompt, max_tokens=2000):
    """调用本地 Ollama 模型"""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.7,
        },
        "stream": False,
    }).encode("utf-8")

    req = Request(
        OLLAMA_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["message"]["content"]
    except URLError as e:
        print(f"❌ Ollama 调用失败: {e}")
        print("   请确认 Ollama 已启动: ollama serve")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"❌ Ollama 返回异常: {e}")
        return None


def get_answer(question, context, use_local=False, history=None):
    """获取问答回复

    Args:
        question: 用户问题
        context: 课程上下文（从缓存中检索）
        use_local: 是否使用本地 Ollama
        history: 对话历史 [(role, content), ...]
    """
    system_prompt = QA_SYSTEM_PROMPT

    # 构建 user_prompt
    prompt_parts = []

    if context:
        prompt_parts.append("## 📚 课程上下文（基于已学习的课程内容）\n")
        prompt_parts.append(context)

    if history:
        prompt_parts.append("\n## 💬 对话历史\n")
        for role, content in history[-MAX_HISTORY_TURNS:]:
            label = "学员" if role == "user" else "教练"
            prompt_parts.append(f"{label}: {content[:300]}")

    prompt_parts.append(f"\n## ❓ 学员提问\n{question}\n")
    prompt_parts.append("\n请基于以上上下文回答。")

    user_prompt = "\n".join(prompt_parts)

    if use_local:
        return call_ollama(system_prompt, user_prompt)
    else:
        return call_deepseek(system_prompt, user_prompt)


# ========================= 交互式界面 =========================


SUGGESTED_QUESTIONS = [
    "今天学到的核心概念是什么？用一句话概括",
    "这个概念在实际工作中怎么应用？",
    "这个技术和 XX 有什么区别？",
    "如果面试官问这个问题，该怎么答？",
    "能给我一个产品设计题的思路框架吗？",
]


def print_banner(use_local=False):
    """打印欢迎 banner"""
    mode = "🔒 本地模型 (Ollama qwen3:32b)" if use_local else "☁️  DeepSeek Chat API"
    print("=" * 60)
    print("  🤖 AI Agent PM 学习伴侣 — 问答 Agent")
    print(f"  模式: {mode}")
    print("=" * 60)
    print()
    print("💡 你可以问：")
    print("   - 课程内容的跟进问题")
    print("   - Agent 产品经理面试准备")
    print("   - 某个概念的实际应用场景")
    print("   - 或直接输入你的疑惑")
    print()
    print("📖 建议问题：")
    for i, q in enumerate(SUGGESTED_QUESTIONS, 1):
        print(f"   {i}. {q}")
    print()
    print("🔄 输入 /new 重置对话  |  /help 帮助  |  /quit 退出")
    print()


def print_help():
    print()
    print("🆘 帮助")
    print("  /quit      - 退出程序")
    print("  /exit      - 退出程序")
    print("  /new       - 重置对话历史")
    print("  /help      - 显示此帮助")
    print("  /context   - 查看当前加载的上下文来源")
    print("  /refresh   - 重新加载缓存内容")
    print("  !question  - 加 ! 前缀切换到反问模式（教练问你问题）")
    print()


def interactive_loop(use_local=False, recent_days=DEFAULT_RECENT_DAYS):
    """交互式问答循环"""
    contents = load_cached_content(recent_days)
    context = None
    history = []

    if contents:
        context = find_relevant_context("", contents)
        print(f"📂 已加载 {len(contents)} 篇学习内容缓存")
        dates = ", ".join(c.get("date", "?") for c in contents[:3])
        if len(contents) > 3:
            dates += f" 等 {len(contents)} 篇"
        print(f"   日期范围: {dates}")
    else:
        print("⚠️  未找到缓存的学习内容（.hermes/learning-plans/ 为空）")
        print("   将在「通用知识」模式下回答，建议先运行计划推送生成内容。")
    print()

    print_banner(use_local)

    while True:
        try:
            q = input("🤔 你的问题> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not q:
            continue

        # 命令处理
        if q.lower() in ("/quit", "/exit", "q"):
            print("👋 再见！")
            break
        elif q.lower() == "/help":
            print_help()
            continue
        elif q.lower() == "/new":
            history = []
            print("🔄 对话历史已重置")
            continue
        elif q.lower() == "/context":
            if context:
                print(f"\n📂 当前上下文（{len(context)} 字符）：")
                print(context[:500] + ("..." if len(context) > 500 else ""))
            else:
                print("⚠️  当前没有加载课程上下文")
            continue
        elif q.lower() == "/refresh":
            contents = load_cached_content(recent_days)
            context = find_relevant_context("", contents) if contents else None
            print(f"🔄 已刷新，加载 {len(contents)} 篇内容")
            continue

        # 特殊模式：反问模式
        coach_mode = False
        if q.startswith("!"):
            coach_mode = True
            q = q[1:].strip()

        # 检索最相关的上下文
        if contents:
            context = find_relevant_context(q, contents)

        if coach_mode:
            # 反问模式：让 LLM 扮演面试官提问
            coach_prompt = (
                "你是一个 AI Agent 产品经理的面试官，正在模拟面试场景。\n"
                "学员说：" + q + "\n\n"
                "请基于这段内容，向他提出 1-2 个追问或深入考察的问题。\n"
                "要求：问题要层层深入，考察学员的真实理解深度。"
            )
            answer = get_answer(coach_prompt, context, use_local, history)
            role_tag = "🎤 面试官"
        else:
            answer = get_answer(q, context, use_local, history)

        if answer:
            if coach_mode:
                print(f"\n{role_tag}:")
            else:
                print(f"\n💡 回答:")
            print(answer)
            print()
            history.append(("user", q))
            history.append(("assistant", answer[:200]))
        else:
            print("⚠️  回答生成失败，请重试或检查网络/服务状态")
            print()


def single_shot(question, use_local=False, recent_days=DEFAULT_RECENT_DAYS, verbose=False):
    """单次问答模式"""
    contents = load_cached_content(recent_days)
    context = find_relevant_context(question, contents) if contents else None

    if verbose:
        print(f"📂 加载 {len(contents)} 篇缓存内容")
        if context:
            print(f"📚 上下文: {len(context)} 字符")
        print()

    answer = get_answer(question, context, use_local)
    if answer:
        print(answer)
    else:
        print("⚠️  回答生成失败")


# ========================= CLI =========================


def main():
    parser = argparse.ArgumentParser(
        description="AI Agent PM 学习伴侣 — 基于课程内容的问答 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                             # 交互模式（API）
  %(prog)s "什么是 Agent"               # 单次问答
  %(prog)s --local                      # 交互模式（本地 Ollama）
  %(prog)s -l "RAG 是什么"               # 本地单次问答
  %(prog)s --days 3 "评估体系"           # 只看最近 3 天
  %(prog)s --all "商业化模式"            # 查看所有缓存
  %(prog)s --local --days 1             # 本地交互 + 只看今天
        """,
    )
    parser.add_argument("question", nargs="?",
                        help="单次问答模式的问题（省略则进入交互模式）")
    parser.add_argument("-l", "--local", action="store_true",
                        help="使用本地 Ollama 模型（qwen3:32b）")
    parser.add_argument("--days", type=int, default=DEFAULT_RECENT_DAYS,
                        help=f"只看最近 N 天的内容（默认 {DEFAULT_RECENT_DAYS}）")
    parser.add_argument("--all", action="store_true",
                        help="使用所有缓存内容（不限天数）")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示详细信息（加载的缓存数、上下文大小等）")

    args = parser.parse_args()

    recent_days = None if args.all else args.days

    if args.question:
        single_shot(args.question, use_local=args.local,
                    recent_days=recent_days, verbose=args.verbose)
    else:
        interactive_loop(use_local=args.local, recent_days=recent_days)


if __name__ == "__main__":
    main()
