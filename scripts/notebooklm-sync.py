#!/usr/bin/env python3
"""
notebooklm-sync.py — v3
P0: 同步状态看板 (_同步状态.md 写入 Obsidian)
P1: Session 过期预检 + 醒目预警
P3: 文件名+修改时间去重，检测旧版本
P4: 50 来源上限自动创建新 notebook（上限已取消，设为极大值）

上传方式 v3: 使用 Playwright file chooser + 点击"上传文件"按钮
"""

import os
import sys
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

SESSION_DIR = Path("/Users/liuwei/.hermes/notebooklm_session")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
CONTEXT_FILE = SESSION_DIR / "context.zip"
STATE_FILE = SESSION_DIR / "sync_state.json"
EXPORT_DIR = Path("/Users/liuwei/Desktop/NotebookLM-导出")
VAULT = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
)

NOTEBOOK_BASE_NAME = "Hermes-知识归档"
MAX_SOURCES_PER_NOTEBOOK = 300  # NotebookLM 免费版上限
BATCH_SIZE = 100  # 一次上传所有文件


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "uploaded_files": {},
        "notebooks": [],
        "notebook_uuids": {},  # name -> uuid 映射
        "sync_history": []
    }


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def file_fingerprint(filepath: Path) -> str:
    """文件名 + 修改时间 + 大小的组合指纹"""
    stat = filepath.stat()
    return f"{filepath.name}|{stat.st_mtime}|{stat.st_size}"


def get_today_export_dir():
    """找今天最新的导出目录"""
    if not EXPORT_DIR.exists():
        return None
    dirs = sorted([d for d in EXPORT_DIR.iterdir() if d.is_dir() and d.name.startswith("20")])
    return dirs[-1] if dirs else None


def collect_files(export_dir: Path) -> list[dict]:
    """收集导出目录下所有 .md 文件及其指纹"""
    files = []
    for f in sorted(export_dir.rglob("*.md")):
        if f.name == "README.md":
            continue
        files.append({
            "path": f,
            "relative": str(f.relative_to(export_dir)),
            "fingerprint": file_fingerprint(f),
        })
    return files


def get_new_and_updated(state: dict, files: list[dict]) -> list[dict]:
    """返回新文件 + 内容有更新的文件"""
    uploaded = state.get("uploaded_files", {})
    result = []
    for f in files:
        rel = f["relative"]
        if rel not in uploaded:
            result.append(f)  # 新文件
        elif uploaded[rel].get("fingerprint") != f["fingerprint"]:
            result.append(f)  # 已更新
    return result


def get_next_notebook_name(state: dict) -> str:
    """找到可用的 notebook 名称"""
    notebooks = state.get("notebooks", [])
    for nb in notebooks:
        if nb["source_count"] < MAX_SOURCES_PER_NOTEBOOK:
            return nb["name"]
    count = len(notebooks)
    if count == 0:
        return NOTEBOOK_BASE_NAME
    else:
        return f"{NOTEBOOK_BASE_NAME}-{count + 1}"


