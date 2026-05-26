#!/usr/bin/env python3
"""
zhihu-fetch.py — 获取知乎文章内容并转为 Markdown

通过 Chrome cookie 认证绕过知乎反爬。首次使用需在浏览器中登录知乎，
此脚本会自动提取 cookie 并缓存，后续直接复用。

Usage:
    zhihu-fetch.py <url>                          # 获取文章，输出到 stdout
    zhihu-fetch.py <url> --save                   # 保存到 Obsidian vault
    zhihu-fetch.py <url> --output-dir <dir>       # 保存到指定目录
    zhihu-fetch.py --login                        # 打开浏览器手动登录，保存 cookie
    zhihu-fetch.py --status                       # 检查 cookie 状态

Output: Markdown 格式，含 YAML frontmatter (title, author, url, fetched_at)
"""

import os
import sys
import json
import re
import time
import hashlib
import argparse
import warnings
import site
from pathlib import Path
from urllib.parse import urlparse

# Ensure both real home and sandbox home site-packages are on path
# (pip3 may install to either location depending on HOME)
_site_packages = [
    "/Users/liuwei/Library/Python/3.9/lib/python/site-packages",
    "/Users/liuwei/.hermes/profiles/minimal/home/Library/Python/3.9/lib/python/site-packages",
]
for _sp in _site_packages:
    if _sp not in sys.path and os.path.isdir(_sp):
        sys.path.insert(0, _sp)

# Suppress urllib3 LibreSSL warning on macOS
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import requests
from bs4 import BeautifulSoup
import html2text

# === Configuration ===
COOKIE_FILE = "/Users/liuwei/.hermes/zhihu_session.json"
VAULT_DIR = "/Users/liuwei/Documents/个人学习笔记"
DEFAULT_OUTPUT_DIR = os.path.join(VAULT_DIR, "raw", "articles", "incoming")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ===================================================================
# Cookie management
# ===================================================================

