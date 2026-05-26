#!/usr/bin/env python3
"""notebooklm-session-keepalive.py — 每日刷新 NotebookLM session

行为:
  1. 用 context.zip 打开 NotebookLM
  2. 如果 session 有效 → 保存刷新后的 storage state（cookie 续期 + 时间戳更新）
  3. 如果被 Google 重定向 → session 真的过期了 → 报警

用法: python3 notebooklm-session-keepalive.py
退出码: 0=正常, 1=session 过期
"""

import os
import sys
from datetime import datetime
from pathlib import Path

SESSION_DIR = Path("/Users/liuwei/.hermes/notebooklm_session")
CONTEXT_FILE = SESSION_DIR / "context.zip"


def main():
    if not CONTEXT_FILE.exists():
        print("❌ context.zip 不存在，需手动登录")
        sys.exit(1)

    age_h = (datetime.now() - datetime.fromtimestamp(CONTEXT_FILE.stat().st_mtime)).total_seconds() / 3600
    print(f"📋 context.zip 年龄: {age_h:.0f}h")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome", headless=True,
            args=["--no-sandbox"]
        )
        context = browser.new_context(
            storage_state=str(CONTEXT_FILE),
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            page.goto("https://notebooklm.google.com", timeout=30000, wait_until="commit")
            page.wait_for_timeout(3000)

            if "accounts.google.com" in page.url:
                browser.close()
                print("❌ Session 已过期（被 Google 重定向到登录页）")
                sys.exit(1)

            # Session 有效 — 保存刷新的 storage state
            context.storage_state(path=str(CONTEXT_FILE))
            browser.close()

            new_age = (datetime.now() - datetime.fromtimestamp(CONTEXT_FILE.stat().st_mtime)).total_seconds() / 3600
            print(f"✅ Session 有效，已刷新 context.zip（年龄: {new_age:.0f}h）")

        except Exception as e:
            browser.close()
            print(f"⚠️  刷新异常: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
