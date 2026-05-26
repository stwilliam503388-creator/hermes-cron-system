#!/usr/bin/env python3
"""
video-queue-processor.py — 视频链接队列处理

Reads URLs from video-queue.txt, processes each with yt-dlp + faster-whisper,
saves the transcript to Obsidian vault at raw/articles/bilibili/.
Removes processed URLs from the queue.

Usage:
    ./video-queue-processor.py                    # Process all queued URLs
    ./video-queue-processor.py --add "URL"        # Add URL to queue
    ./video-queue-processor.py --list             # List queued URLs
"""

import os
import sys
import re
import json
import time
import subprocess
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────

# Fix HOME for cron context
if os.environ.get("HOME", "").startswith("/Users/liuwei/.hermes/profiles/"):
    os.environ["HOME"] = "/Users/liuwei"

# Hardcoded absolute paths (don't use Path.home())
SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
REPO_DIR = "/Users/liuwei/Documents/workspace/MyGithub/universal-video-extractor"
VENV_PYTHON = os.path.join(REPO_DIR, ".venv", "bin", "python3")
QUEUE_FILE = os.path.join(SCRIPTS_DIR, "video-queue.txt")
VAULT_RAW_DIR = "/Users/liuwei/Documents/个人学习笔记/raw/articles/bilibili"
OUTPUT_DIR = os.path.join(REPO_DIR, "output")
WHISPER_CACHE = "/tmp/whisper_cache"

# ── Helpers ────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def read_queue() -> list:
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    return lines

def write_queue(urls: list):
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")

def is_bilibili_url(url: str) -> bool:
    return bool(re.search(r'bilibili\.com/video/', url)) or bool(re.search(r'b23\.tv/', url))

def is_douyin_url(url: str) -> bool:
    return bool(re.search(r'douyin\.com/', url))

def extract_bvid(url: str) -> Optional[str]:
    m = re.search(r'BV[a-zA-Z0-9_]{10,}', url)
    return m.group(0) if m else None

