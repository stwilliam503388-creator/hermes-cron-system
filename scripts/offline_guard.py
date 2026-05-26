#!/usr/bin/env python3
"""
offline_guard.py — 断网恢复守卫

用法:
  python3 offline_guard.py <job_name> <script_path> [args...]

行为:
  1. 测试网络连通性（curl baidu.com）
  2. 在线 → 运行目标脚本
  3. 离线 → 调用本地 ollama (qwen3:32b) 记录上下文
           → 写入失败任务状态文件 ~/.hermes/scripts/.failed_jobs.json
           → 退出 0（不中断 cron 链）

状态文件格式 (failed_jobs.json):
  [
    {"job": "...", "script": "...", "offline_at": "...",
     "summary": "本地 ollama 生成的摘要",
     "online_at": null, "retried": false}
  ]

恢复:
  offline_guard.py --recover  # 重试所有未恢复的失败任务
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path("/Users/liuwei/.hermes/scripts/.failed_jobs.json")
NETWORK_TEST = ["curl", "-s", "--connect-timeout", "5", "--max-time", "8",
                "https://www.baidu.com", "-o", "/dev/null", "-w", "%{http_code}"]
OLLAMA_CMD = ["ollama", "run", "qwen3:32b"]
SCRIPTS_DIR = Path("/Users/liuwei/.hermes/scripts")


def check_network() -> bool:
    """检测网络连通性。返回 True=在线"""
    try:
        result = subprocess.run(NETWORK_TEST, capture_output=True, text=True, timeout=15,
                                encoding='utf-8', errors='replace')
        code = result.stdout.strip()
        return code == "200" or code.startswith("3") or code.startswith("2")
    except Exception:
        return False


def ollama_summary(job_name: str, script: str) -> str:
    """用本地 ollama 生成离线摘要"""
    prompt = (
        f"你是一个任务状态记录器。以下任务因网络不可用被跳过，请用中文简要记录：\n"
        f"任务名称: {job_name}\n"
        f"脚本: {script}\n"
        f"跳过时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"请输出一句中文摘要（50字以内），说明该任务已被跳过。"
    )
    try:
        result = subprocess.run(
            OLLAMA_CMD + [prompt],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace',
        )
        return result.stdout.strip()[:200] if result.stdout.strip() else "离线跳过，无 ollama 摘要"
    except Exception as e:
        return f"离线跳过（ollama 调用失败: {e})"


def load_state() -> list:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_state(state: list):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def run_script(script_path: str, args: list) -> int:
    """运行目标脚本"""
    env = os.environ.copy()
    if "OBSIDIAN_VAULT_PATH" not in env:
        env["OBSIDIAN_VAULT_PATH"] = (
            "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
        )
    result = subprocess.run(
        [sys.executable, script_path] + args,
        capture_output=True, text=True, timeout=300,
        encoding='utf-8', errors='replace',
        env=env,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def do_offline(job_name: str, script: str):
    """离线处理：ollama 记录 + 状态文件"""
    summary = ollama_summary(job_name, script)
    print(f"⚠️  网络不可用，任务 '{job_name}' 已跳过")
    print(f"📝  本地记录: {summary}")

    state = load_state()
    state.append({
        "job": job_name,
        "script": script,
        "offline_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "online_at": None,
        "retried": False,
    })
    save_state(state)
    return 0


def do_recover():
    """恢复模式：重试所有未恢复的任务"""
    state = load_state()
    pending = [s for s in state if not s.get("retried")]

    if not pending:
        print("✅ 无待恢复任务")
        return 0

    network = check_network()
    if not network:
        print(f"⚠️  网络仍不可用，{len(pending)} 个待恢复任务无法执行")
        return 1

    recovered = 0
    failed = 0
    for entry in pending:
        print(f"🔄 恢复: {entry['job']} ({entry['script']})")
        script_path = SCRIPTS_DIR / entry["script"]
        if not script_path.exists():
            script_path = Path(entry["script"])
        if not script_path.exists():
            print(f"  ❌ 脚本不存在: {entry['script']}")
            entry["retried"] = False  # keep for next attempt
            failed += 1
            continue

        rc = run_script(str(script_path), [])
        if rc == 0:
            entry["online_at"] = datetime.now(timezone.utc).isoformat()
            entry["retried"] = True
            recovered += 1
            print(f"  ✅ 恢复成功")
        else:
            print(f"  ⚠️  恢复失败（退出码 {rc}），下次再试")
            failed += 1

    save_state(state)
    print(f"\n📊 恢复统计: {recovered} 成功, {failed} 失败")
    return 0 if failed == 0 else 1


def main():
    # 恢复模式
    if len(sys.argv) >= 2 and sys.argv[1] == "--recover":
        return do_recover()

    # 查看状态
    if len(sys.argv) >= 2 and sys.argv[1] == "--status":
        state = load_state()
        pending = [s for s in state if not s.get("retried")]
        total = len(state)
        print(f"📋 失败任务记录: {total} 条")
        print(f"   ├─ 待恢复: {len(pending)} 条")
        print(f"   └─ 已恢复: {total - len(pending)} 条")
        for s in state:
            status = "✅" if s.get("retried") else "⏳"
            print(f"  {status} {s['job']} ({s['offline_at'][:19]})")
            if not s.get("retried"):
                print(f"     → {s['summary']}")
        return 0

    # 正常守卫模式
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    job_name = sys.argv[1]
    script_rel = sys.argv[2]
    script_args = sys.argv[3:]

    # 解析脚本路径
    script_path = SCRIPTS_DIR / script_rel
    if not script_path.exists():
        script_path = Path(script_rel)
    if not script_path.exists():
        print(f"❌ 脚本不存在: {script_rel}")
        return 1

    # 检测网络
    if check_network():
        print(f"🌐 网络在线，运行 {job_name}")
        return run_script(str(script_path), script_args)
    else:
        # 离线：对流主线任务（如概念萃取）仍尝试运行
        # 只有需要 API 调用的任务才跳过
        api_dependent = ["vault_llm_polish", "llm-polish", "llm"]
        is_api_task = any(term in script_rel.lower() for term in api_dependent)

        if is_api_task:
            return do_offline(job_name, script_rel)
        else:
            print(f"🌐 网络不可用，但任务 '{job_name}' 不需要 API，尝试运行")
            return run_script(str(script_path), script_args)


if __name__ == "__main__":
    sys.exit(main())
