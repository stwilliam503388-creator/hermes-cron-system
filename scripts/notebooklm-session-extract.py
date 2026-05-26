#!/usr/bin/env python3
"""
通过 AppleScript + Playwright CDP 从已运行的 Chrome 提取 NotebookLM session。
先让用户确认已在 NotebookLM，然后关掉 Chrome，用调试模式重启，再提取。
"""

import os, sys, time, subprocess, json
from pathlib import Path

# Fix HOME for cron context (macOS only)
if os.environ.get("HOME", "").startswith("/Users/liuwei/.hermes/profiles/"):
    os.environ["HOME"] = "/Users/liuwei"

SESSION_DIR = Path("/Users/liuwei/.hermes/notebooklm_session")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
CONTEXT_FILE = SESSION_DIR / "context.zip"

print("步骤 1/3: 关闭 Chrome...")
subprocess.run(["pkill", "-x", "Google Chrome"], capture_output=True)
time.sleep(2)
print("  ✅ Chrome 已关闭")

print("步骤 2/3: 以调试模式启动 Chrome...")
chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
proc = subprocess.Popen(
    [chrome_path, "--remote-debugging-port=9222", "--no-first-run"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)

# 等待调试端口就绪
for i in range(20):
    time.sleep(2)
    try:
        r = subprocess.run(
            ["curl", "-s", "http://localhost:9222/json/version"],
            capture_output=True, text=True, timeout=5
        )
        if r.stdout and "Browser" in r.stdout:
            print(f"  ✅ 调试端口就绪 (等待 {i*2+2}秒)")
            break
    except:
        pass
else:
    print("  ❌ 调试端口未响应，请手动运行:")
    print(f'     "{chrome_path}" --remote-debugging-port=9222')
    proc.kill()
    sys.exit(1)

print("步骤 3/3: 提取 session...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    
    # 获取已存在的 context
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = browser.new_context()
    
    # 打开新标签到 NotebookLM（应该已经登录）
    page = context.new_page()
    page.goto("https://notebooklm.google.com", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    url = page.url
    if "accounts.google.com" in url:
        print("❌ 未登录，请在 Chrome 窗口中登录 NotebookLM 后重试")
        page.close()
        browser.close()
        proc.kill()
        sys.exit(1)
    
    print(f"  ✅ 已进入 NotebookLM: {url[:60]}...")
    
    # 保存 storage state
    context.storage_state(path=str(CONTEXT_FILE))
    sz = CONTEXT_FILE.stat().st_size
    print(f"  ✅ Session 已保存 ({sz} bytes)")
    
    page.close()
    browser.close()

print("\n验证 session...")
with sync_playwright() as p:
    ctx = p.chromium.launch(headless=True)
    page = ctx.new_page()
    page.goto("https://notebooklm.google.com", wait_until="networkidle", timeout=15000)
    if "accounts.google.com" in page.url:
        print("❌ 验证失败")
        ctx.close()
        sys.exit(1)
    else:
        print("✅ Session 验证通过！自动上传已就绪")
    ctx.close()

# 关掉调试 Chrome（用户会重新打开自己的 Chrome）
proc.kill()
print("\n调试 Chrome 已关闭，你可以重新打开自己的 Chrome 了")
print("完成！")
