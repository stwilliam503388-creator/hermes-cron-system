#!/usr/bin/env python3
"""Use Playwright to log into Google NotebookLM via local Chrome."""
import sys
import asyncio
from playwright.async_api import async_playwright

EMAIL = "stwilliam503388@gmail.com"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            args=["--no-first-run", "--no-default-browser-check", "--start-maximized"]
        )
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("Navigating to NotebookLM...", flush=True)
        await page.goto("https://notebooklm.google.com", wait_until="networkidle")

        print("Waiting for email input...", flush=True)
        await page.wait_for_selector('input[type="email"]', timeout=15000)
        await page.fill('input[type="email"]', EMAIL)
        await page.click('button:has-text("下一步")')
        
        print("", flush=True)
        print("=== BROWSER WINDOW SHOULD BE ON YOUR SCREEN ===", flush=True)
        print("Email is already filled in.", flush=True)
        print("Please enter your password and complete sign-in.", flush=True)
        print("Come back here after you see the NotebookLM home page.", flush=True)
        print("This script will wait 3 minutes for you.", flush=True)
        print("", flush=True)
        
        # Wait for URL change to NotebookLM
        try:
            await page.wait_for_url("https://notebooklm.google.com/**", timeout=180000)
            print(f"\nSign-in successful! Current URL: {page.url}", flush=True)
            print("Browser stays open. Close the window when done.", flush=True)
            await asyncio.Future()
        except asyncio.TimeoutError:
            print(f"\nTimeout. Current URL: {page.url}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
