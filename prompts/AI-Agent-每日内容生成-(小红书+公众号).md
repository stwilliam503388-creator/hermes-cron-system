# AI Agent 每日内容生成 (小红书+公众号)

- **ID**: 81c3d765872a
- **Model**: deepseek-v4-flash
- **Schedule**: 40 6 * * *
- **Type**: Agent

---

## 步骤 0：网络连通性检查
请先检查能否联网——如果连续 3 次 API/web_search 调用都失败，说明当前可能断网。
此时不要继续消耗 tokens 尝试重试，而是：
1. 输出一条断网通知
2. 标记任务失败
3. 不要尝试写入 Obsidian

## 你的任务
每日 AI Agent PM 内容生成。生成一篇关于 AI Agent 产品经理技能/知识/趋势的文章。

## 生成要求
- 聚焦 AI Agent PM 核心能力：Agent 产品设计、工作流编排、评估体系、Prompt 工程、多模态
- 每天一个主题，深度 800-1200 字
- 包含具体案例或代码/工作流示例
- 附一个思考题

## Obsidian 写入要求
- 写入 /Users/<user>/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault/资讯/AI Agent日报/
- 文件名：YYYY-MM-DD-AI Agent PM 技能.md
- 写入完成后再输出最终内容

## 写入投递队列
最后，将本任务摘要写入投递队列（供微信批量汇总）：
  mkdir -p /Users/<user>/.hermes/delivery-queue/pending
  ts=$(date +%Y%m%d-%H%M)
  创建文件 /Users/<user>/.hermes/delivery-queue/pending/$ts-ai-agent-content.txt
  内容：任务名【AI Agent PM 技能】+ 3行核心摘要（今日主题+核心观点+思考题） + Obsidian文件路径