#!/usr/bin/env python3
"""Wrapper: 执行 vault_concept_extract.py（全量萃取）+ 广播输出到邮箱"""
import subprocess, sys, os
from pathlib import Path

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
SCRIPT = os.path.join(SCRIPTS_DIR, "vault_concept_extract.py")

# 确保 OBSIDIAN_VAULT_PATH 存在
if "OBSIDIAN_VAULT_PATH" not in os.environ:
    os.environ["OBSIDIAN_VAULT_PATH"] = (
        "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
    )

result = subprocess.run(
    [sys.executable, SCRIPT, *sys.argv[1:]],
    capture_output=True, text=True
)
output = (result.stdout + result.stderr).strip()
print(output, end="")

if output:
    subprocess.run([
        sys.executable, os.path.join(SCRIPTS_DIR, "email-broadcast.py"),
        "概念自动萃取", "-m", output[:50000]
    ])

sys.exit(result.returncode)