def load_cookies() -> dict:
    """Load saved Zhihu cookies from file. Returns cookie dict or empty dict."""
    if not os.path.exists(COOKIE_FILE):
        return {}
    try:
        with open(COOKIE_FILE, "r") as f:
            data = json.load(f)
        return data.get("cookies", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def save_cookies(cookies: dict):
    """Save Zhihu cookies to file."""
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w") as f:
        json.dump({
            "cookies": cookies,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Zhihu session cookies. Delete this file to force re-login."
        }, f, ensure_ascii=False, indent=2)


def extract_cookies_from_chrome() -> dict:
    """Try to extract Zhihu cookies from local Chrome profile via browser_cookie3."""
    try:
        # Force real HOME for browser_cookie3
        import browser_cookie3
        real_home = "/Users/liuwei"

        # Try explicit cookie file path
        cookie_paths = [
            os.path.join(real_home, "Library/Application Support/Google/Chrome/Default/Cookies"),
            os.path.join(real_home, "Library/Application Support/Google/Chrome/Profile 1/Cookies"),
        ]

        for cp in cookie_paths:
            if os.path.exists(cp):
                cj = browser_cookie3.chrome(
                    domain_name='zhihu.com',
                    cookie_file=cp
                )
                cookies = {}
                for c in cj:
                    cookies[c.name] = c.value
                if cookies:
                    return cookies

        return {}
    except ImportError:
        return {}
    except Exception as e:
        print(f"[WARN] Chrome cookie extraction failed: {e}", file=sys.stderr)
        return {}


def extract_cookies_manually() -> dict:
    """Open browser for manual login, guide user to copy cookies from DevTools console."""
    import subprocess

    print("=" * 50, file=sys.stderr)
    print("正在打开知乎...", file=sys.stderr)

    # Open zhihu in default browser
    subprocess.run(["open", "https://www.zhihu.com"], check=False)

    print(file=sys.stderr)
    print("请在浏览器中完成以下步骤：", file=sys.stderr)
    print("  1. 登录知乎（如果还没登录）", file=sys.stderr)
    print("  2. 按 F12 打开开发者工具", file=sys.stderr)
    print("  3. 切换到 Console（控制台）标签页", file=sys.stderr)
    print("  4. 输入以下命令并回车：", file=sys.stderr)
    print(file=sys.stderr)
    print("     document.cookie", file=sys.stderr)
    print(file=sys.stderr)
    print("  5. 复制输出的整行文字（一串 key=value 对）", file=sys.stderr)
    print("  6. 粘贴到下方并回车", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(file=sys.stderr)

    try:
        cookie_str = input("Cookie 字符串: ").strip()
    except EOFError:
        print("[ERROR] 无法读取输入。", file=sys.stderr)
        return {}

    if not cookie_str:
        print("[ERROR] Cookie 字符串为空。", file=sys.stderr)
        return {}

    # Parse cookie string: "key1=val1; key2=val2; ..."
    cookies = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            cookies[key.strip()] = val.strip()

    if not cookies:
        print("[ERROR] 未能解析 cookie 字符串。", file=sys.stderr)
        return {}

    print(f"[INFO] 成功提取 {len(cookies)} 个 cookie。", file=sys.stderr)
    return cookies


def get_cookies(force_login: bool = False) -> dict:
    """
    Get Zhihu cookies. Priority:
    1. Cached file (if not force_login)
    2. Chrome profile (browser_cookie3)
    3. Playwright manual login
    """
    if not force_login:
        cached = load_cookies()
        if cached:
            return cached

    # Try Chrome auto-extraction
    print("[INFO] 尝试从 Chrome 自动提取 cookie...", file=sys.stderr)
    chrome_cookies = extract_cookies_from_chrome()
    if chrome_cookies:
        save_cookies(chrome_cookies)
        return chrome_cookies

    # Fallback: manual cookie entry
    print("[INFO] 需要手动输入 cookie...", file=sys.stderr)
    pw_cookies = extract_cookies_manually()
    if pw_cookies:
        save_cookies(pw_cookies)
        return pw_cookies

    return {}


# ===================================================================
# Content extraction
# ===================================================================

def fetch_page(url: str, cookies: dict) -> str:
    """Fetch the HTML content of a Zhihu page with cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)

    # Set cookies
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".zhihu.com")

    resp = session.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def extract_article(html: str, url: str) -> dict:
    """
    Extract article metadata and content from Zhihu HTML.
    Returns dict with keys: title, author, content_html, published
    """
    soup = BeautifulSoup(html, "lxml")
    parsed = urlparse(url)
    domain = parsed.netloc

    result = {
        "title": "",
        "author": "",
        "content_html": "",
        "published": "",
        "type": "unknown"
    }

    # --- Extract title ---
    title_tag = (
        soup.find("h1", class_="Post-Title") or
        soup.find("h1", class_="QuestionHeader-title") or
        soup.find("title")
    )
    if title_tag:
        result["title"] = title_tag.get_text(strip=True)

    # --- Extract author ---
    author_tag = (
        soup.find("meta", {"itemprop": "author"}) or
        soup.find("a", class_="UserLink-link") or
        soup.find("div", class_="AuthorInfo-name")
    )
    if author_tag:
        result["author"] = author_tag.get("content", "") or author_tag.get_text(strip=True)

    # --- Extract date ---
    date_tag = soup.find("meta", {"itemprop": "datePublished"})
    if date_tag:
        result["published"] = date_tag.get("content", "")

    # --- Extract content based on page type ---
    if "zhuanlan.zhihu.com" in domain:
        # Article page
        content = (
            soup.find("article") or
            soup.find("div", class_="Post-RichText") or
            soup.find("div", class_="RichText")
        )
        result["type"] = "article"
    elif "answer" in url or "question" in domain:
        # Answer page (www.zhihu.com/question/xxx/answer/xxx)
        content = (
            soup.find("div", class_="RichContent-inner") or
            soup.find("div", class_="AnswerItem-content") or
            soup.find("div", class_="RichText")
        )
        result["type"] = "answer"
    else:
        # Generic — try common content containers
        content = (
            soup.find("article") or
            soup.find("div", class_="RichText") or
            soup.find("div", class_="Post-RichText")
        )
        result["type"] = "unknown"

    if content:
        # Remove unwanted elements before conversion
        for tag in content.find_all(["script", "style", "noscript"]):
            tag.decompose()

        # Remove Zhihu UI elements
        for cls in [
            "LinkCard", "RichContent-cover", "ContentItem-actions",
            "VoteButton", "AuthorInfo", "Catalog", "CornerButtons",
            "Post-ActionMenu", "Post-SideActions", "Reward",
            "MobileAppHeader", "AppBanner", "Question-sideColumn",
        ]:
            for el in content.find_all(class_=re.compile(cls)):
                el.decompose()

        # Remove "阅读全文" links
        for el in content.find_all("span", string=re.compile(r"阅读全文|收起")):
            el.decompose()

        result["content_html"] = str(content)

    return result


def html_to_markdown(html: str) -> str:
    """Convert HTML content to clean Markdown."""
    h = html2text.HTML2Text()
    h.body_width = 0          # No wrapping
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.ignore_tables = False
    h.protect_links = True
    h.unicode_snob = True
    h.skip_internal_links = False
    h.single_line_break = False
    h.mark_code = True

    md = h.handle(html)

    # Clean up common artifacts
    md = re.sub(r'\n{4,}', '\n\n\n', md)           # Collapse excessive blank lines
    md = re.sub(r'!\[\]\(data:image[^)]*\)', '', md)  # Remove inline data URIs
    md = md.strip()

    return md


def build_frontmatter(meta: dict, url: str) -> str:
    """Build YAML frontmatter."""
    lines = [
        "---",
        f"title: {meta.get('title', 'Untitled')}",
        f"source: zhihu",
        f"url: {url}",
        f"fetched_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if meta.get("author"):
        lines.append(f"author: {meta['author']}")
    if meta.get("published"):
        lines.append(f"published: {meta['published']}")
    if meta.get("type"):
        lines.append(f"type: {meta['type']}")
    lines.append("---")
    return "\n".join(lines)


def generate_filename(title: str, url: str) -> str:
    """Generate a safe filename from title or URL."""
    if title:
        # Truncate and clean
        name = title[:60].strip()
        name = re.sub(r'[\\/:*?"<>|#]', '', name)
        name = re.sub(r'\s+', '-', name)
        if name:
            return f"{name}.md"

    # Fallback: hash-based
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"zhihu-{h}.md"


def save_to_vault(markdown: str, filename: str, output_dir: str = None) -> str:
    """Save markdown to the Obsidian vault. Returns the file path."""
    target_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    return filepath


# ===================================================================
# Main
# ===================================================================

def is_zhihu_url(url: str) -> bool:
    """Check if URL is a Zhihu domain."""
    domain = urlparse(url).netloc.lower()
    return "zhihu.com" in domain


def process_url(url: str, output_dir: str = None, save: bool = False) -> dict:
    """Main processing pipeline for a single Zhihu URL."""
    result = {
        "status": "error",
        "url": url,
        "message": "",
        "path": "",
        "length": 0,
    }

    # Step 1: Get cookies
    cookies = get_cookies()
    if not cookies:
        result["message"] = (
            "无法获取知乎登录 cookie。\n"
            "请运行: python3 ~/.hermes/scripts/zhihu-fetch.py --login\n"
            "在浏览器中登录知乎后再试。"
        )
        return result

    # Step 2: Fetch page
    try:
        html = fetch_page(url, cookies)
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            result["message"] = (
                f"知乎返回 403，cookie 可能已过期或文章需要登录。\n"
                f"请运行: python3 /Users/liuwei/.hermes/scripts/zhihu-fetch.py --login\n"
                f"重新获取 cookie 后再试。\n"
                f"（如文章本身可公开访问，可能是 cookie 缺少 z_c0 HttpOnly 字段）"
            )
        elif e.response.status_code == 404:
            result["message"] = f"文章不存在 (404): {url}"
        else:
            result["message"] = f"请求失败 (HTTP {e.response.status_code}): {e}"
        return result
    except Exception as e:
        result["message"] = f"网络请求失败: {e}"
        return result

    # Step 3: Extract content
    meta = extract_article(html, url)
    if not meta["content_html"]:
        result["message"] = "未能从页面中提取到文章内容。文章可能需要付费或已被删除。"
        return result

    # Step 4: Convert to markdown
    md_body = html_to_markdown(meta["content_html"])
    frontmatter = build_frontmatter(meta, url)
    full_md = frontmatter + "\n\n" + md_body

    # Step 5: Save or output
    if save or output_dir:
        filename = generate_filename(meta["title"], url)
        filepath = save_to_vault(full_md, filename, output_dir)
        result["status"] = "saved"
        result["path"] = filepath
        result["length"] = len(full_md)
        result["message"] = f"已保存到 {filepath}"
    else:
        print(full_md)
        result["status"] = "ok"
        result["message"] = "内容已输出到 stdout"

    return result


def main():
    parser = argparse.ArgumentParser(description="获取知乎文章内容并转为 Markdown")
    parser.add_argument("url", nargs="?", help="知乎文章链接")
    parser.add_argument("--save", "-s", action="store_true", help="保存到 Obsidian vault")
    parser.add_argument("--output-dir", "-o", help="输出目录 (默认: raw/articles/incoming)")
    parser.add_argument("--json", "-j", action="store_true", help="以 JSON 格式输出结果")
    parser.add_argument("--login", action="store_true", help="打开浏览器手动登录知乎，保存 cookie")
    parser.add_argument("--status", action="store_true", help="检查 cookie 状态")

    args = parser.parse_args()

    # --login mode
    if args.login:
        cookies = extract_cookies_manually()
        if cookies:
            save_cookies(cookies)
            print("✅ 知乎 cookie 已保存。")
        else:
            print("❌ 登录失败，未获取到 cookie。")
            sys.exit(1)
        return

    # --status mode
    if args.status:
        cookies = load_cookies()
        if cookies:
            print(f"✅ Cookie 已缓存 ({len(cookies)} 个条目)")
            print(f"   文件: {COOKIE_FILE}")
            # Try a quick validation
            try:
                resp = requests.get(
                    "https://www.zhihu.com/api/v4/me",
                    cookies={k: v for k, v in cookies.items()},
                    headers=HEADERS,
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"   用户: {data.get('name', 'unknown')}")
                    print(f"   状态: 有效 ✅")
                else:
                    print(f"   状态: 可能已过期 (HTTP {resp.status_code})")
            except Exception as e:
                print(f"   验证失败: {e}")
        else:
            print("❌ 没有缓存的 cookie。请运行: python3 zhihu-fetch.py --login")
        return

    # URL mode
    if not args.url:
        parser.print_help()
        sys.exit(1)

    if not is_zhihu_url(args.url):
        print(f"❌ 不是知乎链接: {args.url}", file=sys.stderr)
        sys.exit(1)

    result = process_url(args.url, output_dir=args.output_dir, save=args.save)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["status"] == "error":
            print(f"❌ {result['message']}", file=sys.stderr)
            sys.exit(1)
        elif result["status"] == "saved":
            print(f"✅ {result['message']}")
        # else: content already printed in process_url


if __name__ == "__main__":
    main()
