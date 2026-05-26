# 晚间AI情报快讯（合并）

- **ID**: merged-evening-briefing
- **Model**: deepseek-v4-pro
- **Schedule**: 30 20 * * *
- **Type**: Agent

---

## 你的任务：晚间 AI 情报快讯
每日 20:00 执行，更新下午新出现的 AI 相关内容。

### 板块 1：GitHub Trending 下午更新
对比晨间简报，抓取 https://github.com/trending 中下午新上榜的 AI 项目（Top 5）

### 板块 2：知乎B站晚间热门
- 知乎热榜下午新增科技/AI 内容（Top 5）
- B站晚间热门科技视频（Top 3）

### 板块 3：今日值得关注
从全天信息中提炼 1-2 条最值得深入阅读的内容

## 输出格式
- 总字数 800-1200 字
- 板块用 --- 分隔
- 全中文

## Obsidian 写入
路径：资讯/AI日报/YYYY-MM-DD-晚间情报快讯.md

## 投递队列
```bash
mkdir -p /Users/<user>/.hermes/delivery-queue/pending
cat > /Users/<user>/.hermes/delivery-queue/pending/$(date +%Y%m%d-%H%M)-evening-briefing.txt << 'DELIVERY_EOF'
晚间AI情报快讯摘要
DELIVERY_EOF
```