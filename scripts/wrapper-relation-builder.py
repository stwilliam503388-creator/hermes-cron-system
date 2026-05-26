#!/usr/bin/env python3
"""Wrapper: 运行 vault_relation_builder.py（概念关联图谱）"""
import os
import sys
import subprocess

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
SCRIPT = os.path.join(SCRIPTS_DIR, "vault_relation_builder.py")

if not os.path.isfile(SCRIPT):
    print(f"❌ 脚本不存在: {SCRIPT}")
    sys.exit(1)

if "OBSIDIAN_VAULT_PATH" not in os.environ:
    os.environ["OBSIDIAN_VAULT_PATH"] = (
        "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
    )

result = subprocess.run(
    [sys.executable, SCRIPT] + sys.argv[1:],
    capture_output=True, text=True, timeout=120,
)

print(result.stdout, end="")
if result.returncode != 0:
    if result.stderr:
        print(result.stderr, end="")
    sys.exit(result.returncode)
