#!/usr/bin/env python3
"""daily-error-report.py — 每日 23:00 排查所有 cron 任务报错

读取 jobs.json，列出所有 last_status 为 error/timeout 的任务，
生成汇总报告。不做任何重试/修复操作——纯诊断。

用法: python3 daily-error-report.py
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = "/Users/liuwei"
JOBS_FILE = f"{HOME}/.hermes/profiles/minimal/cron/jobs.json"
QUEUE_DIR = f"{HOME}/.hermes/delivery-queue"


def load_jobs():
    jobs_file = Path(JOBS_FILE)
    if not jobs_file.exists():
        print(f"❌ jobs.json 不存在: {JOBS_FILE}")
        sys.exit(1)
    with open(jobs_file) as f:
        data = json.load(f)
    return data.get("jobs", [])


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"📊 每日定时任务错误排查 — {ts}")
    print("=" * 56)

    jobs = load_jobs()
    total = len(jobs)
    errored = [j for j in jobs if j.get("last_status") in ("error", "timeout")]
    enabled_errored = [j for j in errored if j.get("enabled", True)]
    disabled_errored = [j for j in errored if not j.get("enabled", True)]

    print(f"  总任务数: {total}")
    print(f"  报错任务: {len(errored)}（启用: {len(enabled_errored)}，禁用: {len(disabled_errored)}）")

    # ── 投递队列统计 ──
    pending_dir = Path(QUEUE_DIR, "pending")
    sent_dir = Path(QUEUE_DIR, "sent")
    pending_count = len(list(pending_dir.glob("*.txt"))) if pending_dir.exists() else 0
    sent_count = len(list(sent_dir.glob("*.txt"))) if sent_dir.exists() else 0

    # 投递异常统计
    delivery_errored = [j for j in jobs if j.get("last_delivery_error")]
    content_ok_delivery_fail = [j for j in delivery_errored if j.get("last_status") == "ok"]

    print(f"\n  📬 投递队列: {pending_count} 待发, {sent_count} 已发")
    if delivery_errored:
        print(f"  ⚠️  投递异常: {len(delivery_errored)} 个任务（其中 {len(content_ok_delivery_fail)} 个内容生成成功但投递失败）")

    # ── NotebookLM 同步状态 ──
    context_zip = Path(f"{HOME}/.hermes/notebooklm_session/context.zip")
    sync_state = Path(f"{HOME}/.hermes/notebooklm_session/sync_state.json")
    if context_zip.exists():
        age_h = (time.time() - context_zip.stat().st_mtime) / 3600
        print(f"  🔐 NotebookLM session: {age_h:.0f}h 前（{'⚠️ 已过期' if age_h > 120 else '✅ 有效'}）")
    else:
        print(f"  🔐 NotebookLM session: 不存在")
    if sync_state.exists():
        with open(sync_state) as f:
            try:
                state = json.load(f)
                last_sync = state.get("last_sync", "")
                if last_sync:
                    try:
                        last_dt = datetime.fromisoformat(last_sync)
                        sync_h = (datetime.now() - last_dt).total_seconds() / 3600
                        print(f"  📤 上次同步: {sync_h:.0f}h 前")
                    except (ValueError, TypeError):
                        print(f"  📤 上次同步: {last_sync}")
            except json.JSONDecodeError:
                pass

    if not enabled_errored:
        print("\n✅ 所有启用任务状态正常")
        return

    print(f"\n{'─' * 56}")
    print(f"⚠️  以下 {len(enabled_errored)} 个启用任务需要关注：")
    print(f"{'─' * 56}")

    for j in enabled_errored:
        name = j.get("name", "?")
        uid = j.get("id", "?")
        status = j.get("last_status", "?")
        last_run = j.get("last_run_at", "从未运行")
        schedule = j.get("schedule", {})
        expr = schedule.get("expr", "?") if isinstance(schedule, dict) else str(schedule)
        no_agent = j.get("no_agent", False)

        print(f"\n  🔴 [{name}]")
        print(f"     ID: {uid}")
        print(f"     状态: {status}")
        print(f"     上次运行: {last_run}")
        print(f"     调度: {expr}")
        print(f"     类型: {'脚本' if no_agent else 'Agent'}")

    if disabled_errored:
        print(f"\n📴 已禁用但仍报错的任务 ({len(disabled_errored)}):")
        for j in disabled_errored:
            print(f"  · {j.get('name', '?')}")


if __name__ == "__main__":
    main()
