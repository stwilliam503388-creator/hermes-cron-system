#!/usr/bin/env python3
"""Wrapper: 执行 vault_concept_dedup.py 并广播输出到邮箱"""
import subprocess, sys
from pathlib import Path

result = subprocess.run(
    [sys.executable, str(Path("/Users/liuwei/.hermes/scripts/vault_concept_dedup.py")), *sys.argv[1:]],
    capture_output=True, text=True
)
output = (result.stdout + result.stderr).strip()
print(output, end="")

if output:
    subprocess.run([
        sys.executable, str(Path("/Users/liuwei/.hermes/scripts/email-broadcast.py")),
        "概念去重检测", "-m", output[:50000]
    ])

if result.returncode != 0:
    sys.exit(result.returncode)
