#!/usr/bin/env python3
"""wrapper-recover.py — 定时检查并重试离线失败的任务"""
import sys
import subprocess
import os

guard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offline_guard.py")
result = subprocess.run([sys.executable, guard, "--recover"])
sys.exit(result.returncode)
