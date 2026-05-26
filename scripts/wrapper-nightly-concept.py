#!/usr/bin/env python3
"""
wrapper-nightly-concept.py — 夜间概念知识库维护（去重 → 润色）
- 先执行概念去重检测
- 成功后再执行 LLM 润色（需联网）
- 离线时润色跳过，去重仍然执行
- 汇总结果通过邮件广播
"""
import os
import subprocess
import sys
from datetime import datetime

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
VAULT_PATH = "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"

NETWORK_TEST = [
    "curl", "-s", "--connect-timeout", "5", "--max-time", "8",
    "https://www.baidu.com", "-o", "/dev/null", "-w", "%{http_code}"
]


def check_network() -> bool:
    try:
        r = subprocess.run(NETWORK_TEST, capture_output=True, text=True, timeout=15,
                          encoding='utf-8', errors='replace')
        code = r.stdout.strip()
        return code == "200" or code.startswith("3") or code.startswith("2")
    except Exception:
        return False


def run_script(script_name: str, args: list = None) -> tuple[int, str]:
    """Run a Python script and return (returncode, combined_output)."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    env = os.environ.copy()
    env.setdefault("OBSIDIAN_VAULT_PATH", VAULT_PATH)

    r = subprocess.run(
        [sys.executable, script_path] + (args or []),
        capture_output=True, text=True, timeout=600, env=env
    )
    output = (r.stdout + r.stderr).strip()
    return r.returncode, output


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== 夜间概念知识库维护 [{timestamp}] ===")
    print(f"Vault: {VAULT_PATH}")
    print()

    all_output = []

    # ── 阶段 1：概念去重检测（不需要联网） ──
    print("📊 阶段 1/2：概念去重检测...")
    rc1, out1 = run_script("vault_concept_dedup.py")
    all_output.append(f"── 概念去重检测 ──\n{out1}")

    if rc1 != 0:
        print(f"❌ 概念去重失败 (exit={rc1})，终止后续步骤")
        all_output.append("\n⚠️ 去重失败，LLM 润色已跳过")
    else:
        print(f"✅ 概念去重完成")
        dedup_success = "0 组重复" not in out1  # rough heuristic

        # ── 阶段 2：概念卡片 LLM 润色（需要联网） ──
        print()
        if check_network():
            print("🌐 阶段 2/2：概念卡片 LLM 润色...")
            rc2, out2 = run_script("vault_llm_polish.py", ["--max-cards", "5"])
            all_output.append(f"\n── LLM 润色 ──\n{out2}")
            if rc2 == 0:
                print(f"✅ LLM 润色完成")
            else:
                print(f"⚠️ LLM 润色部分失败 (exit={rc2})")
        else:
            msg = "⚠️ 网络不可用，LLM 润色跳过"
            print(msg)
            all_output.append(f"\n{msg}")

    # ── 汇总输出 ──
    combined = "\n".join(all_output)
    print()
    print(combined)

    # ── 邮件广播 ──
    if combined.strip():
        try:
            subprocess.run([
                sys.executable,
                os.path.join(SCRIPTS_DIR, "email-broadcast.py"),
                "夜间概念知识库维护",
                "-m", combined[:50000]
            ], timeout=30)
        except Exception as e:
            print(f"邮件发送失败: {e}", file=sys.stderr)

    return 0  # always exit 0 — don't block cron chain


if __name__ == "__main__":
    sys.exit(main())
