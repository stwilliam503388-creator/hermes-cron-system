# Hermes 调度器 Mac Mini 部署方案（v3 修正版）

> 状态: `plan` | 优先级: 中（等待 SSH 连 Mac Mini 后执行）| 更新: 2026-05-26
> 标签: 遗留问题
> v2→v3: 任务数 31→35，补充 7 个新风险，修正任务分配，增加前置检查清单

---

## 一、架构总览

```
┌─────────────────────────┐         ┌─────────────────────────┐
│      MacBook (便携)      │         │     Mac Mini (24h常驻)    │
│                         │         │                         │
│  ┌───────────────────┐  │         │  ┌───────────────────┐  │
│  │  Hermes TUI / CLI │  │  SSH    │  │  Hermes 调度器     │  │
│  │  (交互使用)        │◄─┼─────────┼─►│  30 个 cron 任务   │  │
│  │  hermes send      │  │ 隧道    │  │  gateway(微信网关)  │  │
│  └───────────────────┘  │         │  └────────┬──────────┘  │
│                         │         │           │             │
│  ┌───────────────────┐  │         │  ┌────────┴──────────┐  │
│  │  Obsidian (阅读)   │  │         │  │  心跳文件每小时    │  │
│  │  系统告警监测      │  │         │  │  .heartbeat 写    │  │
│  │  检查 Mini 心跳   │  │         │  │ 到 iCloud 路径    │  │
│  │  本地备份/管线/检测│  │         │  └───────────────────┘  │
│  └─────────┬─────────┘  │         │                         │
│            │            │         │           │             │
│            │ iCloud     │         │           ▼             │
│            ▼            │         │  ┌──────────────────┐  │
│  ┌───────────────────┐  │         │  │  ClashX / 代理    │  │
│  │  Obsidian Vault   │◄─┼──Sync──┼─┤  127.0.0.1:7890   │  │
│  │  (iCloud 副本)    │  │         │  │  (LLM API 出口)   │  │
│  │  资讯/ 日报/ 学习计划/ │         │  └──────────────────┘  │
│  │  ← Mini 写入区      │         │                         │
│  │  概念/ 工具笔记/    │         │                         │
│  │  ← MacBook 编辑区   │         │                         │
│  └───────────────────┘  │         │                         │
└─────────────────────────┘         └─────────────────────────┘

同步层：iCloud Drive（日常）+ Git push/pull（备份/兜底）
组网：Tailscale（SSH 像局域网一样用）
```

---

## 二、同步方案

### iCloud Drive（主方案）

两个设备登录同 Apple ID，仓库路径一致：

```
/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/
```

**职责硬分割，从源头消除冲突：**

| 写入端 | 写入目录 | 文件类型 |
|--------|---------|---------|
| Mac Mini（cron 自动生成） | `资讯/` `日报/` `对话归档/` | 情报简报、每日一书、名言解读、阅读清单、面试问答、概念卡片 |
| MacBook（手动编辑） | `概念/` `工具笔记/` `工作流/` `参考/` | 个人笔记、工具配置、学习笔记 |

两条路径完全不重叠。如果需要跨区写入，通过 Obsidian 双向链接而非物理修改文件。

### Git（备份/兜底）

两设备各自执行 git sync：
- MacBook: 06:20 + 23:00（已有 cron）
- Mac Mini: 09:00 + 21:00（新增 cron，错开时间避免同时 push 冲突）

---

## 三、风险与对策（14 项）

### 原有风险（v2，7 项）— 全部保留 ✅

### 风险 1：iCloud 双端写入冲突

**对策**：职责硬分割（上表）+ 写前 mtime 检查（5 分钟窗口）

### 风险 2：微信网关只能跑一台设备

**对策**：Mini 持微信长连接 + MacBook SSH 隧道 `tunnel-mini` alias

### 风险 3：Mac Mini 离线无预警

**对策**：iCloud 心跳文件 `.heartbeat`，MacBook `system-alert.sh` 检查 >2h 报警

### 风险 4：配置漂移

**对策**：`sync-to-mini` alias（rsync 脚本 + config + .env）

### 风险 5：任务拆分决策

**对策**：见第四节任务分配表（v3 修正版）

### 风险 6：API Key 安全

**对策**：`chmod 600 .env` + FileVault

### 风险 7：远程部署验证

**对策**：Tailscale 组网 + 6 步部署流程

---

### 新增风险（v3，7 项）

### 风险 8：Mac Mini 没有代理（P0）— 新增 ⚠️

**问题**：10 个 LLM agent 任务（晨间/晚间简报、名言、日报、面试问答、每日一书、阅读清单、内容生成、周报、播客摘要、概念萃取）全部通过 `HTTPS_PROXY=127.0.0.1:7890` 访问 deepseek API。Mini 不装 ClashX 或等效代理 → 全部 agent 任务 Connection error。

