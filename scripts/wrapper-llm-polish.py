#!/usr/bin/env python3
"""
wrapper-llm-polish.py — LLM 润色概念卡片（离线跳过）

行为:
  - 在线：正常调用 vault_llm_polish.py 润色卡片
  - 离线：输出警告，退出 0（不中断 cron 链）
  - 失败恢复由 daily-midnight-check.py 统一负责
"""
import os
import subprocess
import sys

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
SCRIPT_REL = "vault_llm_polish.py"

NETWORK_TEST = ["curl", "-s", "--connect-timeout", "5", "--max-time", "8",
                "https://www.baidu.com", "-o", "/dev/null", "-w", "%{http_code}"]


def check_network() -> bool:
    try:
        r = subprocess.run(NETWORK_TEST, capture_output=True, text=True, timeout=15,
                          encoding='utf-8', errors='replace')
        code = r.stdout.strip()
        return code == "200" or code.startswith("3") or code.startswith("2")
    except Exception:
        return False


def run_polish(args: list) -> int:
    script = os.path.join(SCRIPTS_DIR, SCRIPT_REL)
    env = os.environ.copy()
    if "OBSIDIAN_VAULT_PATH" not in env:
        env["OBSIDIAN_VAULT_PATH"] = (
            "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
        )
    r = subprocess.run(
        [sys.executable, script] + args,
        capture_output=True, text=True, timeout=900, env=env,
    )
    print(r.stdout, end="")
    if r.stderr and r.returncode != 0:
        print(r.stderr, end="")
    return r.returncode


def main():
    if check_network():
        print(f"🌐 网络在线，运行概念卡片LLM润色")
        return run_polish(sys.argv[1:] if len(sys.argv) > 1 else [])
    else:
        print(f"⚠️  网络不可用，概念卡片LLM润色跳过（不再记录到 .failed_jobs.json）")
        return 0


if __name__ == "__main__":
    sys.exit(main())
