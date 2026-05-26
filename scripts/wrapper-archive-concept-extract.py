#!/usr/bin/env python3
"""Wrapper: 执行 vault_archive_concept_extract.py 并广播输出到邮箱"""
import subprocess, sys
from pathlib import Path

result = subprocess.run(
    [sys.executable, str(Path("/Users/liuwei/.hermes/scripts/vault_archive_concept_extract.py")), *sys.argv[1:]],
    capture_output=True, text=True
)
output = (result.stdout + result.stderr).strip()
print(output, end="")

if output:
    subprocess.run([
        sys.executable, str(Path("/Users/liuwei/.hermes/scripts/email-broadcast.py")),
        "对话归档概念萃取", "-m", output[:50000]
    ])

if result.returncode != 0:
    sys.exit(result.returncode)
