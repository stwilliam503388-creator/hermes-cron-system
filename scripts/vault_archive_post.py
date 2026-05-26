#!/usr/bin/env python3
"""
归档后处理流水线 — vault_archive_post.py
用法：
  python3 vault_archive_post.py                          # 处理今天归档
  python3 vault_archive_post.py 对话归档/2026-05-16.md    # 处理指定文件
  python3 vault_archive_post.py --all                     # 全量（索引同步 + 全量 autolink）
"""
import sys
import subprocess
from pathlib import Path
from datetime import datetime

SCRIPTS = Path("/Users/liuwei/.hermes/scripts")
VAULT = os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"  → {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          encoding='utf-8', errors='replace')


def main():
    args = sys.argv[1:]

    # Step 1: 索引同步
    print("[1/2] 同步对话归档索引...")
    r = run(["python3", str(SCRIPTS / "vault_index_sync.py")])
    print(r.stdout.rstrip())
    if r.stderr:
        print(r.stderr.rstrip())

    # Step 2: 定向补链
    if "--all" in args:
        print("\n[2/2] 全量 autolink...")
        r = run(["python3", str(SCRIPTS / "vault_autolink.py"), "--dry-run"])
    elif args:
        targets = [a for a in args if not a.startswith("--")]
        if targets:
            print(f"\n[2/2] 定向 autolink ({len(targets)} 文件)...")
            for t in targets:
                r = run(["python3", str(SCRIPTS / "vault_autolink.py"), "--target", t, "--dry-run"])
                print(r.stdout.rstrip())
                if r.stderr:
                    print(r.stderr.rstrip())
        else:
            print("\n[2/2] 跳过 autolink（无目标文件）")
    else:
        # 默认：今天归档
        today = datetime.now().strftime("%Y-%m-%d")
        target = f"对话归档/{today}.md"
        today_path = VAULT / target
        if today_path.exists():
            print(f"\n[2/2] 定向 autolink (今天归档)...")
            r = run(["python3", str(SCRIPTS / "vault_autolink.py"), "--target", target, "--dry-run"])
            print(r.stdout.rstrip())
        else:
            print(f"\n[2/2] 跳过 autolink（{target} 不存在）")

    print("\n✅ 归档后处理完成")


if __name__ == "__main__":
    main()