**对策**：

① Mac Mini 安装 ClashX 或等效代理客户端，配置与 MacBook 一致的订阅
② 代理端口统一为 `127.0.0.1:7890`
③ 部署后验证：`curl --proxy http://127.0.0.1:7890 https://api.deepseek.com/v1/models -w "%{http_code}"` 应返回 401（通但不带 key）
④ 如不想装 ClashX，可改用 Cloudflare WARP（免费）或直接配路由器级别代理

### 风险 9：Mac Mini 没有 Chrome（P0）— 新增 ⚠️

**问题**：NotebookLM 上传（02:00）和 session 续期（03:00）使用 Playwright `channel="chrome"` 启动浏览器。Mac Mini 默认没有 Chrome → `playwright._impl._errors.Error: Chromium distribution 'chrome' is not found`

**对策**：

① 方案 A（推荐）：NotebookLM 相关 2 个任务留在 MacBook（已列入第四节保留表）
② 方案 B：Mac Mini 装 Chrome：`brew install --cask google-chrome`，然后 `playwright install chromium`
③ 方案 B 需额外验证 headless 模式在无显示器 Mini 上是否正常（已知 macOS headless Chrome 有时黑屏）

**当前决定**：走方案 A，NotebookLM 留在 MacBook。

### 风险 10：iCloud 心跳延迟误报（P1）— 新增 ⚠️

**问题**：`.heartbeat` 写进 iCloud vault，依赖同步到 MacBook。iCloud 偶有几分钟到几十分钟延迟 → MacBook `system-alert.sh` 误判 Mini 离线 → 频繁报警。

**对策**：

① 心跳阈值从 2h 放宽到 4h（允许 iCloud 同步延迟 + Mini 短暂离线）
② 心跳文件增加序号计数器，MacBook 检查连续缺失 3 次才报警
③ 备用检测：MacBook `network-recovery-check.py` 定期 ping Mini Tailscale IP（直连，不依赖 iCloud）

```bash
# system-alert.sh 心跳检查（修正版）
HEARTBEAT="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/.heartbeat"
if [ -f "$HEARTBEAT" ]; then
    age=$(($(date +%s) - $(stat -f %m "$HEARTBEAT" 2>/dev/null || echo 0)))
    if [ "$age" -gt 14400 ]; then  # 4h，不是 2h
        echo "⚠️ Mac Mini 心跳停止 ($((age/3600))h 前)"
    fi
fi

# 备用检测：ping Tailscale IP
MINI_IP="100.x.x.x"  # 替换为实际 Tailscale IP
if ! ping -c 1 -W 3 "$MINI_IP" > /dev/null 2>&1; then
    echo "⚠️ Mac Mini 不可达（ping 失败）"
fi
```

### 风险 11：两台设备同时 git push 冲突（P1）— 新增 ⚠️

**问题**：两设备对同一 vault 各自 `add → commit → push`。即使有 pull-rebase，同时 push 仍可能 rejected。目前 MacBook 早晚各一次，如果 Mini 也早晚各一次 → 4 次 push/天，冲突概率翻倍。

**对策**：

① **时间错开**：Mini 在 09:00 + 21:00 push，MacBook 在 06:20 + 23:00 push（已有）。至少间隔 2 小时
② pull-rebase 兜底（已在 obsidian-git-sync.sh 中实现）
③ 如果仍然 rejected，第二次 push 会因 pull-rebase 自动解决
④ 降级方案：MacBook 只 pull 不 push，Mini 作为唯一 push 端

### 风险 12：Python 依赖缺失（P1）— 新增 ⚠️

**问题**：`hermes` 安装只装核心依赖。以下脚本需要额外 pip 包：

| 脚本 | 需要的包 | 原因 |
|------|---------|------|
| video-queue-processor.py | `faster-whisper`, `yt-dlp` | 视频下载 + 转写 |
| zhihu-fetch.py | `browser-cookie3` | 提取 Chrome cookie |
| notebooklm-sync.py | `playwright` | 浏览器自动化上传 |
| orphan_checker.py | 无额外依赖 | 纯标准库 ✅ |
| vault_* 系列 | 无额外依赖 | 纯标准库 ✅ |

**对策**：

部署时额外执行：

```bash
# 视频转写依赖
pip install faster-whisper yt-dlp opencc-python-reimplemented

# Playwright（如果要在 Mini 跑 NotebookLM）
pip install playwright && playwright install chromium

# 知乎 cookie 提取
pip install browser-cookie3
```

### 风险 13：delivery-queue 路径隔离（P1）— 新增 ⚠️

**问题**：部分任务通过 `delivery-queue/pending/` 中转投递。路径是本地 `~/.hermes/delivery-queue/`，不走 iCloud。如果 Mini 的任务写队列，MacBook 的 `wechat-batch-deliver.sh` 看不到 → 投递永远空。

