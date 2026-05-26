#!/usr/bin/env python3
"""从已有临时 Chrome profile 中提取 NotebookLM session"""
import sys, time, os
from pathlib import Path

# Fix HOME for cron context (macOS only)
if os.environ.get("HOME", "").startswith("/Users/liuwei/.hermes/profiles/"):
    os.environ["HOME"] = "/Users/liuwei"

from playwright.sync_api import sync_playwright

SESSION_DIR = Path("/Users/liuwei/.hermes/notebooklm_session")
TEMP_PROFILE = SESSION_DIR / "temp_chrome_profile"
CONTEXT_FILE = SESSION_DIR / "context.zip"

print("═══ 从现有 Profile 提取 Session ═══")
print(f"Profile: {TEMP_PROFILE}")
print(f"Size: {sum(f.stat().st_size for f in TEMP_PROFILE.rglob('*') if f.is_file())} bytes")

with sync_playwright() as p:
    # 用已有 profile 启动 Chrome（会加载登录态）
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(TEMP_PROFILE),
        channel="chrome",
        headless=True,  # headless 验证
        args=["--disable-blink-features=AutomationControlled"],
        viewport={"width": 1280, "height": 800},
    )

    page = context.pages[0] if context.pages else context.new_page()
    print("→ 访问 NotebookLM...")
    page.goto("https://notebooklm.google.com", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    url = page.url
    if "accounts.google.com" in url:
        print("❌ Profile 中无有效 NotebookLM 登录态")
        print(f"   当前 URL: {url}")
        context.close()
        sys.exit(1)

    print(f"✅ 已登录: {url[:80]}...")

    # 保存 session
    context.storage_state(path=str(CONTEXT_FILE))
    sz = CONTEXT_FILE.stat().st_size
    print(f"✅ Session 已保存 ({sz} bytes)")
    context.close()

print("\n完成！")
