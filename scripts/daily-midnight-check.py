#!/usr/bin/env python3
"""
daily-midnight-check.py — 每日 00:10 自检脚本
功能：
  1. NotebookLM 同步状态检查，需要时触发同步
  2. 检查从未运行/上次报错的任务，自动重试

用法: python3 daily-midnight-check.py [--dry-run]
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── 路径常量 ──
HOME = "/Users/liuwei"  # 硬编码，因为 cron 环境 $HOME 指向 profile
SCRIPTS_DIR = f"{HOME}/.hermes/scripts"
PROFILE_JOBS = f"{HOME}/.hermes/profiles/minimal/cron/jobs.json"
NOTEBOOKLM_STATE = f"{HOME}/.hermes/notebooklm_session/sync_state.json"
NOTEBOOKLM_VENV = f"{HOME}/.hermes/notebooklm_venv/bin/python"
HERMES_CLI = f"{HOME}/.local/bin/hermes"

DRY_RUN = "--dry-run" in sys.argv

errors = []


def log(msg):
    print(f"  {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def warn(msg):
    print(f"  ⚠️  {msg}")


def fail(msg):
    print(f"  ❌ {msg}")
    errors.append(msg)


def run_cmd(cmd, timeout=300, retries=1):
    """执行命令，支持重试"""
    last_err = ""
    for attempt in range(1, retries + 2):
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace'
            )
            if r.returncode == 0:
                return True, r.stdout
            last_err = r.stderr[-300:] or r.stdout[-300:]
        except subprocess.TimeoutExpired:
            last_err = f"超时 ({timeout}s)"
        except Exception as e:
            last_err = str(e)

        if attempt <= retries:
            log(f"  重试 {attempt}/{retries}...")
            time.sleep(5)
    return False, last_err


# ══════════════════════════════════════
#  1. NotebookLM 同步状态检查
# ══════════════════════════════════════
def check_notebooklm():
    print("\n──────────────────────────────────────")
    print("📋 1. NotebookLM 同步状态检查")
    print("──────────────────────────────────────")

    if DRY_RUN:
        log("[DRY RUN] 跳过实际检查")
        return False

    state_file = Path(NOTEBOOKLM_STATE)
    if not state_file.exists():
        warn(f"sync_state.json 不存在: {NOTEBOOKLM_STATE}")
        return True

    with open(state_file) as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError:
            fail("sync_state.json 解析失败")
            return True

    last_sync = state.get("last_sync", "")
    uploaded = len(state.get("uploaded_files", {}))
    notebooks = state.get("notebooks", [])

    log(f"已上传文件: {uploaded}")
    log(f"Notebook: {notebooks}")
    log(f"上次同步: {last_sync or '从未同步'}")

    if not last_sync:
        warn("从未同步过，需要同步")
        return True

    try:
        last_dt = datetime.fromisoformat(last_sync)
        hours_ago = (datetime.now() - last_dt).total_seconds() / 3600
        if hours_ago > 24:
            warn(f"上次同步超过 {hours_ago:.0f} 小时，需要同步")
            return True
        ok(f"同步正常（{hours_ago:.0f} 小时前）")
        return False
    except (ValueError, TypeError):
        warn(f"无法解析 last_sync: {last_sync}")
        return True


def trigger_notebooklm_sync():
    if DRY_RUN:
        log("[DRY RUN] 跳过 NotebookLM 同步")
        return

    log("触发 NotebookLM 同步...")
    ok, out = run_cmd(
        [NOTEBOOKLM_VENV, f"{SCRIPTS_DIR}/notebooklm-sync.py"],
        timeout=600,
        retries=1,
    )
    if ok:
        for line in out.split("\n"):
            if "成功" in line or "全部已是最新" in line:
                ok(line.strip())
                break
        else:
            log("同步执行完成（结果不明，请查看输出）")
    else:
        if "session 已过期" in out or "过期" in out:
            warn(f"Google session 已过期，需要手动登录")
        else:
            fail(f"同步失败: {out[:200]}")


# ══════════════════════════════════════
#  2. 失败/未运行任务重试
# ══════════════════════════════════════
def check_retry_jobs():
    print("\n──────────────────────────────────────")
    print("📋 2. 失败/未运行任务重试")
    print("──────────────────────────────────────")

    if DRY_RUN:
        log("[DRY RUN] 仅展示，不执行重试")

    jobs_file = Path(PROFILE_JOBS)
    if not jobs_file.exists():
        fail(f"jobs.json 不存在: {PROFILE_JOBS}")
        return 0

    with open(jobs_file) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            fail("jobs.json 解析失败")
            return 0

    jobs = data.get("jobs", [])
    log(f"共 {len(jobs)} 个任务")

    retry_count = 0
    MAX_RETRY = 5  # 每轮最多重试 5 个

    for j in jobs:
        if retry_count >= MAX_RETRY:
            warn(f"达到本轮重试上限 ({MAX_RETRY})，剩余跳过")
            break

        name = j.get("name", "?")
        uid = j.get("id", "?")
        last_status = j.get("last_status", "")
        last_run = j.get("last_run_at", "")
        no_agent = j.get("no_agent", False)
        script = j.get("script", "")
        enabled = j.get("enabled", True)

        if not enabled:
            continue

        # 判断是否需要重试
        reason = ""
        if not last_run:
            reason = "从未运行"
        elif last_status == "error":
            reason = f"上次报错 ({last_status})"
        elif last_status == "timeout":
            reason = f"上次超时 ({last_status})"
        else:
            continue

        log(f"  🔄 [{name}] — {reason}")

        if no_agent and script:
            # 脚本任务
            if script.startswith("/"):
                script_path = script
            else:
                script_path = f"{SCRIPTS_DIR}/{script}"

            if not os.path.isfile(script_path):
                warn(f"    脚本不存在: {script_path}，尝试 hermes cron run")
                if not DRY_RUN:
                    ok_flag, out = run_cmd(
                        [HERMES_CLI, "cron", "run", uid], timeout=600, retries=1
                    )
                    ok(f"    hermes cron run 触发成功" if ok_flag else f"    hermes cron run 失败: {out[:200]}")
                else:
                    log(f"    将执行: hermes cron run {uid}")
                retry_count += 1
                continue

            if DRY_RUN:
                log(f"    将执行: {script_path}")
                retry_count += 1
                continue

            # 实际执行
            if script_path.endswith(".sh"):
                cmd = ["bash", script_path]
            else:
                cmd = [sys.executable, script_path]

            ok_flag, out = run_cmd(cmd, timeout=300, retries=0)
            ok(f"    执行成功" if ok_flag else f"    执行失败: {out[:200]}")
            retry_count += 1

        else:
            # Agent 任务：用 hermes cron run 触发
            if DRY_RUN:
                log(f"    将执行: hermes cron run {uid}")
            else:
                ok_flag, out = run_cmd(
                    [HERMES_CLI, "cron", "run", uid], timeout=600, retries=1
                )
                ok(f"    hermes cron run 触发成功" if ok_flag else f"    hermes cron run 失败: {out[:200]}")
            retry_count += 1

    return retry_count


# ══════════════════════════════════════
#  3. 手工维护索引过期检测
# ══════════════════════════════════════
def check_index_staleness():
    """检查手工维护索引（工具笔记索引、Skills文档索引）是否过期"""
    print("\\n──────────────────────────────────────")
    print("📋 3. 手工维护索引过期检测")
    print("──────────────────────────────────────")

    VAULT = f"{HOME}/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
    INDEXES = {
        "🔧工具笔记索引": f"{VAULT}/工具笔记/🔧工具笔记索引.md",
        "🛠Skills文档索引": f"{VAULT}/工具笔记/skills/🛠Skills文档索引.md",
    }

    stale_count = 0
    for label, path in INDEXES.items():
        try:
            mtime = os.path.getmtime(path)
            age_hours = (time.time() - mtime) / 3600
            if age_hours > 48:
                warn(f"{label} 已 {age_hours:.0f} 小时未更新（阈值48h）")
                stale_count += 1
            elif age_hours > 24:
                warn(f"{label} 已 {age_hours:.0f} 小时未更新（建议24h内更新）")
            else:
                ok(f"{label} {age_hours:.0f}h 内更新正常")
        except FileNotFoundError:
            warn(f"{label} 文件不存在: {path}")
            stale_count += 1

    return stale_count


# ══════════════════════════════════════
#  Main
# ══════════════════════════════════════
if __name__ == "__main__":
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  凌晨统一自检 — {ts}")
    print(f"  凌晨统一自检 — {ts}")
    if DRY_RUN:
        print(f"  ⚠️  干运行模式（不变更任何状态）")
    print(f"{'=' * 56}")

    # 1. NotebookLM 同步状态检查
    need_sync = check_notebooklm()
    if need_sync:
        trigger_notebooklm_sync()

    # 2. 失败任务重试
    retried = check_retry_jobs()
    if retried == 0 and not DRY_RUN:
        ok("所有任务状态正常，无需要重试的任务")
    elif DRY_RUN:
        log(f"  (DRY RUN) 检测到 {retried} 个需要重试的任务")

    # 3. 过期索引检测（手工维护索引，仅供参考；自动维护由 run_vault_maintenance.sh 负责）
    check_index_staleness()

    print(f"\n{'─' * 56}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        print(f"  共 {len(errors)} 个问题")
        sys.exit(1)
    else:
        print("  ✅ 自检完成，无异常")
        sys.exit(0)
