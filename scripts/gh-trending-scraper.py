#!/usr/bin/env python3
"""
GitHub Trending Scraper
Scrapes https://github.com/trending and outputs structured JSON.
For use by the GitHub Trending Daily Report cron job.
"""
import json
import sys
from playwright.sync_api import sync_playwright

def scrape_trending():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://github.com/trending", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # Let JS render

        repos = page.evaluate("""() => {
            const articles = document.querySelectorAll('article.Box-row');
            return Array.from(articles).map(a => {
                const h2 = a.querySelector('h2 a');
                const repoName = h2 ? h2.textContent.trim().replace(/\\s+/g, ' ') : '';
                const href = h2 ? 'https://github.com' + h2.getAttribute('href') : '';
                const desc = (a.querySelector('p.col-9')?.textContent || a.querySelector('p')?.textContent || '').trim();
                const lang = (a.querySelector('[itemprop="programmingLanguage"]')?.textContent || '').trim();
                const totalStars = (a.querySelector('a[href$="/stargazers"]')?.textContent || '').trim();
                const forks = (a.querySelector('a[href$="/forks"]')?.textContent || '').trim();
                const starsMatch = a.textContent.match(/([0-9,]+)\\s*stars?\\s*today/i);
                const starsToday = starsMatch ? starsMatch[1] : '';
                const contributors = Array.from(
                    a.querySelectorAll('a[data-hovercard-type="user"] img')
                ).map(img => img.getAttribute('alt')?.replace('@','') || '').slice(0, 3);
                return {
                    repoName, href, desc: desc.slice(0, 200),
                    lang: lang || 'Unknown',
                    totalStars, forks, starsToday,
                    contributors
                };
            });
        }""")

        browser.close()
        return repos

if __name__ == "__main__":
    try:
        repos = scrape_trending()
        print(json.dumps(repos, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
