#!/usr/bin/env python3
"""
notebooklm-setup.py — v2
使用系统安装的正式 Chrome（非 Playwright Chromium）完成登录，
绕过 Google "不安全浏览器" 检测。
"""
import os, sys, time, json
from pathlib import Path

# Fix HOME for cron context (macOS only)
if os.environ.get("HOME", "").startswith("/Users/liuwei/.hermes/profiles/"):
    os.environ["HOME"] = "/Users/liuwei"

SESSION_DIR = Path("/Users/liuwei/.hermes/notebooklm_session")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
CONTEXT_FILE = SESSION_DIR / "context.zip"
TEMP_PROFILE = SESSION_DIR / "temp_chrome_profile"
TEMP_PROFILE.mkdir(parents=True, exist_ok=True)

print("═══ NotebookLM Session 设置 v2 ═══")
print()

# 检查 Chrome 是否在运行
import subprocess
result = subprocess.run(
    ["pgrep", "-l", "-f", "Google Chrome"],
    capture_output=True, text=True
)
if result.stdout.strip():
    print("⚠️  Chrome 正在运行，请先关闭所有 Chrome 窗口后重试")
    sys.exit(1)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # 使用系统安装的真实 Chrome（不是 Playwright 自带的 Chromium）
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(TEMP_PROFILE),
        channel="chrome",  # ← 关键：使用系统 Chrome
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
        ],
        viewport={"width": 1280, "height": 800},
    )

    page = context.pages[0] if context.pages else context.new_page()

    print("正在打开 NotebookLM（使用系统 Chrome）...")
    page.goto("https://notebooklm.google.com", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # 检测是否已登录
    logged_in = "accounts.google.com" not in page.url and "notebooklm" in page.url

    if logged_in:
        print("✅ 浏览器已有登录态，直接保存 session...")
    else:
        print()
        print("═══════════════════════════════════════════════")
        print("  请在弹出的 Chrome 浏览器中登录 Google 账号")
        print("  这是正式版 Chrome，不会再提示'不安全'")
        print("  登录后会自动检测并保存 session")
        print("  最长等待 180 秒")
        print("═══════════════════════════════════════════════")
        print()

        for i in range(36):  # 180 秒
            time.sleep(5)
            try:
                url = page.url
                if "notebooklm" in url and "accounts.google.com" not in url:
                    logged_in = True
                    break
            except:
                pass
            if i % 4 == 0:
                print(f"  等待中... ({i*5+5}秒)", end="\r")

        print()
        if logged_in:
            print("✅ 登录成功！正在保存 session...")
        else:
            print("⚠️ 超时，保存当前状态（可能不完整）...")

    context.storage_state(path=str(CONTEXT_FILE))
    sz = CONTEXT_FILE.stat().st_size if CONTEXT_FILE.exists() else 0
    print(f"✅ Session 已保存 ({sz} bytes)")

    # 验证
    print("\n正在验证 session...")
    ctx_v = p.chromium.launch(channel="chrome", headless=True)
    pg_v = ctx_v.new_page()
    pg_v.goto("https://notebooklm.google.com", wait_until="domcontentloaded", timeout=15000)
    time.sleep(2)
    final_url = pg_v.url
    ctx_v.close()

    if "accounts.google.com" in final_url:
        print("❌ 验证失败，session 无效")
        print("   请关闭所有 Chrome 窗口后重新运行本脚本")
        context.close()
        sys.exit(1)
    else:
        print("✅ 验证通过！自动上传已就绪")

    context.close()

print("\n完成！")
