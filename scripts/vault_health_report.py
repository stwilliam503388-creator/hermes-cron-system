#!/usr/bin/env python3
"""vault_health_report.py — 知识库健康看板（方案B核心组件）

功能：
  1. 解析 25 个 cron 任务状态
  2. 检查 Obsidian 各日报目录内容新鲜度
  3. 检查 agent_failed_tasks.json 失败记录
  4. 检查过期索引
  5. 输出 Markdown 报告 → stdout（可管道到 notify.sh）+ 保存到 vault

用法：
  python3 vault_health_report.py                             # 输出到 stdout
  python3 vault_health_report.py --vault /path/to/vault      # 指定 vault 路径
  python3 vault_health_report.py --output /path/to/report.md # 指定输出文件
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# === 常量 ===
HOME = os.environ.get("HOME", "/Users/liuwei")
VAULT = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
)
JOBS_PATH = os.path.join(HOME, ".hermes", "cron", "jobs.json")
FAILED_TASKS_PATH = os.path.join(HOME, ".hermes", "scripts", ".agent_failed_tasks.json")
NOW = datetime.now()

# === 检查的日报目录 ===
DAILY_DIRS = {
    "📰 GitHub日报": "资讯/GitHub日报",
    "📰 AI Agent日报": "资讯/AI Agent日报",
    "📰 AI面试日报": "资讯/AI面试日报",
    "📰 每日名言": "资讯/每日名言",
    "📚 豆瓣每日一书": "资讯/豆瓣每日一书",
}

INDEX_FILES = {
    "🏠 知识库总索引": "🏠 知识库总索引.md",
    "📰 资讯索引": "资讯/📰资讯索引.md",
    "📅 对话归档索引": "对话归档/📅对话归档索引.md",
    "🔧 工具笔记索引": "工具笔记/🔧工具笔记索引.md",
    "🛠 Skills文档索引": "工具笔记/skills/🛠Skills文档索引.md",
}


def read_json(path):
    """安全读取 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失败: {e}"}


def parse_timestamp(ts_str):
    """解析 ISO 时间戳"""
    if not ts_str:
        return None
    try:
        # 处理时区格式: 2026-05-19T06:02:04.524706+08:00
        if "+" in ts_str and ts_str.endswith("+08:00"):
            ts_str = ts_str.replace("+08:00", "")
        elif ts_str.endswith("Z"):
            ts_str = ts_str[:-1]
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def analyze_jobs(jobs):
    """分析所有 cron 任务状态"""
    total = len(jobs)
    ok = 0
    error = 0
    never_run = 0
    paused = 0
    warnings = []

    for job in jobs:
        jid = job.get("id", "?")
        name = job.get("name", "未知任务")
        status = job.get("last_status")
        last_run = job.get("last_run_at")
        last_error = job.get("last_error")
        enabled = job.get("enabled", True)
        paused_flag = job.get("state") == "paused" or not enabled
        no_agent = job.get("no_agent", False)

        if paused_flag:
            paused += 1
            continue

        if status == "ok":
            ok += 1
        elif status == "error":
            error += 1
            warnings.append(("❌", name, f"last_status=error: {last_error or '(无详情)'}"))
        elif last_run is None:
            never_run += 1
            # 只对非一次性任务报警
            schedule = job.get("schedule", {})
            if schedule.get("kind") == "cron":
                warnings.append(("⚪", name, "从未运行"))

        # 检测陈旧任务（上次运行超过 24 小时，每天运行的任务）
        if last_run and status == "ok":
            last_dt = parse_timestamp(last_run)
            if last_dt:
                hours_ago = (NOW - last_dt).total_seconds() / 3600
                schedule_expr = job.get("schedule", {}).get("expr", "")
                # 检测每天运行的任务是否有超过 30h 未执行的
                if "*/" in schedule_expr or schedule_expr.count("*") >= 3:
                    if hours_ago > 30:
                        warnings.append(("⚠️", name, f"上次运行 {hours_ago:.0f}h 前（超阈值30h）"))

    return {
        "total": total,
        "ok": ok,
        "error": error,
        "never_run": never_run,
        "paused": paused,
        "warnings": warnings,
    }


def check_content_freshness(vault):
    """检查各日报目录今日是否有新内容"""
    today = NOW.strftime("%Y-%m-%d")
    results = []

    for label, rel_path in DAILY_DIRS.items():
        full_path = os.path.join(vault, rel_path)
        if not os.path.isdir(full_path):
            results.append((label, "❌ 目录不存在"))
            continue

        today_files = [
            f for f in os.listdir(full_path)
            if f.endswith(".md") and today in f
        ]
        if today_files:
            # 检查文件大小是否为非 stub
            non_stub = 0
            for fname in today_files:
                fpath = os.path.join(full_path, fname)
                size = os.path.getsize(fpath)
                if size > 200:  # 小于 200B 视为 stub
                    non_stub += 1
                else:
                    results.append((label, f"⚠️ {fname} 仅 {size}B (stub)"))
            if non_stub > 0:
                results.append((label, f"✅ 今日有 {non_stub} 篇新内容"))
        else:
            results.append((label, "⚠️ 今日尚无新内容"))

    return results


