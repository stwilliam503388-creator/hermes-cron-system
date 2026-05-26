# Hermes 定时任务系统设计文档

> 版本: v3.0 | 更新: 2026-05-27 | 任务数: 35（24 Mini + 11 MacBook）
> 覆盖: MacBook (liuwei) + Mac Mini (apple)

---

## 目录

1. [系统架构](#1-系统架构)
2. [任务目录](#2-任务目录)
3. [脚本清单](#3-脚本清单)
4. [数据流与投递管线](#4-数据流与投递管线)
5. [可靠性机制](#5-可靠性机制)
6. [NotebookLM 集成](#6-notebooklm-集成)
7. [Mac Mini 双机部署](#7-mac-mini-双机部署)
8. [移植指南](#8-移植指南)
9. [踩坑记录](#9-踩坑记录)

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     iCloud Drive                             │
│            Obsidian Vault (共享存储层)                        │
│  /Users/<user>/Library/Mobile Documents/com~apple~CloudDocs │
│                    /Obsidian Vault/                          │
└─────────────┬───────────────────────────┬───────────────────┘
              │                           │
    ┌─────────▼──────────┐     ┌──────────▼──────────┐
    │   MacBook (liuwei) │     │   Mac Mini (apple)   │
    │   便携 + 交互       │     │   24h 常驻 + 后台     │
    │                    │     │                      │
    │ ┌────────────────┐ │     │ ┌──────────────────┐ │
    │ │ Hermes TUI/CLI │ │     │ │ Hermes Gateway   │ │
    │ │ SOUL.md+Skills │ │     │ │ (minimal profile) │ │
    │ │ Memory (Mem0)  │ │     │ │ 24 cron jobs     │ │
    │ └───────┬────────┘ │     │ │ weixin gateway   │ │
    │         │          │     │ └────────┬─────────┘ │
    │ ┌───────▼────────┐ │     │          │           │
    │ │ 11 保留任务     │ │     │ ┌────────▼─────────┐ │
    │ │ 备份/管线/告警  │ │     │ │ LLM Agent Tasks  │ │
    │ │ NotebookLM      │ │     │ │ deepseek-v4-pro  │ │
    │ │ 交互式聊天      │ │     │ │ + flash (部分)   │ │
    │ └────────────────┘ │     │ │ HTTPS_PROXY=     │ │
    │                    │     │ │ 127.0.0.1:7890   │ │
    │ ClashX/代理        │     │ │ ClashX Meta      │ │
    │ Chrome+Playwright  │     │ └──────────────────┘ │
    └────────────────────┘     └──────────────────────┘

投递通道:
  Feishu: bot token (双机共用)
  WeChat: iLink WebSocket (Mini 持长连接)
  delivery-queue: 本地文件队列 (MacBook)
```

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **iCloud 单源** | Obsidian vault 通过 iCloud 共享，两台机器读写同路径 |
| **职责硬分割** | Mini 写资讯/日报/对话归档，MacBook 写概念/工具笔记/参考 |
| **单一重试源** | 所有重试读 `jobs.json`，不维护独立状态文件 |
| **内容优先投递** | 先生成内容到 vault，再投递；投递失败不影响内容存在 |
| **no_agent 静默** | watchdog 模式：健康时 stdout 为空，异常时才输出 |
| **诊断 exit 0** | 健康检查/诊断脚本始终 exit 0，诊断结果写在输出里 |

### 关键路径

| 路径 | 值 | 说明 |
|------|-----|------|
| Vault | `~/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/` | iCloud 共享 |
| Hermes 配置 | `~/.hermes/profiles/minimal/` | 活动 profile |
| 脚本 | `~/.hermes/scripts/` | 所有 cron 脚本 |
| 任务定义 | `~/.hermes/profiles/minimal/cron/jobs.json` | 单一真相源 |
| 投递队列 | `~/.hermes/delivery-queue/{pending,sent}/` | 文件队列 |
| .env | `~/.hermes/profiles/minimal/.env` | API keys + 代理配置 |
| NotebookLM | `~/.hermes/notebooklm_session/` | session + 状态 |

---

## 2. 任务目录

### 2.1 任务总览

共 35 个定时任务，分 7 类：

| 类别 | 数量 | 运行位置 | 说明 |
|------|------|---------|------|
| LLM 内容生成 | 12 | Mini | Agent 模式，调 deepseek API 生成内容 |
| 概念知识库 | 5 | Mini | 脚本模式，处理 vault 概念卡片 |
| 微信投递 | 3 | Mini | 队列批量投递到微信 |
| Git 同步 | 2 | Mini | vault git 备份 |
| 自检/恢复 | 3 | Mini | 失败重试 + 网络恢复 |
| 备份/管线 | 5 | MacBook | 本地备份 + Obsidian 流水线 |
| 监控/报告 | 5 | 两端 | 告警、健康测试、错误报告 |

### 2.2 LLM 内容生成（12 个，Mini）

| ID | 名称 | 调度 | 模型 | 投递 |
|----|------|------|------|------|
| merged-morning-briefing | 晨间AI情报简报 | 07:00 | deepseek-v4-pro | origin,feishu |
| merged-evening-briefing | 晚间AI情报快讯 | 20:30 | deepseek-v4-pro | origin,feishu |
| 203327bd97ca | 每日AI Agent面试问答日报 | 12:00,20:00 | deepseek-v4-flash | origin,feishu |
| 81c3d765872a | AI Agent 每日内容生成(小红书+公众号) | 06:40 | deepseek-v4-flash | origin,feishu |
| ce30a76a3af9 | 豆瓣 Top250 每日一书解读 | 12:30 | deepseek-v4-flash | origin,feishu |
| 17a174a181df | 每日名言+解读 | 20:00 | deepseek-v4-flash | origin,feishu |
| 6aeb002b6f92 | 每日阅读清单 | 03:40 | deepseek-v4-flash | origin,feishu |
| 4b35124a30f2 | 周报自动生成 | 周五 17:00 | deepseek-v4-flash | origin,feishu |
| 8958f4ca8a19 | 播客转文字摘要 | 周日 10:00 | deepseek-v4-flash | origin,feishu |
| a4b2a4cf2ef2 | AI Agent PM 学习计划每日推送 | 04:10 | no_agent (script) | origin,feishu |
| f510eaee4ef0 | 内容工厂-早间 | 定时 | agent | - |
| a62879dcd3f7 | 内容工厂-午间 | 定时 | agent | - |

### 2.3 概念知识库（5 个，Mini）

| ID | 名称 | 调度 | 类型 | 脚本 |
|----|------|------|------|------|
| a52e754dc363 | 概念自动萃取 | 21:00 | no_agent | wrapper-concept-extract.py |
| dcaf6f6f5868 | 概念关联图谱重建 | 周一 08:00 | no_agent | wrapper-relation-builder.py |
| 57112dc39f45 | 概念卡片健康巡检 | 周日 09:00 | no_agent | wrapper-concept-health.py |
| nightly-concept-maintenance | 夜间概念知识库维护(去重+润色) | 01:30 | no_agent | wrapper-nightly-concept.py |
| 32a55060aba6 | 知识库自动维护 | 03:10 | no_agent | run_vault_maintenance.sh |

### 2.4 微信投递（3 个，Mini）

| ID | 名称 | 调度 | 脚本 |
|----|------|------|------|
| 86eb77b65850 | 微信早间批量投递 | 07:30 | wechat-batch-deliver.sh |
| 12ffc417c149 | 微信午间批量投递 | 13:00 | wechat-batch-deliver.sh |
| 4a643fb59586 | 微信晚间批量投递 | 21:00 | wechat-batch-deliver.sh |

### 2.5 Git 同步（2 个，Mini）

| ID | 名称 | 调度 | 脚本 | 说明 |
|----|------|------|------|------|
| 79d7420a567e | Obsidian vault git sync - morning | 06:20 | obsidian-git-sync.sh | Mini 错开 MacBook 的 06:20 |
| 470358e8520b | Obsidian vault git sync - evening | 23:00 | obsidian-git-sync.sh | 错开 MacBook 的 23:00 |

### 2.6 自检/恢复（3 个，Mini）

| ID | 名称 | 调度 | 类型 | 脚本 |
|----|------|------|------|------|
| unified-selfcheck-retry | 凌晨统一自检+失败重试 | 06:50 | no_agent | daily-midnight-check.py |
| 384e9ac0e21a | 网络恢复检测 | 每 2h | no_agent | network-recovery-check.py |
| 27b19b4e578b | 每日错误排查报告 | 23:00 | no_agent | daily-error-report.py |

### 2.7 备份/管线（5 个，MacBook）

| ID | 名称 | 调度 | 脚本 | 说明 |
|----|------|------|------|------|
| d1ceaef1eb49 | Obsidian Vault 独立备份 | 00:40 | vault-backup.sh | 7 天滚动 + 4 周保留 |
| 2d9526c8a5c4 | Obsidian 每日凌晨自动流水线 | 01:50 | wrapper-obsidian-pipeline.sh | 对话归档→概念萃取→导出 |
| 36946ce6a46a | config-backup | 每 6h | config-backup.sh | Hermes 配置备份 |
| 9ebece959732 | Hermes 配置周备份 | 周日 03:00 | hermes-backup.sh | 完整配置归档 |
| 4e19c6f630b1 | 浏览器标签页归档 | 23:00 | browser-tabs-archive.sh | 归档 Chrome 标签页 |

### 2.8 监控/报告（5 个，两端）

| ID | 名称 | 调度 | 位置 | 脚本 |
|----|------|------|------|------|
| 09a23c339f1f | 系统告警监控 | 每小时 | MacBook | system-alert.sh |
| 3feaafa67345 | Obsidian orphan checker | 07:35 | MacBook | orphan_checker.py |
| e1c5401f5085 | 全链路健康测试 | 周一 08:00 | MacBook | end-to-end-health.py |
| 2e6319697f57 | NotebookLM session 每日续期 | 03:00 | MacBook | notebooklm-session-keepalive.py |
| notebooklm-upload | NotebookLM 上传同步 | 02:00 | MacBook | wrapper-notebooklm-upload.sh |

### 2.9 其他（3 个，Mini）

| ID | 名称 | 调度 | 类型 |
|----|------|------|------|
| 3170f3242e88 | 视频队列自动转写 | 08:00,14:00,20:00 | no_agent |
| bf1675cf55e9 | 内容工厂-每日索引统计 | 定时 | no_agent |
| 9666b7eb7e5e | 变现管道周报 | 周日 | agent |

---

## 3. 脚本清单

### 3.1 核心基础设施

| 脚本 | 语言 | 功能 | 关键依赖 |
|------|------|------|---------|
| `setenv.sh` | Bash | 统一环境变量（HOME、VAULT_PATH） | 被所有脚本 source |
| `notify.sh` | Bash | 统一通知推送 | hermes send |

### 3.2 备份与同步

| 脚本 | 功能 | 可靠性特性 |
|------|------|-----------|
| `vault-backup.sh` | Vault rsync 快照 + 7天/4周保留 | `set -uo pipefail`（无 `set -e`），手动退出码检查 |
| `obsidian-git-sync.sh` | git add → commit → pull-rebase → push | 500KB log 轮转，空变更静默退出 |
| `config-backup.sh` | Hermes 配置备份 | 每 6h |
| `hermes-backup.sh` | 完整配置 tar.zst 归档 | 每周 |

### 3.3 Vault 维护

| 脚本 | 功能 |
|------|------|
| `run-obsidian-pipeline.sh` | 凌晨流水线：对话归档→概念萃取→导出→上传 |
| `export-obsidian-to-notebooklm.sh` | 按 7 分类导出清洁笔记（去噪声/Category注入） |
| `run_vault_maintenance.sh` | 自动补链→健康巡检→索引更新→过期检测 |
| `vault_autolink.py` | 自动补链孤岛笔记 |
| `vault_health.py` | 健康巡检（孤岛/老化/悬浮链接统计） |
| `vault_master_index_update.py` | 更新知识库总索引 |
| `orphan_checker.py` | 检测新孤岛文件并自动链接 |

### 3.4 概念卡片

| 脚本 | 功能 | 关键参数 |
|------|------|---------|
| `wrapper-concept-extract.py` | 从对话归档萃取概念 → 生成卡片 | 21:00 执行 |
| `wrapper-concept-dedup.py` | 概念去重 | 被 nightly-concept 调用 |
| `wrapper-llm-polish.py` | LLM 润色概念卡片（离线跳过）| 网络检查前置 |
| `wrapper-nightly-concept.py` | 合并 dedup + polish 链 | 01:30 |
| `wrapper-concept-health.py` | 概念卡片健康巡检 | 周日 09:00 |
| `wrapper-relation-builder.py` | 概念关联图谱重建 | 周一 08:00 |

### 3.5 投递

| 脚本 | 功能 | 特性 |
|------|------|------|
| `wechat-batch-deliver.sh` | 队列批量投递到微信 | iconv UTF-8 过滤、30 天过期清理、并发锁、8 条/次上限 |

### 3.6 监控与恢复

| 脚本 | 功能 | 调度 |
|------|------|------|
| `daily-midnight-check.py` | NotebookLM 检查→失败重试→索引过期检测 | 06:50 |
| `network-recovery-check.py` | 网络+代理检测→失败任务重试 | 每 2h |
| `daily-error-report.py` | 全量错误报告（含投递统计+NotebookLM状态）| 23:00 |
| `end-to-end-health.py` | 5 环节全链路健康测试 | 周一 08:00 |
| `system-alert.sh` | 系统告警（含 Mini 心跳检测）| 每小时 |
| `offline_guard.py` | 离线守卫（手动使用，不参与 cron 自动重试）| - |

### 3.7 NotebookLM

| 脚本 | 功能 |
|------|------|
| `notebooklm-sync.py` | Playwright 浏览器自动上传到 NotebookLM (v3) |
| `notebooklm-session-keepalive.py` | 每日打开 NotebookLM 刷新 cookie 续期 |
| `wrapper-notebooklm-upload.sh` | 按 7 分类逐一上传调度器 |
| `notebooklm-setup.py` | 初次登录：打开 Chrome 完成 Google 认证 |
| `notebooklm-session-extract.py` | 从已运行 Chrome 提取 session |
| `notebooklm-extract.py` | 从临时 Chrome profile 提取 session |

### 3.8 视频与学习

| 脚本 | 功能 |
|------|------|
| `video-queue-processor.py` | yt-dlp 下载 + faster-whisper 转写 |
| `learning-plan-push-day1.py` | AI Agent PM 学习内容推送 |

---

## 4. 数据流与投递管线

### 4.1 内容生成全链路

```
Agent cron job (LLM 生成)
  │
  ├─► 写入 Obsidian vault (iCloud)
  │     └─► iCloud 自动同步到另一台设备
  │
  ├─► deliver: origin,feishu
  │     └─► Hermes Gateway 投递到飞书 + 微信
  │
  └─► (可选) 写入 delivery-queue/pending/
        └─► wechat-batch-deliver.sh 读取 → 发送 → 移到 sent/
```

### 4.2 NotebookLM 同步链路

```
01:50  Obsidian 管线导出 
        export-obsidian-to-notebooklm.sh
        └─► Desktop/NotebookLM-导出/YYYY-MM-DD/
              ├─ 工具知识库/  (→ AI 知识库 · 工具笔记)
              ├─ 学习参考/    (→ AI 知识库 · 学习笔记)  
              ├─ 资讯趋势/    (→ AI 知识库 · 资讯)
              ├─ 工作流/      (→ AI 知识库 · 工作流)
              ├─ 概念/        (→ AI 知识库 · 概念)
              ├─ 对话归档/    (→ AI 知识库 · 对话归档)
              └─ 参考/        (→ AI 知识库 · 参考)

02:00  wrapper-notebooklm-upload.sh
        ├─ 检查 context.zip 年龄 (<120h)
        └─► notebooklm-sync.py (Playwright + Chrome)
              └─► 按分类上传到对应 NotebookLM notebook

03:00  notebooklm-session-keepalive.py
        └─► 刷新 context.zip (cookie 续期)
```

### 4.3 投递队列架构

```
~/.hermes/delivery-queue/
├── pending/     # 待投递的 .txt 文件
│   ├── 20260526-1200-github-trending.txt
│   ├── 20260526-0000-knowledge-maint.txt
│   └── ...
└── sent/        # 已投递归档
    └── ... (30天自动清理)

wechat-batch-deliver.sh (07:30/13:00/21:00)
  ├─ 读取 pending/ 下 .txt 文件（最多 8 个/次）
  ├─ 每个文件截断到 500 字符
  ├─ 合并为一个 digest 消息
  ├─ hermes send → 微信
  ├─ 成功: 移动到 sent/
  └─ 失败: 保留在 pending/ 下次重试
```

### 4.4 投递通道

| 通道 | 协议 | 依赖 | 运行位置 |
|------|------|------|---------|
| Feishu | Bot Token API | HTTPS (需要代理) | Mini Gateway |
| WeChat | iLink WebSocket | 持久连接 | Mini Gateway |
| delivery-queue | 本地文件 | 无 | MacBook (写队列的任务留 MacBook) |

### 4.5 投递策略矩阵

| 任务类型 | 投递方式 | 原因 |
|---------|---------|------|
| Agent 内容生成 | `deliver: origin,feishu` | 内容直接投递飞书+微信 |
| 维护/备份脚本 | `deliver: local` | 仅记录日志 |
| 诊断/健康 | `deliver: local` | 仅记录日志 |
| 错误报告 | `deliver: origin,feishu` | 用户需要看到 |

---

## 5. 可靠性机制

### 5.1 三层恢复体系

```
Layer 1: network-recovery-check (每 2h)
  ├─ 网络检测 (baidu.com)
  ├─ 代理检测 (deepseek API via proxy)
  ├─ 扫描 jobs.json 中 error/timeout 任务
  ├─ 跳过高频任务 (每小时/每 2h)
  └─ 重试: hermes cron run <id> 或 直接执行脚本

Layer 2: daily-midnight-check (06:50)
  ├─ NotebookLM 同步状态检查 → 触发重试
  ├─ 扫描 jobs.json 中 error/timeout 任务
  ├─ 每轮最多重试 5 个任务
  └─ 索引过期检测 (仅警告)

Layer 3: daily-error-report (23:00)
  ├─ 全量错误汇总
  ├─ 投递队列统计 (pending/sent)
  ├─ NotebookLM session 状态
  ├─ content-OK-but-delivery-failed 任务列表
  └─ 仅诊断，不重试
```

### 5.2 防崩溃设计

| 防护 | 实现 |
|------|------|
| UTF-8 崩溃 | 所有 `subprocess.run` 加 `encoding='utf-8', errors='replace'` |
| HOME 路径错误 | cron 脚本硬编码绝对路径，Python 脚本检测 `HOME` 前缀 |
| Git push rejected | pull-rebase 前置，日志轮转 500KB |
| 投递失败 | 内容先生成到 vault，投递失败不影响内容 |
| 过期索引误报 | `warn()` 而非 `fail()`，始终 exit 0 |
| 关联数组崩溃 | macOS bash 3.2 不支持 `declare -A` 中文 key → 显式调用 |
| macOS echo 多字节 bug | 全角括号 `（）` + 变量扩展 → 改用 `printf` |

### 5.3 网络与代理

```
.env 配置:
  HTTPS_PROXY=http://127.0.0.1:7890
  https_proxy=http://127.0.0.1:7890
  HTTP_PROXY=http://127.0.0.1:7890
  http_proxy=http://127.0.0.1:7890
  ALL_PROXY=http://127.0.0.1:7890

代理客户端: ClashX Meta (Mini) / ClashX (MacBook)
代理端口: 127.0.0.1:7890
代理检测: curl --proxy http://127.0.0.1:7890 https://api.deepseek.com/v1/models
成功标志: HTTP 401 (通但无 auth header) 或 HTTP 200
```

### 5.4 监控指标

| 指标 | 检测方式 | 报警阈值 |
|------|---------|---------|
| Mini 离线 | iCloud .heartbeat 文件 | >4h 未更新 |
| Mini 不可达 | ping Tailscale IP | 连续 3 次失败 |
| NotebookLM session | context.zip mtime | >120h |
| NotebookLM 同步 | sync_state.json last_sync | >48h |
| 投递队列积压 | pending/ 文件数 | >5 |
| Git 同步 | push exit code | exit ≠ 0 |
| 代理不可用 | proxy check curl | 超时或 5xx |

---

## 6. NotebookLM 集成

### 6.1 架构

```
Obsidian Vault (iCloud)
  │
  ├─ 01:50 export-obsidian-to-notebooklm.sh
  │     └─ 按 7 分类导出清洁 .md 到桌面
  │
  ├─ 02:00 wrapper-notebooklm-upload.sh
  │     ├─ context.zip 年龄检查 (<120h)
  │     └─ notebooklm-sync.py
  │           ├─ Playwright + Chrome (headless)
  │           ├─ storageState: context.zip
  │           ├─ 指纹去重 (文件名+mtime+size)
  │           ├─ 按分类上传到 7 个 NotebookLM notebook
  │           └─ 写入 sync_state.json + _同步状态.md
  │
  └─ 03:00 notebooklm-session-keepalive.py
        └─ 刷新 context.zip (cookie 续期)
```

### 6.2 Session 管理

| 文件 | 用途 | 有效期 |
|------|------|--------|
| `context.zip` | Playwright storageState (Google cookies) | ~14 天 (Google) |
| `sync_state.json` | 已上传文件指纹 + 同步历史 | 永久 |
| `temp_chrome_profile/` | 临时 Chrome profile | 手动创建 |

### 6.3 NotebookLM 分类映射

| Obsidian 目录 | 导出目录 | NotebookLM notebook |
|--------------|---------|-------------------|
| 工具笔记 | 工具知识库 | AI 知识库 · 工具笔记 |
| 学习笔记 | 学习参考 | AI 知识库 · 学习笔记 |
| 资讯 | 资讯趋势 | AI 知识库 · 资讯 |
| 工作流 | 工作流 | AI 知识库 · 工作流 |
| 概念 | 概念 | AI 知识库 · 概念 |
| 对话归档 | 对话归档 | AI 知识库 · 对话归档 |
| 参考 | 参考 | AI 知识库 · 参考 |

### 6.4 Session 续期机制

三层防御：
1. 阈值 20h → 120h（Google cookie 实际 14 天，120h 安全）
2. 每日 03:00 keepalive 刷新 timestamp
3. Playwright 重定向检测 (`accounts.google.com` → 真正过期)

若 session 真的过期，需在 MacBook 运行：
```bash
python3 ~/.hermes/scripts/notebooklm-setup.py login
```

---

## 7. Mac Mini 双机部署

### 7.1 设备分工

| 设备 | 角色 | 任务数 |
|------|------|--------|
| Mac Mini (apple) | 24h 后台运行 | 24 (LLM 内容 + 概念 + 投递 + Git + 自检) |
| MacBook (liuwei) | 便携 + 交互 | 11 (备份 + 管线 + NotebookLM + 告警 + 聊天) |

### 7.2 同步机制

| 数据 | 方式 |
|------|------|
| Obsidian vault | iCloud Drive (同 Apple ID，同路径) |
| Git 备份 | 两端各 push（时间错开：MacBook 06:20/23:00，Mini 09:00/21:00） |
| Hermes 配置 | `sync-to-mini` alias (rsync scripts + config + .env) |
| Memory | Mem0 云端 (API key 共享) |
| Skills | 初始 tar + 后续 sync-to-mini |
| 微信消息 | Mini 持长连接，MacBook 通过 SSH 隧道调用 |

### 7.3 Mini 部署步骤摘要

```bash
# 前置条件
- 同 Apple ID，iCloud Drive 已开启
- ClashX Meta 代理运行 (127.0.0.1:7890)
- Chrome 已安装
- SSH 远程登录已启用

# 1. 安装 Hermes
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sh

# 2. 同步配置（MacBook 上执行）
MACMINI="apple@<mini-ip>"
rsync -avz --delete ~/.hermes/scripts/ $MACMINI:.hermes/scripts/
rsync -avz ~/.hermes/profiles/minimal/ $MACMINI:.hermes/profiles/minimal/
# 然后修正所有路径: /Users/liuwei → /Users/apple

# 3. 停用 MacBook 保留任务（在 jobs.json 中设 enabled: false）

# 4. 启动网关（关键：必须指定 profile）
hermes --profile minimal gateway start
# NOT: hermes gateway start  ← 会跑在 default profile
```

### 7.4 部署踩坑

| 坑 | 症状 | 修复 |
|----|------|------|
| 用户名不同 | 路径硬编码 `/Users/liuwei` 全崩 | `sed s/liuwei/apple/g` |
| gateway 跑在 default profile | `cron list` 显示 "No scheduled jobs" | `--profile minimal` |
| .env 第 19 行 `@` 未引号 | `python-dotenv could not parse` | 加双引号 |
| root .env 未闭合引号 | 同上 | `EMAIL_SMTP_HOST='` → `EMAIL_SMTP_HOST=''` |
| `--no-chat` 不存在 (v0.14.0) | gateway 启动失败 | 直接 `gateway start` |

---

## 8. 移植指南

### 8.1 移植到新 Mac 的完整步骤

#### 步骤 1：环境准备

```bash
# 安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装依赖
brew install git python@3.11 node curl

# 安装 ClashX 或等效代理客户端
# 配置代理订阅，确保 127.0.0.1:7890 可用
```

#### 步骤 2：设置 iCloud

```
系统设置 → Apple ID → iCloud → iCloud Drive → 打开
等待 Obsidian Vault 同步完成（Finder 侧边栏可见）
```

#### 步骤 3：安装 Hermes

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sh
source ~/.zshrc
```

#### 步骤 4：同步配置（从源机器）

```bash
# 从源机器打包
cd ~/.hermes
tar czf /tmp/hermes-migrate.tar.gz \
  profiles/minimal/config.yaml \
  profiles/minimal/.env \
  profiles/minimal/SOUL.md \
  profiles/minimal/skills/ \
  scripts/

# 传输到目标机器
scp /tmp/hermes-migrate.tar.gz user@target:.hermes/

# 在目标机器解压
cd ~/.hermes
tar xzf hermes-migrate.tar.gz

# 修正路径（如果用户名不同）
cd scripts
find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.json" \) \
  -exec sed -i '' 's|/Users/<olduser>|/Users/<newuser>|g' {} +
```

#### 步骤 5：修正 .env

```bash
# 检查并修复 .env 问题
# 1. 引号闭合
grep "'$" ~/.hermes/.env ~/.hermes/profiles/minimal/.env

# 2. @ 字符引号
grep '@' ~/.hermes/profiles/minimal/.env | grep -v '"'

# 3. 代理配置（确认端口）
grep -i proxy ~/.hermes/profiles/minimal/.env

# 验证 dotenv 可解析
python3 -c "import dotenv; dotenv.load_dotenv('$HOME/.hermes/.env'); print('OK')"
python3 -c "import dotenv; dotenv.load_dotenv('$HOME/.hermes/profiles/minimal/.env'); print('OK')"
```

#### 步骤 6：迁移任务

```bash
# 从源机器的 jobs.json 选择要迁移的任务
# 方法 A: 全量复制（在源机器）
python3 << 'PYEOF'
import json
with open("~/.hermes/profiles/minimal/cron/jobs.json") as f:
    data = json.load(f)
# 修正路径
for j in data["jobs"]:
    if j.get("script") and "/Users/olduser" in str(j["script"]):
        j["script"] = j["script"].replace("/Users/olduser", "/Users/newuser")
with open("/tmp/jobs-portable.json", "w") as f:
    json.dump(data, f, indent=2)
PYEOF

# 方法 B: 手动创建（推荐逐个验证）
hermes --profile minimal cron create \
  --name "任务名" \
  --schedule "0 7 * * *" \
  --script "script-name.py" \
  --no-agent \
  --deliver local
```

#### 步骤 7：启动

```bash
# 关键：指定 profile
hermes --profile minimal gateway start

# 验证
hermes --profile minimal cron list | head -5
hermes --profile minimal cron status
```

#### 步骤 8：持续同步

```bash
# 添加到 ~/.zshrc
alias sync-hermes='rsync -avz --delete \
  ~/.hermes/scripts/ source-machine:.hermes/scripts/ && \
  rsync -avz ~/.hermes/profiles/minimal/config.yaml \
    source-machine:.hermes/profiles/minimal/config.yaml && \
  echo "✅ synced"'
```

### 8.2 路径修正清单

移植时必须检查和修正以下路径引用：

| 位置 | 旧值 | 新值 | 修正方式 |
|------|------|------|---------|
| `scripts/*.py` | `/Users/liuwei/` | `/Users/<new>/` | sed |
| `scripts/*.sh` | `/Users/liuwei/` | `/Users/<new>/` | sed |
| `jobs.json` | `/Users/liuwei/` | `/Users/<new>/` | Python 脚本 |
| `config.yaml` | 无硬编码路径 | - | 无需修改 |
| `.env` | API keys | 不变 | 直接复制 |

### 8.3 移植验证清单

- [ ] `hermes --version` 正常
- [ ] `hermes --profile minimal config list` 显示配置
- [ ] `python3 -c "import dotenv; dotenv.load_dotenv(...); print('OK')"` 两次（root + profile）
- [ ] `curl --proxy http://127.0.0.1:7890 https://api.deepseek.com/v1/models` → 401
- [ ] `ls "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/"` vault 可访问
- [ ] `hermes --profile minimal cron list` 显示任务
- [ ] `hermes --profile minimal send --to feishu "test"` 飞书投递正常
- [ ] 手动触发一个 cron 任务并验证 vault 写入

---

## 9. 踩坑记录

### 9.1 macOS 特有陷阱

| 陷阱 | 症状 | 修复 |
|------|------|------|
| bash 3.2 `declare -A` 中文 key | `syntax error: invalid arithmetic operator` | 显式函数调用替代关联数组 |
| bash echo 多字节字符 | UTF-8 字节损坏，位置 31 出现 `0xbc` | 改用 `printf` |
| `sed -i` 需要备份后缀 | macOS 要求 `sed -i ''`，Linux 是 `sed -i` | 统一用 `sed -i ''` |
| `stat` 参数差异 | macOS `stat -f %z`，Linux `stat -c %s` | 用 Python 替代或条件判断 |
| `/tmp` 不自动清理 | 日志累积到重启才清 | 脚本内置轮转（500KB） |

### 9.2 Hermes 特有陷阱

| 陷阱 | 症状 | 修复 |
|------|------|------|
| cron HOME remapping | `Path.home()` 解析到 `~/.hermes/profiles/minimal/home/` | 硬编码绝对路径 |
| `jobs.json` schedule 是 dict | `schedule.count("*")` → AttributeError | `schedule.get("expr", "")` |
| gateway 默认 profile | cron list 显示 "No scheduled jobs" | `--profile minimal` |
| .env 解析错误级联 | 配置加载不完整，任务不加载 | 检查 root + profile 两层 .env |
| no_agent stdout 编码 | `utf-8 codec can't decode byte 0xbc` | `encoding='utf-8', errors='replace'` |

### 9.3 网络相关

| 陷阱 | 症状 | 修复 |
|------|------|------|
| 代理端口冲突 | 部分任务 Connection error | 统一端口 7890 |
| HTTP_PROXY 不覆盖 HTTPS | urllib/httpx 直连超时 | 同时设 HTTPS_PROXY |
| Feishu SSL EOF | `UNEXPECTED_EOF_WHILE_READING` | 间歇性，重试解决 |

---

## 附录

### A. 文件清单

```
~/.hermes/
├── profiles/minimal/
│   ├── config.yaml           # Hermes 主配置
│   ├── .env                  # API keys + 代理
│   ├── SOUL.md               # Agent personality
│   ├── skills/               # 380 skills
│   └── cron/
│       └── jobs.json         # 40 任务定义（35 启用）
├── scripts/                  # 所有 cron 脚本 (~1.3MB)
├── plans/
│   └── mac-mini-deployment.md # Mac Mini 部署方案 v3
├── delivery-queue/           # 投递队列
│   ├── pending/
│   └── sent/
└── notebooklm_session/       # NotebookLM session
    ├── context.zip           # Playwright storageState
    └── sync_state.json       # 同步状态
```

### B. 调度时间线

```
00:40  vault-backup ───────────────────── [MacBook]
01:30  concept-nightly-maintenance ────── [Mini]
01:50  obsidian-pipeline ──────────────── [MacBook]
02:00  notebooklm-upload ──────────────── [MacBook]
03:00  notebooklm-keepalive ───────────── [MacBook]
03:10  vault-maintenance ──────────────── [Mini]
03:40  daily-reading-list ─────────────── [Mini]
04:10  learning-plan-push ─────────────── [Mini]
05:10  (空闲)
06:20  git-sync-morning ───────────────── [Mini]
06:40  content-generation ─────────────── [Mini]
06:50  unified-selfcheck ──────────────── [Mini]
07:00  morning-briefing ───────────────── [Mini]
07:30  wechat-deliver-morning ─────────── [Mini]
07:35  orphan-checker ─────────────────── [MacBook]
08:00  video-queue (第1轮) ────────────── [Mini]
09:00  git-sync-mini ──────────────────── [Mini]
12:00  interview-qa-report ────────────── [Mini]
12:30  douban-daily-book ──────────────── [Mini]
13:00  wechat-deliver-noon ────────────── [Mini]
14:00  video-queue (第2轮) ────────────── [Mini]
17:00  weekly-report (周五) ────────────── [Mini]
20:00  daily-quote ────────────────────── [Mini]
20:00  video-queue (第3轮) ────────────── [Mini]
20:30  evening-briefing ───────────────── [Mini]
21:00  concept-extract ────────────────── [Mini]
21:00  wechat-deliver-evening ─────────── [Mini]
23:00  git-sync-evening (Mini) ────────── [Mini]
23:00  error-report ───────────────────── [Mini]
23:00  browser-tabs-archive ───────────── [MacBook]

每小时: system-alert ──────────────────── [MacBook]
每 2h:  network-recovery-check ────────── [Mini]
每 6h:  config-backup ─────────────────── [MacBook]
```

### C. 模型使用策略

| 模型 | 使用场景 | 原因 |
|------|---------|------|
| deepseek-v4-pro | 晨间/晚间简报 | 质量优先（最重要的用户可见内容） |
| deepseek-v4-flash | 其他 LLM 内容 | 成本优化（12 个日常任务） |

---

> 文档生成: 2026-05-27 | Hermes v0.14.0 | macOS 15.7.3 / 26.5
