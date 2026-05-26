# 晨间AI情报简报（合并）

- **ID**: merged-morning-briefing
- **Model**: deepseek-v4-pro
- **Schedule**: 0 7 * * *
- **Type**: Agent

---

## 步骤 0：网络连通性检查（由 pre-check 脚本完成，如已注入则跳过）

## 你的任务：晨间 AI 情报简报
每日 07:00 执行，聚合以下 4 个来源 + 输出到 Obsidian 和投递队列。

### 板块 1：GitHub Trending（AI/ML/LLM/Agent 相关）
抓取 https://github.com/trending，筛选 AI 相关 Top 5：
- 仓库名 + 今日涨星 + 简介（100字内）
- 技术栈标签 + 入选理由

### 板块 2：Hacker News + V2EX AI 精选
- HN Top 5 AI 话题（标题+分数+一行评注）
- V2EX 精选 3 条（标题+热度+评注）

### 板块 3：AI 行业简报
- 🔥 头条：今日最重要 AI 事件（1条）
- 📄 论文速递（2篇，从 ArXiv new/AI 抓取）
- 🏢 产业动态（2条）

### 板块 4：知乎B站内容速览
- 知乎热榜中科技/AI 相关 Top 5（标题+链接+一行摘要）
- B站科技区热门 Top 3（标题+链接+一行摘要）

## 输出格式
- 总字数 1200-1800 字
- 板块之间用 --- 分隔
- 全中文输出，末尾标注数据来源和时间

## Obsidian 写入
写入路径：资讯/AI日报/YYYY-MM-DD-晨间情报简报.md

## 投递队列
最后写入投递队列供微信批量汇总：
```bash
mkdir -p /Users/<user>/.hermes/delivery-queue/pending
cat > /Users/<user>/.hermes/delivery-queue/pending/$(date +%Y%m%d-%H%M)-morning-briefing.txt << 'DELIVERY_EOF'
晨间AI情报简报摘要（300字内）
DELIVERY_EOF
```