def write_sync_dashboard(state: dict, status: str, message: str, uploaded_count: int):
    """P0: 写入同步状态看板到 Obsidian"""
    dashboard_path = Path(VAULT) / "_同步状态.md"
    
    today = datetime.now().strftime("%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_icon = {"ok": "✅", "partial": "⚠️", "error": "❌", "skip": "⏭️"}.get(status, "❓")

    history = state.get("sync_history", [])
    history = history[-14:]
    
    today_record = {
        "date": today,
        "status": status_icon,
        "uploaded": uploaded_count,
        "message": message
    }
    history = [h for h in history if h.get("date") != today]
    history.append(today_record)

    lines = [
        "# 📊 同步状态看板",
        "",
        f"> 最后更新: {now}",
        "",
        "## 每日同步记录",
        "",
        "| 日期 | 整理 | 导出 | 上传 | 说明 |",
        "|------|:----:|:----:|:----:|------|",
    ]
    
    for h in history:
        d = h["date"]
        s = h["status"]
        cnt = h["uploaded"]
        msg = h.get("message", "")
        if s == "✅":
            lines.append(f"| {d} | ✅ | ✅ | ✅({cnt}) | {msg} |")
        elif s == "⚠️":
            lines.append(f"| {d} | ✅ | ✅ | ⚠️({cnt}) | {msg} |")
        elif s == "⏭️":
            lines.append(f"| {d} | ✅ | ✅ | ⏭️ | {msg} |")
        else:
            lines.append(f"| {d} | ✅ | ✅ | ❌ | {msg} |")
    
    lines.append("")
    
    if status == "error" and "session" in message.lower():
        lines.append("---")
        lines.append("")
        lines.append("## ⚠️ 需要你操作")
        lines.append("")
        lines.append("NotebookLM 的登录 session 已过期。在终端运行：")
        lines.append("")
        lines.append("```bash")
        lines.append("python3 ~/.hermes/scripts/notebooklm-setup.py login")
        lines.append("```")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append(f"_自动更新于 {now}_")
    
    dashboard_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ 同步状态看板已更新: {dashboard_path}")


def save_file_state(state: dict, fp: dict, notebook_name: str):
    """增量保存单个文件的上传状态"""
    rel = fp["relative"]
    state.setdefault("uploaded_files", {})[rel] = {
        "fingerprint": fp["fingerprint"],
        "notebook": notebook_name,
        "uploaded_at": datetime.now().isoformat()
    }
    save_state(state)


def upload_files_v3(files: list[dict], notebook_name: str) -> dict:
    """
    v3 上传方法：
    使用 Playwright file chooser 事件 + 点击"上传文件"按钮，
    真正触发 NotebookLM 的文件上传。
    """
    if not CONTEXT_FILE.exists():
        return {"success": False, "message": "没有保存的 session。请先运行: notebooklm-setup.py login",
                "session_expired": True}
    
    from playwright.sync_api import sync_playwright
    
    state = load_state()
    uploaded_count = 0
    total = len(files)
    notebook_uuids = state.get("notebook_uuids", {})

    print(f"  → 需上传 {len(files)}/{total} 个文件")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome", headless=True,
            args=["--no-sandbox"]
        )
        context = browser.new_context(
            storage_state=str(CONTEXT_FILE),
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        # 设置 Timeout 为 15 秒
        page.set_default_timeout(60000)

        try:
            # ── 判断是否已有 notebook UUID ──
            existing_uuid = notebook_uuids.get(notebook_name)
            
            if existing_uuid:
                # 已有 notebook，直接导航进入
                print(f"  → 打开已有 Notebook: {notebook_name}")
                page.goto(
                    f"https://notebooklm.google.com/notebook/{existing_uuid}",
                    timeout=60000, wait_until="commit"
                )
                page.wait_for_timeout(3000)

                if "accounts.google.com" in page.url:
                    browser.close()
                    return {"success": False, "message": "Google session 已过期，请重新登录",
                            "session_expired": True}

                # 点击"添加来源"打开对话框
                add_btn = page.query_selector('button:has-text("添加来源")')
                if add_btn:
                    add_btn.click(force=True, timeout=5000)
                    page.wait_for_timeout(2000)
                    print("  → 已打开添加来源对话框")
                else:
                    # 尝试 URL 参数方式
                    page.goto(
                        f"https://notebooklm.google.com/notebook/{existing_uuid}?addSource=true",
                        timeout=60000, wait_until="commit"
                    )
                    page.wait_for_timeout(3000)
                    print("  → 通过 URL 参数打开添加来源对话框")
            else:
                # 首次创建：从首页新建 notebook
                print(f"  → 创建新 Notebook: {notebook_name}")
                page.goto("https://notebooklm.google.com", timeout=60000, wait_until="commit")
                page.wait_for_timeout(3000)

                if "accounts.google.com" in page.url:
                    browser.close()
                    return {"success": False, "message": "Google session 已过期，请重新登录",
                            "session_expired": True}

                # 点击 add 按钮创建新 notebook（多策略选择器）
                add_btn = page.query_selector(
                    'button:has-text("add"), button:has-text("新建"), mat-icon:has-text("add")'
                )
                if not add_btn:
                    # 备选：直接找 project-button 中的 add 区域
                    add_btn = page.query_selector('project-button:has-text("新建")')
                if add_btn:
                    add_btn.click(timeout=10000)
                    page.wait_for_timeout(3000)
                else:
                    browser.close()
                    return {"success": False, "message": "无法找到新建笔记本按钮",
                            "session_expired": False}
                
                # 捕获新 notebook 的 UUID
                if "/notebook/" in page.url:
                    existing_uuid = page.url.split("/notebook/")[1].split("?")[0].split("#")[0]
                    notebook_uuids[notebook_name] = existing_uuid
                    state["notebook_uuids"] = notebook_uuids
                    save_state(state)
                    print(f"  → 新 Notebook UUID: {existing_uuid}")
                else:
                    browser.close()
                    return {"success": False, "message": "创建新 notebook 后未捕获到 UUID",
                            "session_expired": False}

            # ── 上传文件 ──
            # 分批上传
            current_handler = None

            def on_filechooser(chooser, paths):
                print(f"  → File chooser 触发，设置 {len(paths)} 个文件...")
                chooser.set_files(paths)

            for batch_start in range(0, len(files), BATCH_SIZE):
                batch = files[batch_start:batch_start + BATCH_SIZE]
                batch_paths = [str(fp["path"]) for fp in batch]
                
                # 注册 file_chooser 事件
                handler = lambda chooser, p=batch_paths: on_filechooser(chooser, p)
                current_handler = handler
                page.on("filechooser", handler)

                # 尝试多种方式触发文件上传
                upload_triggered = False
                
                # 方法1: 直接找 file input 并设置文件
                file_input = page.query_selector('input[type="file"]')
                if file_input:
                    file_input.set_input_files(batch_paths)
                    upload_triggered = True
                    print(f"  → 直接设置 file input，{len(batch_paths)} 个文件")
                
                # 方法2: 点击各种上传按钮
                if not upload_triggered:
                    for selector in [
                        'button:has-text("上传文件")',
                        'button:has-text("Upload")',
                        '[data-test-id*="upload"]',
                        '[aria-label*="upload" i]',
                        '[aria-label*="上传" i]',
                        'button:has-text("选择文件")',
                        'button:has-text("Choose")',
                    ]:
                        btn = page.query_selector(selector)
                        if btn:
                            btn.click(force=True, timeout=5000)
                            upload_triggered = True
                            print(f"  → 点击 {selector}")
                            break
                
                # 方法3: 点击对话框中的任何按钮（最后手段）
                if not upload_triggered:
                    # 截图调试
                    page.screenshot(path=f"/tmp/nblm_debug_{batch_start}.png")
                    print(f"  ⚠ 所有选择器失败，截图: /tmp/nblm_debug_{batch_start}.png")
                    # 尝试点击 drag-and-drop 区域
                    drop_zone = page.query_selector('[class*="drop"], [class*="upload"], [class*="drag"]')
                    if drop_zone:
                        drop_zone.click(timeout=5000)
                        print(f"  → 点击 drop zone")
                        upload_triggered = True
                
                if upload_triggered:
                    page.wait_for_timeout(5000)
                    page_text = page.evaluate('() => document.body.innerText')
                    batch_success = 0
                    for fp in batch:
                        file_key = Path(fp["relative"]).stem
                        if file_key in page_text:
                            save_file_state(state, fp, notebook_name)
                            uploaded_count += 1
                            batch_success += 1
                            print(f"  ✓ {fp['relative']}")
                        else:
                            print(f"  ⚠ 可能未上传: {fp['relative']}")
                    
                    if batch_success < len(batch):
                        print(f"  → 本批 {batch_success}/{len(batch)} 成功")
                else:
                    print(f"  ⚠ 未找到上传入口，跳过本批 {len(batch)} 个文件")
                
                # 移除 file_chooser 监听避免重复
                try:
                    page.remove_listener("filechooser", current_handler)
                except:
                    pass

                # 如果不是最后一批，重新导航打开对话框
                if batch_start + BATCH_SIZE < len(files):
                    page.goto(
                        f"https://notebooklm.google.com/notebook/{existing_uuid}?addSource=true",
                        timeout=60000, wait_until="commit"
                    )
                    page.wait_for_timeout(5000)

            # ── 关闭对话框 ──
            try:
                close_btn = page.query_selector('button:has-text("close")')
                if close_btn:
                    close_btn.click(force=True, timeout=5000)
            except:
                pass
            
            browser.close()
            
            return {
                "success": uploaded_count > 0,
                "count": uploaded_count,
                "total": total,
                "session_expired": False,
                "message": f"上传 {uploaded_count}/{total} 篇"
            }

        except Exception as e:
            browser.close()
            return {"success": uploaded_count > 0, "count": uploaded_count,
                    "total": total, "session_expired": False,
                    "message": f"上传异常（已保存 {uploaded_count}/{total} 篇）: {e}"}


def check_session_valid() -> tuple[bool, str]:
    """检查 context.zip 是否有效（24h 内）"""
    if not CONTEXT_FILE.exists():
        return False, "context.zip 不存在"
    age_hours = (datetime.now() - datetime.fromtimestamp(CONTEXT_FILE.stat().st_mtime)).total_seconds() / 3600
    if age_hours > 120:
        return False, f"session 已过期（{age_hours:.0f}h 前，阈值 120h）"
    return True, f"session 有效（{age_hours:.0f}h 前）"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--notebook', help='指定 notebook 名称（覆盖自动选择）')
    parser.add_argument('--category', help='仅处理指定分类子目录')
    args, _ = parser.parse_known_args()
    
    print("══════════ NotebookLM 自动同步 v3 ══════════")
    if args.notebook:
        print(f"📓 指定 Notebook: {args.notebook}")
    if args.category:
        print(f"📂 过滤分类: {args.category}")
    
    # P0: Session 预检
    session_ok, session_msg = check_session_valid()
    if not session_ok:
        state = load_state()
        print(f"❌ {session_msg}，跳过同步")
        write_sync_dashboard(state, "error", session_msg, 0)
        return
    
    state = load_state()
    
    # 找今天导出的目录
    export_dir = get_today_export_dir()
    if not export_dir:
        print("⏭️  没有找到今天的导出目录，跳过同步")
        write_sync_dashboard(state, "skip", "无导出数据", 0)
        return
    
    # 收集文件（可选按分类过滤）
    files = collect_files(export_dir)
    if args.category:
        files = [f for f in files if f['relative'].startswith(args.category + '/')]
        print(f"📂 过滤后: {len(files)} 个文件（分类: {args.category}）")
    if not files:
        print("⏭️  导出目录为空或无匹配文件，跳过同步")
        write_sync_dashboard(state, "skip", "无笔记文件", 0)
        return
    
    # P3: 检测新文件 + 已更新的文件
    pending = get_new_and_updated(state, files)
    
    if not pending:
        print(f"📭 无新文件或更新文件（共 {len(files)} 篇已同步）")
        write_sync_dashboard(state, "ok", "全部已是最新", 0)
        return
    
    print(f"📄 发现 {len(pending)} 个需要同步的文件")
    
    # P4: 找到合适的 notebook
    if args.notebook:
        notebook_name = args.notebook
    else:
        notebook_name = get_next_notebook_name(state)
    print(f"📓 目标 Notebook: {notebook_name}")
    
    # 上传（v3 方法）
    try:
        result = upload_files_v3(pending, notebook_name)
    except Exception as e:
        updated_state = load_state()
        updated_state["last_sync"] = datetime.now().isoformat()
        write_sync_dashboard(updated_state, "error", f"上传异常: {e}", 0)
        print(f"❌ {e}")
        return
    
    # 重新读取最新 state（via upload_files_v3 内部可能已更新）
    updated_state = load_state()
    uploaded_count = result.get("count", 0) if isinstance(result, dict) else 0
    
    if uploaded_count > 0 or result.get("success"):
        # P4: 更新 notebook 来源计数
        nb_found = False
        for nb in updated_state.get("notebooks", []):
            if nb["name"] == notebook_name:
                nb["source_count"] = nb.get("source_count", 0) + uploaded_count
                nb_found = True
                break
        if not nb_found and uploaded_count > 0:
            updated_state.setdefault("notebooks", []).append({
                "name": notebook_name,
                "source_count": uploaded_count,
                "created_at": datetime.now().strftime("%Y-%m-%d")
            })
        
        updated_state["last_sync"] = datetime.now().isoformat()
        save_state(updated_state)
        dashboard_status = "ok" if result.get("success", False) else "partial"
        write_sync_dashboard(updated_state, dashboard_status, result["message"], uploaded_count)
        print(f"{'✅' if result.get('success') else '⚠️'} {result['message']}")

        # 来源数量接近上限时预警
        for nb in updated_state["notebooks"]:
            if nb["source_count"] >= MAX_SOURCES_PER_NOTEBOOK:
                print(f"⚠️  {nb['name']} 已有 {nb['source_count']} 个来源，接近上限！")
                print(f"   下次同步将自动创建新 notebook")
    
    elif result.get("session_expired"):
        write_sync_dashboard(updated_state, "error", result["message"], 0)
        print(f"❌ {result['message']}")
        print("   请在终端运行: python3 ~/.hermes/scripts/notebooklm-setup.py login")
    else:
        write_sync_dashboard(updated_state, "error", result["message"], 0)
        print(f"❌ {result['message']}")


if __name__ == "__main__":
    main()