**涉及任务**：
- `wrapper-obsidian-pipeline.sh` → 写 `pending/xxx-obsidian-pipeline.txt`
- `run_vault_maintenance.sh` → 写 `pending/xxx-knowledge-maint.txt`
- `vault-backup.sh` → 写 `pending/xxx-vault-backup.txt`
- `wechat-batch-deliver.sh`（早中晚 ×3）→ 读 `pending/` → 发送 → 移到 `sent/`

**对策**：

① **简单方案**：队列路径也放到 iCloud vault 下共享，或将写入端的队列改为直接 `hermes send`
② **当前决定**：这些写队列的任务全部留在 MacBook（已在第四节保留表中），Mini 不写 delivery-queue
③ 所有 agent 任务（晨间简报等）直接通过 cron `deliver` 参数投递，不经过队列

### 风险 14：用户约束冲突（P2）— 新增 ⚠️

**问题**：之前的约束「系统告警、备份、管线任务、检测任务不应推送，仅本地执行」。v2 方案写「31 个全放 Mini」直接违反这一约束。

**对策**：

① **严格遵守**：以下 5 类任务留在 MacBook，不推送

| 类别 | 任务 |
|------|------|
| 系统告警 | system-alert（每小时） |
| Vault 备份 | vault-backup（00:40） |
| Hermes 备份 | config-backup（每 6h）|
| Obsidian 管线 | wrapper-obsidian-pipeline（01:50）|
| 检测任务 | orphan-checker（07:35）、end-to-end-health（周一 08:00）|

② NotebookLM 相关（需 Chrome）也留 MacBook
③ 其余 30 个任务搬到 Mini

---

## 四、任务分配表（v3 修正版）

### 搬 Mac Mini（30 个）

| 类别 | 任务 | 原因 |
|------|------|------|
| LLM 内容 | 晨间/晚间AI简报、每日名言、面试日报、每日一书、阅读清单、内容生成、周报、播客摘要 | 纯 LLM API 调用，Mini 跑更稳定 |
| 概念知识库 | 概念自动萃取、夜间维护、关联重建、健康巡检、知识库自动维护 | CPU 密集型，Mini 分担负载 |
| 微信投递 | wechat-batch-deliver ×3（早中晚）| Mini 持微信网关长连接 |
| Git 同步 | obsidian-git-sync ×2（09:00, 21:00）| 错开 MacBook 的 06:20/23:00 |
| 自检/恢复 | daily-midnight-check、network-recovery-check、断网检测 | Mini 常驻在线更适合 |
| 学习相关 | AI Agent PM 学习计划推送、视频队列转写 | 非交互式任务 |
| 报告 | daily-error-report（23:00）| 汇总全局状态 |
| NotebookLM | ~~已决定留 MacBook~~ | 见风险 9 |

### 留 MacBook（5 个）

| 任务 | 原因 |
|------|------|
| system-alert（每小时）| 用户约束：系统告警不推送 |
| vault-backup（00:40）| 用户约束：本地备份 |
| config-backup（每 6h）| 用户约束：配置备份本地 |
| wrapper-obsidian-pipeline（01:50）| 用户约束：管线任务 |
| orphan-checker（07:35）| 用户约束：检测任务 |
| **NotebookLM 相关（2 个）** | **需要 Playwright + Chrome** |
| notebooklm-upload（02:00）| 需 Playwright `channel="chrome"` |
| notebooklm-session-keepalive（03:00）| 需 Playwright `channel="chrome"` |
| 浏览器标签页归档（23:00）| 需本地浏览器数据 |
| end-to-end-health（周一 08:00）| 全链路检测，本地跑更准 |
| Hermes 周备份（周日 03:00）| 用户约束：备份本地 |

### 两边都跑（1 个）

| 任务 | Mini | MacBook | 原因 |
|------|------|---------|------|
| obsidian-git-sync | 09:00 + 21:00 | 06:20 + 23:00 | 双向备份兜底，时间错开避免 push 冲突 |

---

## 五、部署前置检查清单（新增）

**部署前，确保 Mac Mini 满足以下条件：**

- [ ] macOS 已登录同一 Apple ID（iCloud Drive 已开，Obsidian vault 已同步到本地）
- [ ] **ClashX 或等效代理已安装并运行**，端口 `127.0.0.1:7890`（风险 8）
- [ ] 代理已验证：`curl --proxy http://127.0.0.1:7890 https://api.deepseek.com/v1/models -w "%{http_code}"` → `401`
- [ ] Tailscale 已安装，与 MacBook 组网
- [ ] Mac Mini Tailscale IP 已知（如 `100.x.x.x`）
- [ ] Homebrew 已安装（`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`）
- [ ] 磁盘空间 >20GB（备份 + venv + 日志会占用）
- [ ] 电源设置：「防止自动休眠」已开启（系统设置 → 电池 → 电源适配器 → 防止自动休眠）

