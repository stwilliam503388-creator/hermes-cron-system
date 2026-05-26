#!/bin/bash
# video-enqueue.sh — 添加视频链接到处理队列
# Usage:
#   video-enqueue.sh "https://www.bilibili.com/video/BVxxx"
#   video-enqueue.sh "https://www.douyin.com/video/xxx"

SCRIPT_DIR="/Users/liuwei/.hermes/scripts"
SCRIPT="$SCRIPT_DIR/video-queue-processor.py"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <video-url> [more-urls...]"
    echo ""
    echo "Supported: Bilibili, Douyin/TikTok, Xiaohongshu, YouTube"
    echo ""
    echo "Check queue: $SCRIPT --list"
    exit 1
fi

"$VENV_PYTHON" "$SCRIPT" --add "$@"
echo ""
echo "Queue will be processed next: 08:00 / 14:00 / 20:00"
echo "Or run immediately: $SCRIPT"