def sanitize_title(title: str) -> str:
    """Create a safe filename from video title."""
    # Remove special chars, limit length
    safe = re.sub(r'[\\/:*?"<>|]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    return safe[:80]

# ── Video Processing ────────────────────────────────────────────────────────

def process_video(url: str) -> Optional[str]:
    """
    Process a single video URL:
    1. Download audio via yt-dlp (proxy bypassed)
    2. Transcribe with faster-whisper
    3. Save markdown to Obsidian vault
    Returns path to saved markdown file, or None on failure.
    """
    log(f"Processing: {url}")

    if not os.path.exists(VENV_PYTHON):
        log(f"ERROR: Venv python not found at {VENV_PYTHON}")
        return None

    # Step 1: Download audio
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    download_cmd = [
        VENV_PYTHON, "-c", f"""
import os, yt_dlp, json

# Bypass Hermes proxy (blocks Bilibili)
for k in ['HTTPS_PROXY','https_proxy','HTTP_PROXY','http_proxy','ALL_PROXY','all_proxy']:
    os.environ.pop(k, None)

url = '{url}'
ydl_opts = {{
    'proxy': '',
    'format': 'bestaudio/best',
    'outtmpl': '{OUTPUT_DIR}/audio_%(id)s.%(ext)s',
    'quiet': True,
    'http_headers': {{
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/',
    }},
}}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=True)
    info_file = '{OUTPUT_DIR}/video_info.json'
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump({{
            'title': info.get('title', 'Unknown'),
            'uploader': info.get('uploader', 'Unknown'),
            'duration': info.get('duration', 0),
            'webpage_url': info.get('webpage_url', url),
            'ext': info.get('ext', ''),
            'id': info.get('id', ''),
        }}, f, ensure_ascii=False)
    print(f"OK {{info.get('id')}}.{{info.get('ext')}}")
"""
    ]

    log("Downloading audio...")
    result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=600,
                           encoding='utf-8', errors='replace')
    if result.returncode != 0:
        log(f"Download failed: {result.stderr[-200:]}")
        return None

    # Find the audio file
    audio_file = None
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("audio_") and not f.endswith(".json"):
            audio_file = os.path.join(OUTPUT_DIR, f)
            break

    if not audio_file:
        log("Audio file not found after download")
        return None

    log(f"Audio: {audio_file} ({os.path.getsize(audio_file)//1024}KB)")

    # Step 2: Transcribe with Whisper
    transcribe_cmd = [
        VENV_PYTHON, "-c", f"""
import os, json, sys
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from faster_whisper import WhisperModel
import time

audio = '{audio_file}'
info_path = '{OUTPUT_DIR}/video_info.json'

with open(info_path, 'r') as f:
    info = json.load(f)

print(f"Loading Whisper base model...", flush=True)
model = WhisperModel("base", device="cpu", compute_type="int8",
    download_root='{WHISPER_CACHE}')

duration = info.get('duration', 0)
print(f"Transcribing {{duration}}s audio...", flush=True)
t0 = time.time()
segments, seg_info = model.transcribe(audio, language="zh",
    beam_size=5, vad_filter=True)
print(f"Language: {{seg_info.language}}", flush=True)

all_segs = list(segments)
print(f"Segments: {{len(all_segs)}}, took {{time.time()-t0:.0f}}s", flush=True)

# Format transcript
lines = []
for seg in all_segs:
    m, s = int(seg.start // 60), int(seg.start % 60)
    lines.append(f"[{{m:02d}}:{{s:02d}}] {{seg.text.strip()}}")

result = {{
    'title': info['title'],
    'uploader': info['uploader'],
    'url': info['webpage_url'],
    'duration': info['duration'],
    'language': seg_info.language,
    'segments': len(all_segs),
    'transcript': '\\n'.join(lines),
}}
out = json.dumps(result, ensure_ascii=False)
print(f"TRANSCRIPT_JSON_START", flush=True)
print(out, flush=True)
print(f"TRANSCRIPT_JSON_END", flush=True)
"""
    ]

    log("Transcribing with Whisper...")
    result = subprocess.run(transcribe_cmd, capture_output=True, text=True, timeout=3600,
                           encoding='utf-8', errors='replace')

    if result.returncode != 0:
        log(f"Transcription failed: {result.stderr[-200:]}")
        return None

    # Parse the JSON output
    output = result.stdout
    start_marker = "TRANSCRIPT_JSON_START"
    end_marker = "TRANSCRIPT_JSON_END"
    start_idx = output.find(start_marker)
    end_idx = output.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        log(f"Failed to parse transcription output")
        return None

    json_str = output[start_idx + len(start_marker):end_idx].strip()
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}")
        return None

    # Step 3: Save to Obsidian vault
    title = data['title']
    transcript = data['transcript']
    uploader = data['uploader']
    url = data['url']
    duration = data['duration']
    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "?"

    safe_title = sanitize_title(title)
    bvid = extract_bvid(url) or "unknown"
    filename = f"{bvid}-{safe_title}.md"
    filepath = os.path.join(VAULT_RAW_DIR, filename)

    os.makedirs(VAULT_RAW_DIR, exist_ok=True)

    md_content = f"""---
source: "Bilibili"
url: "{url}"
author: "{uploader}"
captured_at: "{time.strftime('%Y-%m-%d')}"
type: "video"
duration: "{duration_str}"
tags: [bilibili, 视频转写]
title: "{title}"
---

# {title}

> B站视频｜UP主：{uploader}｜时长 {duration_str}
> 原始链接：{url}

---

## 语音转写

*由 video-transcript-extractor 自动转写，Whisper base 模型，准确率有限。*

{transcript}
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    log(f"Saved: {filepath} ({len(transcript)} chars)")

    # Cleanup audio file
    try:
        os.remove(audio_file)
        os.remove(os.path.join(OUTPUT_DIR, "video_info.json"))
    except OSError:
        pass

    return filepath


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--add":
            urls = read_queue()
            for url in sys.argv[2:]:
                if url not in urls:
                    urls.append(url)
                    log(f"Added to queue: {url}")
            write_queue(urls)
            return
        elif sys.argv[1] == "--list":
            urls = read_queue()
            if urls:
                print(f"Queue ({len(urls)} pending):")
                for i, url in enumerate(urls, 1):
                    bvid = extract_bvid(url) or "?"
                    print(f"  {i}. [{bvid}] {url[:80]}")
            else:
                print("Queue is empty.")
            return

    # Process queue
    urls = read_queue()
    if not urls:
        log("Queue is empty. Nothing to do.")
        return

    log(f"Processing {len(urls)} video(s)...")
    processed = []
    failed = []

    for url in urls:
        result = process_video(url)
        if result:
            processed.append(url)
            log(f"✅ {result}")
        else:
            failed.append(url)
            log(f"❌ Failed: {url}")

    # Update queue: remove processed, keep failed for retry
    remaining = [u for u in urls if u in failed]
    write_queue(remaining)

    log(f"Done. Processed: {len(processed)}, Failed: {len(failed)}, Remaining: {len(remaining)}")

    # If any failed, write a brief error report
    if failed:
        report = os.path.join(SCRIPTS_DIR, "video-queue-errors.txt")
        with open(report, "w", encoding="utf-8") as f:
            f.write(f"# Video queue errors - {time.strftime('%Y-%m-%d %H:%M')}\n\n")
            for url in failed:
                f.write(f"- {url}\n")


if __name__ == "__main__":
    main()
