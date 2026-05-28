#!/usr/bin/env python3
"""notebooklm-session-keepalive.py — 每 6 小时刷新 NotebookLM session (v2)

改进:
  - 使用 persistent_context（全浏览器状态，更持久）
  - 过期时直接报警（而非静默失败）
  - 记录最后成功刷新时间，供上传脚本参考

用法: python3 notebooklm-session-keepalive.py
退出码: 0=正常, 1=session 过期需手动登录
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

SESSION_DIR = Path("/Users/liuwei/.hermes/notebooklm_session")
CONTEXT_FILE = SESSION_DIR / "context.zip"
PERSISTENT_DIR = SESSION_DIR / "persistent_browser"
STATE_FILE = SESSION_DIR / "keepalive_state.json"


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def main():
    state = load_state()

    if not CONTEXT_FILE.exists():
        print("❌ context.zip 不存在，需手动登录")
        sys.exit(1)

    age_h = (datetime.now() - datetime.fromtimestamp(CONTEXT_FILE.stat().st_mtime)).total_seconds() / 3600
    print(f"📋 context.zip 年龄: {age_h:.0f}h")

    # 如果距离上次成功刷新 < 4h，跳过（避免过于频繁）
    last_ok = state.get("last_successful_refresh")
    if last_ok:
        last_dt = datetime.fromisoformat(last_ok)
        since_ok = (datetime.now() - last_dt).total_seconds() / 3600
        if since_ok < 4:
            print(f"⏭️  上次成功刷新在 {since_ok:.1f}h 前，跳过（<4h 阈值）")
            sys.exit(0)

    from playwright.sync_api import sync_playwright

    PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # v2: 使用 persistent context（全浏览器状态，更持久）
        browser_ref = None
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PERSISTENT_DIR),
                channel="chrome",
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
                viewport={"width": 1280, "height": 800},
            )
        except Exception as e:
            print(f"⚠️  persistent context 创建失败: {e}")
            # 降级：使用普通 context + storage_state
            browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                storage_state=str(CONTEXT_FILE) if CONTEXT_FILE.exists() else None,
                viewport={"width": 1280, "height": 800},
            )
            browser_ref = browser

        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            page.goto("https://notebooklm.google.com", timeout=30000, wait_until="commit")
            page.wait_for_timeout(5000)

            if "accounts.google.com" in page.url:
                print("❌ Session 已过期（被 Google 重定向到登录页）")
                state["last_check"] = datetime.now().isoformat()
                state["status"] = "expired"
                state["expired_since"] = state.get("expired_since") or datetime.now().isoformat()
                save_state(state)
                context.close()
                if browser_ref:
                    browser_ref.close()
                sys.exit(1)

            # Session 有效 — 保存 storage state
            context.storage_state(path=str(CONTEXT_FILE))
            context.close()
            if browser_ref:
                browser_ref.close()

            new_age = (datetime.now() - datetime.fromtimestamp(CONTEXT_FILE.stat().st_mtime)).total_seconds() / 3600
            print(f"✅ Session 有效，已刷新（年龄: {new_age:.0f}h）")

            state["last_successful_refresh"] = datetime.now().isoformat()
            state["last_check"] = datetime.now().isoformat()
            state["status"] = "ok"
            state.pop("expired_since", None)
            save_state(state)

        except Exception as e:
            context.close()
            if browser_ref:
                browser_ref.close()
            print(f"⚠️  刷新异常: {e}")
            state["last_check"] = datetime.now().isoformat()
            state["last_error"] = str(e)[:200]
            save_state(state)
            sys.exit(1)


if __name__ == "__main__":
    main()
