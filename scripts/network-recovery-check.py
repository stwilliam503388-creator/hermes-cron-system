#!/usr/bin/env python3
"""
网络恢复检测 + 失败任务自动重试

每 2 小时执行一次（cron: 0 */2 * * *），在 MacBook 上运行。
检测到网络恢复后自动重试所有 error/timeout 状态的 cron 任务。

相关配置：~/.hermes/profiles/minimal/.env 已有 HTTPS_PROXY 等代理变量
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = "/Users/liuwei"
HERMES = f"{HOME}/.local/bin/hermes"
JOBS_FILE = f"{HOME}/.hermes/profiles/minimal/cron/jobs.json"
SCRIPTS_DIR = f"{HOME}/.hermes/scripts"
NETWORK_TEST = [
    "curl", "-s", "--connect-timeout", "5", "--max-time", "8",
    "https://www.baidu.com", "-o", "/dev/null", "-w", "%{http_code}"
]

# Proxy 健康检测：通过代理访问境外 API（直连不通，代理通才算正常）
PROXY_TEST = [
    "curl", "-s", "--connect-timeout", "5", "--max-time", "10",
    "--proxy", "http://127.0.0.1:7890",
    "https://api.deepseek.com/v1/models", "-o", "/dev/null", "-w", "%{http_code}"
]

# offline_guard.py .failed_jobs.json recovery is no longer needed;
# all retry is handled via jobs.json by daily-midnight-check.py
# and this script's own retry loop below.

# 需要联网的 LLM 任务 ID（失败时网络恢复后重试）
LLM_AGENT_JOBS = [
    "merged-morning-briefing",   # 晨间AI情报简报
    "merged-evening-briefing",   # 晚间AI情报快讯
    "203327bd97ca",              # 每日AI Agent面试问答日报
    "81c3d765872a",              # AI Agent 每日内容生成
    "ce30a76a3af9",              # 豆瓣每日一书解读
    "17a174a181df",              # 每日名言+解读
    "6aeb002b6f92",              # 每日阅读清单
    "4b35124a30f2",              # 周报自动生成
    "8958f4ca8a19",              # 播客转文字摘要
    "a52e754dc363",              # 概念自动萃取
]


def check_proxy() -> tuple[bool, str]:
    """返回 (代理可用, 状态描述)"""
    try:
        r = subprocess.run(PROXY_TEST, capture_output=True, text=True, timeout=15,
                           encoding='utf-8', errors='replace')
        code = r.stdout.strip()
        if code.startswith("2") or code == "401":
            return True, f"proxy OK (deepseek API: {code})"
        return False, f"proxy returned {code}"
    except subprocess.TimeoutExpired:
        return False, "proxy timeout"
    except Exception as e:
        return False, f"proxy error: {e}"


def check_network() -> bool:
    try:
        r = subprocess.run(NETWORK_TEST, capture_output=True, text=True, timeout=15,
                           encoding='utf-8', errors='replace')
        code = r.stdout.strip()
        return code in ("200", "302", "301", "304") or code.startswith("2")
    except Exception:
        return False


def get_errored_jobs() -> list[dict]:
    jobs_file = Path(JOBS_FILE)
    if not jobs_file.exists():
        print(f"  jobs.json: {JOBS_FILE}")
        return []
    try:
        data = json.loads(jobs_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"  jobs.json parse fail: {e}")
        return []
    jobs = data.get("jobs", [])
    return [j for j in jobs if j.get("last_status") in ("error", "timeout")]


def retry_job(job: dict) -> bool:
    job_id = job.get("id", "")
    name = job.get("name", "?")
    no_agent = job.get("no_agent", False)
    script = job.get("script", "")
    schedule_raw = job.get("schedule", "")
    schedule = schedule_raw.get("expr", "") if isinstance(schedule_raw, dict) else str(schedule_raw)
    if "*/" in schedule or schedule.count("*") >= 4:
        print(f"  -- [{name}] high-freq, skip")
        return True
    print(f"  >> [{name}] retrying...")
    if no_agent and script:
        sp = script if script.startswith("/") else f"{SCRIPTS_DIR}/{script}"
        if not os.path.isfile(sp):
            return cli_retry(job_id, name)
        cmd = ["bash", sp] if sp.endswith(".sh") else [sys.executable, sp]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            print(f"    {'OK' if r.returncode == 0 else f'FAIL({r.returncode})'}")
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"    timeout")
            return False
        except Exception as e:
            print(f"    {e}")
            return False
    else:
        return cli_retry(job_id, name)


def cli_retry(job_id: str, name: str) -> bool:
    try:
        r = subprocess.run([HERMES, "cron", "run", job_id, "--accept-hooks"],
                           capture_output=True, text=True, timeout=30)
        ok = r.returncode == 0
        print(f"    {'OK' if ok else 'FAIL'}: hermes cron run {job_id}")
        return ok
    except Exception as e:
        print(f"    {e}")
        return False


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== net-recovery [{ts}] ===")
    if not check_network():
        print("  offline, skip")
        return 0
    print("  online")
    proxy_ok, proxy_msg = check_proxy()
    if proxy_ok:
        print(f"  {proxy_msg}")
    else:
        print(f"  ⚠️  {proxy_msg} — LLM 任务可能受影响")
    errored = get_errored_jobs()
    if not errored:
        print("  all ok")
        return 0
    print(f"  {len(errored)} failed jobs")
    for j in errored:
        retry_job(j)
        time.sleep(2)
    return 0

if __name__ == "__main__":
    sys.exit(main())
