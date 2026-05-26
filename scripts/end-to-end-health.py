#!/usr/bin/env python3
"""end-to-end-health.py — 全链路健康测试

验证 5 个关键环节:
  1. Vault 可访问 + 近期有内容更新
  2. GitHub 备份同步状态
  3. NotebookLM session + 同步状态
  4. 投递队列健康
  5. Proxy 可用性（LLM API 连通）

用法: python3 end-to-end-health.py
退出码: 0=全部正常, 1=部分异常, 2=严重异常
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HOME = "/Users/liuwei"
VAULT = f"{HOME}/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
JOBS_FILE = f"{HOME}/.hermes/profiles/minimal/cron/jobs.json"
CONTEXT_ZIP = f"{HOME}/.hermes/notebooklm_session/context.zip"
SYNC_STATE = f"{HOME}/.hermes/notebooklm_session/sync_state.json"
QUEUE_PENDING = f"{HOME}/.hermes/delivery-queue/pending"

errors = []
warnings = []


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")
    warnings.append(msg)


def err(msg):
    print(f"  ❌ {msg}")
    errors.append(msg)


def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding='utf-8', errors='replace')
        return r.returncode == 0, r.stdout.strip()
    except Exception:
        return False, ""


# ══ 1. Vault 健康 ══
def check_vault():
    print("\n📂 1. Vault 可访问性")
    vault_p = Path(VAULT)
    if not vault_p.exists():
        err(f"Vault 路径不存在: {VAULT}")
        return
    ok(f"Vault 路径存在")

    # 检查最近 24h 内有新文件
    recent = []
    cutoff = time.time() - 86400
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('.obsidian', '.git', '.trash')]
        for f in files:
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                try:
                    if os.path.getmtime(fp) > cutoff:
                        recent.append(os.path.relpath(fp, VAULT))
                except OSError:
                    pass
    if recent:
        ok(f"近 24h 有 {len(recent)} 篇笔记更新（最新: {recent[0]}）")
    else:
        warn("近 24h 无笔记更新")


# ══ 2. GitHub 备份 ══
def check_git():
    print("\n🔄 2. GitHub 备份同步")
    vault_p = Path(VAULT)
    git_dir = vault_p / ".git"
    if not git_dir.exists():
        err("Vault 不是 git 仓库")
        return

    # 检查最近 git log
    success, out = run(["git", "-C", VAULT, "log", "--oneline", "-1"], timeout=10)
    if success and out:
        ok(f"最新 commit: {out}")
    else:
        err("无法读取 git log")

    # 检查本地是否有未推送的 commit
    success, out = run(["git", "-C", VAULT, "log", "--oneline", "origin/main..HEAD"], timeout=10)
    if success and out.strip():
        commits = len(out.strip().split("\n"))
        warn(f"有 {commits} 个未推送的 commit")
    elif success:
        ok("本地与远程同步")

    # 检查 stash
    success, out = run(["git", "-C", VAULT, "stash", "list"], timeout=10)
    if success and out.strip():
        warn(f"有未恢复的 git stash")


# ══ 3. NotebookLM ══
def check_notebooklm():
    print("\n🔐 3. NotebookLM 同步")

    ctx = Path(CONTEXT_ZIP)
    if not ctx.exists():
        err("context.zip 不存在，需手动登录")
        return

    age_h = (time.time() - ctx.stat().st_mtime) / 3600
    if age_h > 120:
        warn(f"session 过期 ({age_h:.0f}h，阈值 120h)")
    else:
        ok(f"session 有效 ({age_h:.0f}h)")

    state = Path(SYNC_STATE)
    if state.exists():
        try:
            with open(state) as f:
                d = json.load(f)
            last = d.get("last_sync", "")
            files = len(d.get("uploaded_files", {}))
            if last:
                try:
                    dt = datetime.fromisoformat(last)
                    h = (datetime.now() - dt).total_seconds() / 3600
                    ok(f"上次同步: {h:.0f}h 前，{files} 个文件已上传")
                except (ValueError, TypeError):
                    ok(f"上次同步: {last}，{files} 个文件")
        except (json.JSONDecodeError, OSError):
            warn("sync_state.json 解析失败")
    else:
        warn("sync_state.json 不存在")


# ══ 4. 投递队列 ══
def check_delivery():
    print("\n📬 4. 投递队列")
    pending = Path(QUEUE_PENDING)
    p_count = len(list(pending.glob("*.txt"))) if pending.exists() else 0
    if p_count > 5:
        warn(f"投递队列积压: {p_count} 待发")
    else:
        ok(f"投递队列正常 ({p_count} 待发)")

    # 检查投递错误（从 jobs.json）
    jobs_file = Path(JOBS_FILE)
    if jobs_file.exists():
        try:
            with open(jobs_file) as f:
                data = json.load(f)
            jobs = data.get("jobs", [])
            delivery_errors = [j for j in jobs if j.get("last_delivery_error")]
            if delivery_errors:
                names = ", ".join(j["name"] for j in delivery_errors[:3])
                warn(f"{len(delivery_errors)} 个任务有投递错误 ({names}...)")
        except (json.JSONDecodeError, OSError):
            pass


# ══ 5. Proxy ══
def check_proxy():
    print("\n🌐 5. Proxy 可用性")
    success, code = run([
        "curl", "-s", "--connect-timeout", "5", "--max-time", "10",
        "--proxy", "http://127.0.0.1:7890",
        "https://api.deepseek.com/v1/models", "-o", "/dev/null", "-w", "%{http_code}"
    ], timeout=15)
    if success and (code.startswith("2") or code == "401"):
        ok(f"proxy OK (deepseek API: {code})")
    elif success:
        warn(f"proxy 通但 API 返回 {code}")
    else:
        err("proxy 不通，LLM 任务全部受影响")


# ══ Main ══
def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"🔍 全链路健康测试 — {ts}")
    print("=" * 50)

    check_vault()
    check_git()
    check_notebooklm()
    check_delivery()
    check_proxy()

    print(f"\n{'─' * 50}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        print(f"\n  {len(errors)} 个严重问题")
    if warnings:
        for w in warnings:
            print(f"  ⚠️  {w}")
        print(f"\n  {len(warnings)} 个警告")
    if not errors and not warnings:
        print("  ✅ 全链路正常")
    print(f"{'─' * 50}")

    if errors:
        sys.exit(1)
    elif warnings:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
