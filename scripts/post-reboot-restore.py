#!/usr/bin/env python3
"""
post-reboot-restore.py — 重启后重做所有 10 项修复任务
用法: python3 post-reboot-restore.py [--apply] [--skip-cleanup]
  --apply:    实际执行（默认 dry-run，只输出计划）
  --skip-cleanup: 跳过孤儿清理步骤（9,10）
"""
import json, os, shutil, subprocess, sys

SCRIPTS_DIR = "/Users/liuwei/.hermes/scripts"
VAULT_PATH = "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
SETENV = os.path.join(SCRIPTS_DIR, "setenv.sh")
D = "/--- DRY RUN ---/" if "--apply" not in sys.argv else ""
skip_cleanup = "--skip-cleanup" in sys.argv

def info(msg): print(f"  ℹ️  {msg}")
def ok(msg): print(f"  ✅ {msg}")
def act(msg): print(f"  🔧 {D}{msg}" if D else f"  🔧 {msg}")
def skip(msg): print(f"  ⏭️  {msg}")

print("═" * 56)
print(" Obsidian 自动化修复 — 重启后恢复清单")
print("═" * 56)

if D.strip():
    print(" ⚠️  DRY RUN 模式 — 加 --apply 执行\n")
else:
    print(" 🚀 执行模式\n")

# ── P0: 致命 Bug 修复 ──
print("━" * 56)
print("🔴 P0: 严重 Bug 修复")
print("━" * 56)

# 1. wrapper-obsidian-pipeline.sh tilde → 绝对路径
print("\n[1/10] wrapper-obsidian-pipeline.sh tilde 修复")
fp = os.path.join(SCRIPTS_DIR, "wrapper-obsidian-pipeline.sh")
if os.path.isfile(fp):
    with open(fp) as f:
        content = f.read()
    if "~/.hermes/scripts/" in content:
        new_content = content.replace(
            "~/.hermes/scripts/",
            "/Users/liuwei/.hermes/scripts/"
        )
        if "--apply" in sys.argv:
            with open(fp, "w") as f:
                f.write(new_content)
            act("替换 tilde → 绝对路径")
        else:
            info("需替换 2 处 ~/.hermes/scripts/ → 绝对路径")
    else:
        ok("已经是绝对路径")
else:
    skip("文件不存在")

# 2. wrapper-llm-polish.py os.path.expanduser → 硬编码
print("\n[2/10] wrapper-llm-polish.py HOME 重映射修复")
fp = os.path.join(SCRIPTS_DIR, "wrapper-llm-polish.py")
if os.path.isfile(fp):
    with open(fp) as f:
        content = f.read()
    old = 'STATE_FILE = os.path.expanduser("~/.hermes/scripts/.failed_jobs.json")'
    new = 'STATE_FILE = "/Users/liuwei/.hermes/scripts/.failed_jobs.json"'
    if old in content:
        if "--apply" in sys.argv:
            with open(fp, "w") as f:
                f.write(content.replace(old, new))
            act("替换 os.path.expanduser → 硬编码")
        else:
            info("需替换 os.path.expanduser 为硬编码路径")
    else:
        ok("已是硬编码路径")
else:
    skip("文件不存在")

# 3. setenv.sh 补充 NOTEBOOKLM_VENV
print("\n[3/10] setenv.sh 补充 NOTEBOOKLM_VENV")
if os.path.isfile(SETENV):
    with open(SETENV) as f:
        content = f.read()
    if "NOTEBOOKLM_VENV" not in content:
        new_line = '\nexport NOTEBOOKLM_VENV="/Users/liuwei/.hermes/notebooklm_venv/bin/python"\n'
        if "--apply" in sys.argv:
            with open(SETENV, "a") as f:
                f.write(new_line)
            act("添加 NOTEBOOKLM_VENV 到 setenv.sh")
        else:
            info("需添加 export NOTEBOOKLM_VENV=...")
    else:
        ok("NOTEBOOKLM_VENV 已定义")
else:
    skip("setenv.sh 不存在")

# 4. run-obsidian-pipeline.sh 改为读 setenv.sh 的变量
print("\n[4/10] run-obsidian-pipeline.sh NOTEBOOKLM_VENV 修正")
fp = os.path.join(SCRIPTS_DIR, "run-obsidian-pipeline.sh")
if os.path.isfile(fp):
    with open(fp) as f:
        content = f.read()
    old = 'NOTEBOOKLM_VENV="$HOME/.hermes/notebooklm_venv/bin/python"'
    new = 'NOTEBOOKLM_VENV="${NOTEBOOKLM_VENV:-/Users/liuwei/.hermes/notebooklm_venv/bin/python}"'
    if old in content:
        if "--apply" in sys.argv:
            with open(fp, "w") as f:
                f.write(content.replace(old, new))
            act("替换 NOTEBOOKLM_VENV 为 ${NOTEBOOKLM_VENV:-绝对路径}")
        else:
            info("需替换 NOTEBOOKLM_VENV 行")
    else:
        ok("已修复")
