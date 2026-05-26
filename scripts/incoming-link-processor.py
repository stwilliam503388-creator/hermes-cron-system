#!/usr/bin/env python3
"""
incoming-link-processor.py — 自动处理来自消息通道的链接

When given a URL, determines if it's a video or article link,
then processes accordingly. Outputs a summary for the agent to respond.

Usage:
    ./incoming-link-processor.py <url>              # Process and return summary
    ./incoming-link-processor.py <url> --json       # Return structured JSON
"""

import os
import re
import sys
import json
import subprocess
from urllib.parse import urlparse

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
REPO_DIR = "/Users/liuwei/Documents/workspace/MyGithub/universal-video-extractor"
VAULT_DIR = "/Users/liuwei/Documents/个人学习笔记"

VIDEO_DOMAINS = [
    "bilibili.com", "b23.tv",
    "douyin.com", "tiktok.com",
    "xiaohongshu.com", "xhslink.com",
    "youtube.com", "youtu.be",
]

def classify_url(url: str) -> str:
    """Classify URL as 'video', 'article', or 'unknown'."""
    domain = urlparse(url).netloc.lower()
    for vd in VIDEO_DOMAINS:
        if vd in domain:
            return "video"
    return "article"

def process_video(url: str) -> dict:
    """Add video URL to the processing queue."""
    queue_file = os.path.join(SCRIPTS_DIR, "video-queue.txt")
    queue = []
    if os.path.exists(queue_file):
        with open(queue_file, "r", encoding="utf-8") as f:
            queue = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    if url in queue:
        return {"status": "already_queued", "message": "已在队列中"}

    queue.append(url)
    with open(queue_file, "w", encoding="utf-8") as f:
        for u in queue:
            f.write(u + "\n")

    # Extract BVID if Bilibili
    bvid = ""
    m = re.search(r'BV[a-zA-Z0-9_]{10,}', url)
    if m:
        bvid = m.group(0)

    return {
        "status": "queued",
        "type": "video",
        "bvid": bvid,
        "message": f"已加入视频转写队列（BID: {bvid or '?'}）",
        "queue_position": len(queue),
        "next_run": "下一个定时处理时间：08:00 / 14:00 / 20:00"
    }

ZHI_HU_DOMAINS = ["zhihu.com", "zhuanlan.zhihu.com"]

def process_article(url: str) -> dict:
    """Download article via domain-specific tools and save."""
    output_dir = os.path.join(VAULT_DIR, "raw", "articles", "incoming")
    os.makedirs(output_dir, exist_ok=True)

    # --- Zhihu: use cookie-based scraper (baoyu CDP blocked by 40362) ---
    domain = urlparse(url).netloc.lower()
    if any(zh in domain for zh in ZHI_HU_DOMAINS):
        zhihu_script = os.path.join(SCRIPTS_DIR, "zhihu-fetch.py")
        if os.path.exists(zhihu_script):
            try:
                result = subprocess.run(
                    ["python3", zhihu_script, url, "--save", "--json"],
                    capture_output=True, text=True, timeout=90,
                    env={**os.environ, "HOME": "/Users/liuwei"}
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if data.get("status") == "saved" and data.get("path"):
                        return {
                            "status": "saved",
                            "type": "article",
                            "path": data["path"],
                            "length": data.get("length", 0),
                            "message": f"知乎文章已保存到 {data['path']}"
                        }
                # zhihu-fetch failed — parse error for better message
                stderr = result.stderr.strip()
                if "cookie" in stderr.lower() or "登录" in stderr:
                    return {
                        "status": "pending",
                        "type": "article",
                        "path": "",
                        "message": (
                            "知乎需要登录才能抓取。\n"
                            "首次使用请运行: python3 ~/.hermes/scripts/zhihu-fetch.py --login\n"
                            "或者直接复制文章内容发给我。"
                        )
                    }
            except subprocess.TimeoutExpired:
                pass
            except json.JSONDecodeError:
                pass
        # Fall through to pending note

    # Try baoyu-url-to-markdown script
    skill_dir = os.path.join(
        os.path.expanduser("~"),
        ".hermes", "profiles", "minimal", "skills",
        "llm-wiki", "deps", "baoyu-url-to-markdown"
    )

    bun = "/Users/liuwei/.hermes/node/bin/bun"
    main_ts = os.path.join(skill_dir, "scripts", "main.ts")
    article_path = ""

    if os.path.exists(main_ts) and os.path.exists(bun):
        try:
            result = subprocess.run(
                [bun, main_ts, url, "--output-dir", output_dir],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                # Find the saved file
                for root, dirs, files in os.walk(output_dir):
                    for f in files:
                        if f.endswith(".md") and not f.endswith("-captured.html"):
                            article_path = os.path.join(root, f)
                            break
                    if article_path:
                        break
        except subprocess.TimeoutExpired:
            pass

    if os.path.exists(article_path):
        with open(article_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {
            "status": "saved",
            "type": "article",
            "path": article_path,
            "length": len(content),
            "message": f"文章已保存到 {article_path}"
        }
    else:
        # Fallback: save URL info as a note for manual processing
        fallback_path = os.path.join(output_dir, f"pending-{hash(url) & 0xfffffff}.md")
        with open(fallback_path, "w", encoding="utf-8") as f:
            f.write(f"---\nurl: {url}\nreceived: pending\n---\n\n# 待处理链接\n\n> {url}\n\n此链接未能自动抓取，需要手动处理。\n")
        return {
            "status": "pending",
            "type": "article",
            "path": fallback_path,
            "message": "文章自动抓取失败，已保存为待处理条目"
        }

def main():
    if len(sys.argv) < 2:
        print("Usage: incoming-link-processor.py <url> [--json]")
        sys.exit(1)

    url = sys.argv[1].strip()
    use_json = "--json" in sys.argv

    classification = classify_url(url)

    if classification == "video":
        result = process_video(url)
    else:
        result = process_article(url)

    result["url"] = url
    result["classification"] = classification

    if use_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[{result['status'].upper()}] {result['message']}")
        if result.get("bvid"):
            print(f"  视频ID: {result['bvid']}")
        queue_pos = result.get("queue_position")
        if queue_pos:
            print(f"  队列位置: #{queue_pos}")
        if result.get("path"):
            print(f"  保存路径: {result['path']}")
        if result.get("next_run"):
            print(f"  {result['next_run']}")

if __name__ == "__main__":
    main()
