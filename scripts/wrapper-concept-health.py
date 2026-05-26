#!/usr/bin/env python3
"""Wrapper: 运行 vault_concept_health.py（概念卡健康巡检）"""
import os
import sys
import subprocess

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
SCRIPT = os.path.join(SCRIPTS_DIR, "vault_concept_health.py")

if not os.path.isfile(SCRIPT):
    print(f"❌ 脚本不存在: {SCRIPT}")
    sys.exit(1)

if "OBSIDIAN_VAULT_PATH" not in os.environ:
    os.environ["OBSIDIAN_VAULT_PATH"] = (
        "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
    )

result = subprocess.run(
    [sys.executable, SCRIPT] + sys.argv[1:],
    capture_output=True, text=True, timeout=30,
)

print(result.stdout, end="")
if result.returncode != 0:
    if result.stderr:
        print(result.stderr, end="")
    print(f"\n⚠️  健康巡检发现异常（退出码 {result.returncode}），详见上方报告")
# 始终 exit 0 — cron 调度器将非零退出码视为"任务失败"，
# 但这是一个诊断脚本，其报告本身就是输出结果
sys.exit(0)