def check_failed_tasks():
    """检查 agent_failed_tasks.json 中的最近失败记录"""
    data = read_json(FAILED_TASKS_PATH)
    if not data:
        return []

    failures = data if isinstance(data, list) else data.get("failed", [])
    if not failures:
        return []

    # 只取最近 24 小时内的失败
    recent = []
    for f in failures:
        ftime = f.get("time", "")
        job_name = f.get("job", "未知")
        reason = f.get("reason", "未知")
        try:
            ft = datetime.strptime(ftime, "%Y-%m-%d %H:%M")
            if (NOW - ft).total_seconds() < 86400:
                recent.append((job_name, ftime, reason))
        except ValueError:
            pass

    return recent


def check_index_freshness(vault):
    """检查索引文件更新时间"""
    results = []
    for label, rel_path in INDEX_FILES.items():
        full_path = os.path.join(vault, rel_path)
        if not os.path.isfile(full_path):
            results.append((label, "❌ 文件不存在"))
            continue

        mtime = os.path.getmtime(full_path)
        hours_ago = (NOW.timestamp() - mtime) / 3600
        if hours_ago > 48:
            results.append((label, f"❌ 已 {hours_ago:.0f}h 未更新（超48h阈值）"))
        elif hours_ago > 24:
            results.append((label, f"⚠️ 已 {hours_ago:.0f}h 未更新（建议24h内）"))
        else:
            results.append((label, f"✅ {hours_ago:.0f}h 内更新过"))

    return results


def generate_report(vault, output_path=None):
    """生成完整健康报告"""
    jobs_data = read_json(JOBS_PATH)
    jobs = jobs_data.get("jobs", []) if jobs_data else []

    # === 1. 任务状态 ===
    analysis = analyze_jobs(jobs)
    warnings = analysis["warnings"]

    # === 2. 内容新鲜度 ===
    content = check_content_freshness(vault)

    # === 3. 失败记录 ===
    failures = check_failed_tasks()

    # === 4. 索引新鲜度 ===
    indices = check_index_freshness(vault)

    # === 构建报告 ===
    lines = []
    lines.append(f"# 📊 知识库健康报告")
    lines.append(f"生成时间：{NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Vault路径：{vault}")
    lines.append("")

    # 状态概览
    ok_pct = analysis["ok"] / max(analysis["total"], 1) * 100
    lines.append(f"## 📈 总览")
    lines.append(f"- 总任务数：{analysis['total']}")
    lines.append(f"- ✅ 正常：{analysis['ok']} ({ok_pct:.0f}%)")
    lines.append(f"- ❌ 失败：{analysis['error']}")
    lines.append(f"- ⚪ 从未运行：{analysis['never_run']}")
    lines.append(f"- ⏸ 已暂停：{analysis['paused']}")
    lines.append("")

    # 告警列表
    if warnings:
        lines.append("## ⚠️ 告警 & 异常")
        lines.append("")
        for icon, name, detail in warnings:
            lines.append(f"- {icon} **{name}**: {detail}")
        lines.append("")

    # 内容新鲜度
    lines.append(f"## 📰 日报内容检查 ({NOW.strftime('%Y-%m-%d')})")
    lines.append("")
    if content:
        for label, status in content:
            lines.append(f"- {status} — {label}")
    else:
        lines.append("- 无日报目录配置")
    lines.append("")

    # 最近失败
    if failures:
        lines.append("## 🔴 最近 24h 失败记录")
        lines.append("")
        for job_name, ftime, reason in failures:
            lines.append(f"- **{job_name}** 于 {ftime}：{reason}")
        lines.append("")

    # 索引状态
    lines.append("## 📇 索引文件状态")
    lines.append("")
    for label, status in indices:
        lines.append(f"- {status} — {label}")
    lines.append("")

    # 建议
    lines.append("## 💡 建议操作")
    lines.append("")
    if analysis["error"] > 0:
        lines.append("- 🔧 修复失败任务（见上）")
    if failures:
        lines.append("- 🔄 重试失败内容生成")
    has_stale = any("未更新" in s for _, s in indices)
    if has_stale:
        lines.append("- 📝 手动更新过期索引")
    if analysis["never_run"] > 0:
        lines.append("- ⏰ 检查从未运行的任务配置")
    if not any("今日" in s for _, s in content):
        lines.append("- ⏳ 今日日报尚未生成（时间未到或任务失败）")
    lines.append("")

    report_text = "\n".join(lines)

    # 输出到 stdout
    print(report_text)

    # 保存到 vault
    vault_report_path = os.path.join(vault, "📊 知识库健康报告.md")
    try:
        with open(vault_report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
    except OSError as e:
        print(f"保存到 vault 失败：{e}", file=sys.stderr)

    # 可选自定义输出
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_text)
        except OSError as e:
            print(f"保存到输出文件失败：{e}", file=sys.stderr)

    return report_text


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="知识库健康看板")
    parser.add_argument("--vault", default=VAULT, help=f"Obsidian vault 路径（默认：{VAULT}）")
    parser.add_argument("--output", help="额外输出文件路径（可选）")
    args = parser.parse_args()

    generate_report(args.vault, args.output)