else:
    skip("文件不存在")

# ── P1: 中度问题 ──
print("\n" + "━" * 56)
print("🟡 P1: 中度问题修复")
print("━" * 56)

# 5. 删除 vault_daily_check.py
print("\n[5/10] 删除 orphan vault_daily_check.py")
fp = os.path.join(SCRIPTS_DIR, "vault_daily_check.py")
if os.path.isfile(fp):
    if "--apply" in sys.argv:
        os.remove(fp)
        act(f"已删除 {fp}")
    else:
        info(f"需删除 {fp} ({os.path.getsize(fp)}B)")
else:
    ok("已不存在")

# 6. 删除 orphan wrapper
print("\n[6/10] 删除 orphan wrappers")
for orphan in ["wrapper-autolink.sh", "vault_autolink_auto.sh"]:
    fp = os.path.join(SCRIPTS_DIR, orphan)
    if os.path.isfile(fp):
        if "--apply" in sys.argv:
            os.remove(fp)
            act(f"已删除 {orphan}")
        else:
            info(f"需删除 {orphan} ({os.path.getsize(fp)}B)")
    else:
        ok(f"{orphan} 已不存在")

# 7. setenv.sh 补 VAULT_BACKUP_DIR
print("\n[7/10] setenv.sh 补充 VAULT_BACKUP_DIR")
if os.path.isfile(SETENV):
    with open(SETENV) as f:
        content = f.read()
    if "VAULT_BACKUP_DIR" not in content:
        new_line = 'export VAULT_BACKUP_DIR="/Users/liuwei/VaultBackups/obsidian-vault"\n'
        if "--apply" in sys.argv:
            with open(SETENV, "a") as f:
                f.write(new_line)
            act("添加 VAULT_BACKUP_DIR 到 setenv.sh")
        else:
            info("需添加 VAULT_BACKUP_DIR 到 setenv.sh")
    else:
        ok("VAULT_BACKUP_DIR 已定义")
else:
    skip("setenv.sh 不存在")

# 8. vault-backup.sh 改为读 setenv.sh 变量
print("\n[8/10] vault-backup.sh 硬编码路径 → setenv 变量")
fp = os.path.join(SCRIPTS_DIR, "vault-backup.sh")
if os.path.isfile(fp):
    with open(fp) as f:
        content = f.read()
    hardcoded = '/Users/liuwei/VaultBackups/obsidian-vault'
    if hardcoded in content and "VAULT_BACKUP_DIR" not in content:
        if "--apply" in sys.argv:
            new_content = content.replace(
                f'BACKUP_DIR="{hardcoded}"',
                'BACKUP_DIR="${VAULT_BACKUP_DIR:-' + hardcoded + '}"'
            )
            with open(fp, "w") as f:
                f.write(new_content)
            act("替换 vault-backup.sh 为变量引用")
        else:
            info("需替换硬编码路径为 ${VAULT_BACKUP_DIR:-...}")
    else:
        ok("已是变量引用")
else:
    skip("vault-backup.sh 不存在")

# ── P2: 文档同步 ──
print("\n" + "━" * 56)
print("🟢 P2: 文档同步")
print("━" * 56)

# 9. 归档 XHS 脚本
print("\n[9/10] 清理 XHS 僵尸脚本")
if not skip_cleanup:
    xhs_dir = os.path.join(SCRIPTS_DIR, "_archived_xhs")
    xhs_files = [f for f in os.listdir(SCRIPTS_DIR) if f.startswith("xhs_")]
    if xhs_files:
        if "--apply" in sys.argv:
            os.makedirs(xhs_dir, exist_ok=True)
            for f in xhs_files:
                shutil.move(os.path.join(SCRIPTS_DIR, f), os.path.join(xhs_dir, f))
            act(f"已归档 {len(xhs_files)} 个 XHS 文件到 {xhs_dir}")
        else:
            info(f"需归档 {len(xhs_files)} 个 XHS 文件: {', '.join(xhs_files[:5])}...")
    else:
        ok("无 XHS 文件")
else:
    skip("--skip-cleanup 跳过")

# 10. 更新 SKILL.md 同步
print("\n[10/10] SKILL.md 同步 (手动)")
info("需更新: 时间线 19:00→21:00、润色 ~07:30→05:00、Usage 中的 vault_daily_check.py")
info("需更新: references/schedule-optimization.md 最终调度表")
if "--apply" in sys.argv:
    skip("文档同步需手动编辑，--apply 不处理此项")

# ── 总结 ──
print("\n" + "═" * 56)
completed = [False] * 10
if "--apply" in sys.argv:
    print(" ✅ 已执行 --apply，修改已完成")
else:
    print(" ℹ️  这是 dry-run（未做任何修改）")
    print("    重新执行: python3 post-reboot-restore.py --apply")
    print("    跳过清理: python3 post-reboot-restore.py --apply --skip-cleanup")
print("═" * 56)
