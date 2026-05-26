# Hermes Cron System

基于 [Hermes Agent](https://github.com/nousresearch/hermes-agent) 的自动化定时任务系统。

| 指标 | 数值 |
|------|------|
| 任务总数 | 35（24 Mini + 11 MacBook） |
| 脚本数 | 77（50 .py + 27 .sh） |
| Agent 提示词 | 13 |
| 投递通道 | 飞书 + 微信 + delivery-queue |
| 存储后端 | iCloud Drive (Obsidian Vault) |
| 模型 | deepseek-v4-pro + deepseek-v4-flash |

## 目录结构

```
├── README.md
├── system-design.md              # 系统设计文档（31KB, 9章）
├── mac-mini-deployment.md        # Mac Mini 双机部署方案（17KB, 14风险对策）
├── config/
│   ├── config.yaml               # Hermes 配置（已脱敏）
│   ├── SOUL.md                   # Agent personality
│   └── cron-jobs-sanitized.json  # 40 任务定义（已脱敏）
├── scripts/                      # 77 个自动化脚本
│   ├── *.py                      # Python 脚本（vault维护/投递/监控/NotebookLM）
│   └── *.sh                      # Shell 脚本（备份/同步/管线）
└── prompts/                      # 13 个 Agent 任务提示词
    ├── 晨间AI情报简报合并.md
    ├── 晚间AI情报快讯合并.md
    ├── 每日AI-Agent面试问答日报.md
    ├── AI-Agent-每日内容生成.md
    ├── 豆瓣-Top250-每日一书解读.md
    ├── 每日名言+解读.md
    ├── 每日阅读清单.md
    ├── 周报自动生成.md
    ├── 播客转文字摘要.md
    ├── 内容工厂-早间.md
    ├── 内容工厂-午间.md
    ├── 闲鱼选品+文案生成.md
    └── Obsidian-orphan-checker.md
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

## 关键脚本

### 基础设施
- `setenv.sh` — 统一环境变量（被所有脚本 source）
- `notify.sh` — 统一通知推送

### Vault 维护
- `vault_autolink.py` — 自动补链孤岛笔记
- `vault_health.py` — 健康巡检
- `vault_master_index_update.py` — 知识库总索引更新
- `orphan_checker.py` — 新孤岛检测 + 自动补链

### 投递
- `wechat-batch-deliver.sh` — 队列批量微信投递（早中晚 ×3）

### 监控恢复
- `daily-midnight-check.py` — 凌晨统一自检（NotebookLM + 重试 + 索引检测）
- `network-recovery-check.py` — 每 2h 网络+代理检测 + 失败重试
- `daily-error-report.py` — 每日 23:00 全量错误报告
- `end-to-end-health.py` — 周一全链路 5 环节健康测试

### NotebookLM
- `notebooklm-sync.py` — Playwright 浏览器自动上传 (v3)
- `notebooklm-session-keepalive.py` — 每日 cookie 续期
- `wrapper-notebooklm-upload.sh` — 7 分类上传调度器
- `export-obsidian-to-notebooklm.sh` — 清洁笔记导出

## 快速开始

详见 [移植指南](system-design.md#8-移植指南) 和 [Mac Mini 部署方案](mac-mini-deployment.md)。

```
# 1. 安装 Hermes
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sh

# 2. 同步配置
rsync -avz scripts/ target:.hermes/scripts/
rsync -avz config/ target:.hermes/profiles/minimal/
# 修正路径 sed s/<olduser>/<newuser>/g

# 3. 启动
hermes --profile minimal gateway start
hermes --profile minimal cron list
```

## 设计原则

- **iCloud 单源** — Obsidian vault 共享，两台机器读写同路径
- **职责硬分割** — Mini 写资讯/日报，MacBook 写概念/笔记
- **单一重试源** — 所有重试读 `jobs.json`，不维护独立状态
- **内容优先投递** — 先生成到 vault，再投递；投递失败不影响内容
- **诊断 exit 0** — 健康脚本始终 exit 0，结果写在输出里
