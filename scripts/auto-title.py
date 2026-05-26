#!/usr/bin/env python3
"""
自动生成 Hermes 会话标题
用法: python3 ~/.hermes/scripts/auto-title.py [session_id]
      不传 session_id 则处理最近的无标题会话
"""

import json, os, sys, sqlite3, subprocess, ssl, urllib.request

SESSIONS_DIR = os.path.expanduser("~/.hermes/sessions")
STATE_DB = os.path.expanduser("~/.hermes/state.db")
HERMES_BIN = "hermes"


def get_llm_config():
    """优先用 DeepSeek（云端，不受本地代理影响），不可用时尝试 Ollama"""
    # 先从环境变量读取，再从 .env 文件读取
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        env_file = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_file):
            for line in open(env_file):
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip('\'"')
                    break
    if api_key:
        return {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": api_key,
            "model": "deepseek-chat",
        }

    # 回退 Ollama
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        resp = urllib.request.urlopen(req, timeout=2)
        if resp.status == 200:
            return {
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "api_key": "ollama",
                "model": "qwen2.5-coder:14b",
            }
    except:
        pass

    print("❌ 无可用的 LLM（无 DEEPSEEK_API_KEY 且 Ollama 不可达）")
    sys.exit(1)


def api_call(config: dict, payload: dict, timeout=30) -> dict:
    """调用 LLM API，绕过系统代理"""
    data = json.dumps(payload).encode()
    url = f"{config['base_url']}/chat/completions"

    # ProxyHandler({}) = 不走任何代理
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
    )
    resp = opener.open(req, timeout=timeout)
    return json.loads(resp.read())


def extract_context(session_path: str) -> str:
    """从 session 文件中提取前几条用户消息"""
    with open(session_path) as f:
        session = json.load(f)

    user_msgs = []
    for msg in session.get("messages", []):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
                )
            content = content.strip()
            if content:
                user_msgs.append(content[:200])
        if len(user_msgs) >= 3:
            break

    return "\n".join(f"- {m}" for m in user_msgs)


def generate_title(context: str, config: dict) -> str:
    """调用 LLM 生成中文标题"""
    prompt = (
        "根据以下对话开头，生成一个简短的中文标题（8-20字），用于后续恢复会话。\n"
        "只输出标题本身，不要引号、不要解释。\n\n"
        f"对话内容：\n{context}\n\n标题："
    )

    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 30,
        "temperature": 0.3,
    }

    result = api_call(config, payload)
    title = result["choices"][0]["message"]["content"].strip()
    title = title.strip("'\"\"'\n ").replace("\n", " ")
    return title[:30]  # 截断


def find_untitled_sessions() -> list:
    """从 state.db 查询无标题会话，匹配对应的 JSON 文件"""
    conn = sqlite3.connect(STATE_DB)
    cur = conn.execute(
        "SELECT id FROM sessions "
        "WHERE title IS NULL OR title = '' "
        "ORDER BY started_at DESC LIMIT 10"
    )
    untitled = []
    for (sid,) in cur.fetchall():
        path = os.path.join(SESSIONS_DIR, f"session_{sid}.json")
        if os.path.exists(path):
            untitled.append((sid, path))
    conn.close()
    return untitled


def main():
    if len(sys.argv) > 1:
        sid = sys.argv[1]
        path = os.path.join(SESSIONS_DIR, f"session_{sid}.json")
        if not os.path.exists(path):
            print(f"❌ Session 文件不存在: {path}")
            sys.exit(1)
        targets = [(sid, path)]
    else:
        targets = find_untitled_sessions()
        if not targets:
            print("✅ 所有会话已有标题")
            return

    print(f"📋 待处理: {len(targets)} 个无标题会话")

    config = get_llm_config()
    print(f"🤖 使用: {config['provider']}/{config['model']}")

    for sid, path in targets:
        print(f"\n── {sid[:20]}... ──")
        try:
            context = extract_context(path)
            if not context.strip():
                print("  ⚠️  无用户消息，跳过")
                continue

            title = generate_title(context, config)

            print(f"  上下文预览: {context[:120]}")
            print(f"  生成标题: {title}")

            result = subprocess.run(
                [HERMES_BIN, "sessions", "rename", sid, title],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                print(f"  ✅ 已设置")
            else:
                print(f"  ❌ 失败: {result.stderr.strip()}")

        except Exception as e:
            print(f"  ❌ 错误: {e}")


if __name__ == "__main__":
    main()
