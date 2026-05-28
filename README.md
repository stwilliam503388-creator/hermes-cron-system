# Hermes Cron System

基于 [Hermes Agent](https://github.com/nousresearch/hermes-agent) 的自动化定时任务系统。

| 指标 | 数值 |
|------|------|
| 任务总数 | 40（34 启用 + 6 停用） |
| 脚本数 | 77（50 .py + 27 .sh） |
| Agent 提示词 | 13 |
| 投递通道 | 飞书 + 微信 + delivery-queue |
| 存储后端 | iCloud Drive (Obsidian Vault) |
| 双机部署 | Mac Mini (24) + MacBook (10 保留 + 6 停用) |
| 最新更新 | 2026-05-27 |

## 最近变更

| 日期 | 变更 |
|------|------|
| 05-27 | 脚本同步：obsidian-git-sync 加 pull-rebase + 日志轮转，notebooklm-sync 阈值调整，notebooklm-keepalive cookie 续期，wrapper-notebooklm-upload bash 3.2 兼容，wechat-batch-deliver encoding 修复，export-obsidian/run-vault-maintenance 路径修正 |
| 05-27 | 初始上传：系统设计文档 + Mac Mini 部署方案 + 脚本 + 提示词 + 配置 |

## 目录结构

```
├── README.md
├── system-design.md              # 系统设计文档（9章，含架构/数据流/移植指南）
├── mac-mini-deployment.md        # Mac Mini 双机部署方案（14风险对策）
├── config/
│   ├── config.yaml               # Hermes 配置（已脱敏）
│   ├── SOUL.md                   # Agent personality
│   └── cron-jobs-sanitized.json  # 40 任务定义（已脱敏）
├── scripts/                      # 77 个自动化脚本
│   ├── *.py                      # Python 脚本（vault维护/投递/监控/NotebookLM）
│   └── *.sh                      # Shell 脚本（备份/同步/管线）
└── prompts/                      # 13 个 Agent 任务提示词
```

## 任务分类

| 类别 | 数量 | 运行位置 |
|------|------|---------|
| LLM 内容生成 | 12 | Mac Mini |
| 概念知识库维护 | 5 | Mac Mini |
| 微信批量投递 | 3 | Mac Mini |
| Git 同步 | 2 | Mac Mini |
| 自检/恢复/报告 | 3 | Mac Mini |
| 备份/管线 | 5 | MacBook |
| 监控/健康/NotebookLM | 5 | MacBook |
| 其他（内容工厂/闲鱼/变现） | 5 | Mac Mini |

## 关键脚本

### 基础设施
- `setenv.sh` — 统一环境变量（被所有脚本 source）
- `notify.sh` — 统一通知推送

### Vault 维护
- `vault_autolink.py` — 自动补链孤岛笔记
- `vault_health.py` — 健康巡检
- `vault_master_index_update.py` — 知识库总索引更新
- `orphan_checker.py` — 新孤岛检测 + 自动补链
- `run_vault_maintenance.sh` — 知识库自动维护流水线

### 投递
- `wechat-batch-deliver.sh` — 队列批量微信投递（早中晚 ×3）

### 监控恢复
- `daily-midnight-check.py` — 凌晨统一自检（NotebookLM + 重试 + 索引检测）
- `network-recovery-check.py` — 每 2h 网络+代理检测 + 失败重试
- `daily-error-report.py` — 每日 23:00 全量错误报告
- `end-to-end-health.py` — 周一全链路 5 环节健康测试

### NotebookLM
- `notebooklm-sync.py` — Playwright 浏览器自动上传 (v3)
- `notebooklm-session-keepalive.py` — 每 6h cookie 续期
- `wrapper-notebooklm-upload.sh` — 7 分类上传调度器
- `export-obsidian-to-notebooklm.sh` — 清洁笔记导出

### Git 同步
- `obsidian-git-sync.sh` — vault git add/commit/pull-rebase/push + 日志轮转

## 快速开始

详见 [移植指南](system-design.md#8-移植指南) 和 [Mac Mini 部署方案](mac-mini-deployment.md)。

```bash
# 1. 安装 Hermes
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sh

# 2. 同步配置
rsync -avz scripts/ target:.hermes/scripts/
rsync -avz config/ target:.hermes/profiles/minimal/
# 修正路径: sed -i '' 's|<olduser>|<newuser>|g'

# 3. 启动（关键：必须指定 profile）
hermes --profile minimal gateway start
hermes --profile minimal cron list
```

## 设计原则

- **iCloud 单源** — Obsidian vault 共享，两台机器读写同路径
- **职责硬分割** — Mini 写资讯/日报，MacBook 写概念/笔记
- **单一重试源** — 所有重试读 `jobs.json`，不维护独立状态
- **内容优先投递** — 先生成到 vault，再投递；投递失败不影响内容
- **诊断 exit 0** — 健康脚本始终 exit 0，结果写在输出里