---

## 六、部署步骤（v3 修正）

### Step 0：前置验证

```bash
ssh liuwei@100.x.x.x

# 验证代理
curl --proxy http://127.0.0.1:7890 https://api.deepseek.com/v1/models -w "\nHTTP %{http_code}\n" -o /dev/null

# 验证 iCloud vault
ls "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/" | head -5

# 验证磁盘空间
df -h /
```

### Step 1：Mac Mini 安装 Hermes

```bash
ssh liuwei@100.x.x.x
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sh

# 安装 Python 额外依赖
pip install faster-whisper yt-dlp opencc-python-reimplemented browser-cookie3
```

### Step 2：同步配置和脚本

```bash
# MacBook 上执行
MACMINI="liuwei@100.x.x.x"

# 同步 profile（含 jobs.json + config.yaml）
rsync -avz --delete \
  ~/.hermes/profiles/minimal/ \
  $MACMINI:.hermes/profiles/minimal/

# 同步脚本
rsync -avz --delete \
  ~/.hermes/scripts/ \
  $MACMINI:.hermes/scripts/

# 同步 .env（API keys）
rsync -avz \
  ~/.hermes/profiles/minimal/.env \
  $MACMINI:.hermes/profiles/minimal/.env
```

### Step 3：Mini 端清理不应运行的任务

```bash
ssh liuwei@100.x.x.x

# 禁用 MacBook 保留的任务（它们在 Mini 上不应运行）
hermes cron pause system-alert-job-id        # 替换为实际 ID
hermes cron pause vault-backup-job-id
hermes cron pause config-backup-job-id
hermes cron pause obsidian-pipeline-job-id
hermes cron pause orphan-checker-job-id
hermes cron pause notebooklm-upload-job-id
hermes cron pause notebooklm-keepalive-job-id
hermes cron pause browser-tabs-job-id
hermes cron pause end-to-end-health-job-id
hermes cron pause hermes-backup-job-id
```

（实际部署时我会提供精确的 job_id 列表）

### Step 4：配置安全

```bash
ssh liuwei@100.x.x.x
chmod 600 ~/.hermes/profiles/minimal/.env
```

### Step 5：添加心跳 cron

```bash
ssh liuwei@100.x.x.x

# 创建心跳脚本
cat > ~/.hermes/scripts/heartbeat-to-icloud.sh << 'EOF'
#!/bin/bash
HEARTBEAT="/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/.heartbeat"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) #$(( $(cat "$HEARTBEAT" 2>/dev/null | grep -o '#[0-9]*' | grep -o '[0-9]*' || echo 0) + 1 ))" > "$HEARTBEAT"
EOF
chmod +x ~/.hermes/scripts/heartbeat-to-icloud.sh

# 每小时心跳
hermes cron create --name "Mac Mini 心跳" --schedule "0 * * * *" \
  --script "heartbeat-to-icloud.sh" --no-agent --deliver local
```

### Step 6：启动调度器+网关

```bash
ssh liuwei@100.x.x.x
hermes --profile minimal gateway start
```

### Step 7：验证

```bash
ssh liuwei@100.x.x.x

# 触发测试任务
hermes cron run obsidian-git-sync-morning
sleep 5

# 检查调度器状态
hermes cron status

# 检查文件写入
ls -lt "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/资讯/" | head -3
```

回到 MacBook 打开 Obsidian 确认文件已同步。

### Step 8：MacBook 配置 SSH 隧道 + 别名

```bash
# ~/.zshrc 追加
alias tunnel-mini='ssh -fNL 9090:localhost:9090 -NL 9091:localhost:9091 mac-mini'
alias sync-to-mini='rsync -avz --delete \
  ~/.hermes/scripts/ mac-mini:.hermes/scripts/ && \
  rsync -avz ~/.hermes/profiles/minimal/config.yaml \
    mac-mini:.hermes/profiles/minimal/config.yaml && \
  rsync -avz ~/.hermes/profiles/minimal/.env \
    mac-mini:.hermes/profiles/minimal/.env && \
  echo "✅ synced"'

# SSH config (~/.ssh/config)
Host mac-mini
    HostName 100.x.x.x
    User liuwei
    ServerAliveInterval 60
```

---

## 七、变更摘要

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-05-23 | 初版，7 大风险 + 6 步部署 |
| v2 | 2026-05-24 | iCloud 职责硬分割、心跳文件法、SSH 隧道、配置漂移对策 |
| v3 | 2026-05-26 | 任务数 31→35、新增 7 个风险（代理/Chrome/心跳延迟/Git 冲突/Python 依赖/队列隔离/用户约束）、修正任务分配表、增加前置检查清单、心跳脚本增加序号计数器 |
