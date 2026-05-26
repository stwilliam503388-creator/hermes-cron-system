#!/usr/bin/env python3
"""自动知乎登录 — 弹浏览器窗口，自动检测登录完成后保存 cookie，无需手动按键。"""
import json, os, sys, time

# Ensure playwright importable from both possible locations
_site_packages = [
    "/Users/liuwei/Library/Python/3.9/lib/python/site-packages",
    "/Users/liuwei/.hermes/profiles/minimal/home/Library/Python/3.9/lib/python/site-packages",
]
for sp in _site_packages:
    if sp not in sys.path and os.path.isdir(sp):
        sys.path.insert(0, sp)

from playwright.sync_api import sync_playwright

COOKIE_FILE = "/Users/liuwei/.hermes/zhihu_session.json"

def main():
    print("正在启动浏览器，请在弹出的窗口中扫码或密码登录知乎...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.goto("https://www.zhihu.com/signin", wait_until="domcontentloaded")

        # Auto-detect login completion: wait up to 5 minutes for URL to leave signin page
        print("等待登录完成（最长等待 5 分钟）...")
        try:
            page.wait_for_url(
                lambda url: "signin" not in url,
                timeout=300_000  # 5 minutes
            )
            print("检测到登录完成！")
        except Exception:
            print("\n⏰ 登录超时（5 分钟），请检查是否成功登录。")
            # Check if we're already past signin despite timeout
            if "signin" in page.url:
                browser.close()
                print("❌ 未检测到登录，请重试。")
                sys.exit(1)

        # Give cookies time to settle
        time.sleep(3)

        # Extract ALL cookies including HttpOnly
        all_cookies = ctx.cookies()
        cookies = {}
        for c in all_cookies:
            if "zhihu" in c.get("domain", ""):
                cookies[c["name"]] = c["value"]

        browser.close()

        # Verify we got the key auth cookie
        has_zc0 = "z_c0" in cookies
        total = len(cookies)

        if not cookies:
            print("❌ 未提取到任何 cookie。")
            sys.exit(1)

        print(f"\n提取到 {total} 个 cookie")
        for k in ["z_c0", "d_c0", "SESSIONID", "_xsrf"]:
            print(f"  {'✅' if k in cookies else '❌'} {k}")

        if not has_zc0:
            print("\n⚠️  缺少关键 cookie z_c0，可能抓取会失败。")

        # Save
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "cookies": cookies,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "note": "Zhihu session cookies (including HttpOnly).",
            }, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Cookie 已保存到 {COOKIE_FILE}")
        print("现在通过微信发送知乎链接即可自动抓取！")

if __name__ == "__main__":
    main()
