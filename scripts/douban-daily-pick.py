#!/usr/bin/env python3
"""
豆瓣 Top250 每日选书脚本
- 从 douban-top250.json 读取书单
- 从 douban-reading-progress.json 读取进度
- 随机选一本未读的（前100本试用范围内）
- 更新进度文件
- 输出选中书籍信息到 stdout（供 cron agent 消费）
"""

import json
import os
import random
import sys
from datetime import datetime

DATA_DIR = os.path.expanduser("~/.hermes/data")
BOOK_LIST_PATH = os.path.join(DATA_DIR, "douban-top250.json")
PROGRESS_PATH = os.path.join(DATA_DIR, "douban-reading-progress.json")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    books = load_json(BOOK_LIST_PATH)
    progress = load_json(PROGRESS_PATH)

    processed_ids = progress.get("processed", [])
    max_first_batch = progress.get("max_first_batch", 100)

    # Calculate available books (within first 100/max_first_batch, not yet processed)
    available = []
    for book in books:
        rank = book["rank"]
        if rank > max_first_batch:
            continue
        if rank in processed_ids:
            continue
        available.append(book)

    if not available:
        print("STATUS=ALL_DONE")
        print("MESSAGE=所有书已解读完毕！")
        return

    # Pick a random book
    book = random.choice(available)
    rank = book["rank"]

    # Update progress
    progress["processed"].append(rank)
    progress["last_pick"] = {
        "rank": rank,
        "title": book["title"],
        "author": book["author"],
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    save_json(PROGRESS_PATH, progress)

    # Output book info for the agent
    print(f"STATUS=OK")
    print(f"RANK={rank}")
    print(f"TITLE={book['title']}")
    print(f"AUTHOR={book['author']}")
    print(f"RATING={book['rating']}")
    print(f"PUBLISHER={book.get('publisher', '')}")
    print(f"DONE_COUNT={len(progress['processed'])}")
    print(f"REMAINING={len(available) - 1}")

if __name__ == "__main__":
    main()
