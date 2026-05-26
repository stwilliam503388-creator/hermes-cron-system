# 每日AI Agent面试问答日报

- **ID**: 203327bd97ca
- **Model**: deepseek-v4-flash
- **Schedule**: 0 12 * * *
- **Type**: Agent

---

## 步骤 0：网络连通性检查
请先检查能否联网——如果连续 3 次 API/web_search 调用都失败，说明当前可能断网。
此时不要继续消耗 tokens 尝试重试，而是：
1. 输出一条断网通知
2. 标记任务失败
3. 不要尝试写入 Obsidian

## 你的任务
每日 AI Agent 岗位面试问答日报。每天从网络上搜索 AI Agent 相关面试题，整理成高频问答。

## 数据来源
- 搜索最新 AI Agent 面试题（牛客网、力扣、知乎等）
- 结合当前 AI Agent 技术趋势
- 每天选 2-3 个核心问题

## 输出格式
- 问题
- 面试官期望的答案要点（3-5 点）
- 拓展阅读/相关技术点
- 难度评级：⭐-⭐⭐⭐

## Obsidian 写入要求
- 写入 /Users/<user>/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/资讯/AI面试日报/
- 文件名：YYYY-MM-DD-AI面试日报.md
- 写入完成后再输出最终内容

## 写入投递队列
最后，将本任务摘要写入投递队列（供微信批量汇总）：
  mkdir -p /Users/<user>/.hermes/delivery-queue/pending
  ts=$(date +%Y%m%d-%H%M)
  创建文件 /Users/<user>/.hermes/delivery-queue/pending/$ts-ai-interview.txt
  内容：任务名【AI面试日报】+ 3行核心摘要（今日问答主题+问题数） + Obsidian文件路径