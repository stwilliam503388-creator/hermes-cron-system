#!/usr/bin/env python3
"""
AI Agent PM 学习计划每日推送 — DeepSeek 在线版 (增强版 v2)
每天早上 07:00 生成当日详细学习内容，推送到两个邮箱
功能增强：
1. 明确标注当天内容在整体计划中的位置（Phase/Week/Day/进度）
2. 关联 GitHub 项目链接（当日相关项目 + 链接）
3. 补充面试经验内容（相关面试题 + 面经要点）
"""

import smtplib
import ssl
import json
import re
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from urllib.request import Request, urlopen
from urllib.error import URLError
from typing import Optional

# ========================= 配置 =========================

SMTP_CONFIG = {
    "host": "smtp.qq.com",
    "port": 465,
    "user": "453169854@qq.com",
    "password": "tokhhpbgyavkcbdi",
}

TO_EMAILS = [
    "liuwei634@huawei.com",
    "stwilliam503388@gmail.com",
]

DEEPSEEK_API_KEY = "sk-1fce5227c29a49749f8cc7c5637fcbed"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"  # 使用 DeepSeek V3

# ========================= 核心 GitHub 项目索引 =========================
# 按主题分类的 GitHub 项目链接，用于注入到每日学习内容中

CORE_PROJECTS = {
    "hello-agents": {
        "name": "datawhalechina/hello-agents",
        "url": "https://github.com/datawhalechina/hello-agents",
        "stars": "5.7k",
        "desc": "硬核 Agent 技术教程，从零手搓 Agent 框架",
    },
    "interview-guide": {
        "name": "bcefghj/ai-agent-interview-guide",
        "url": "https://github.com/bcefghj/ai-agent-interview-guide",
        "stars": "919",
        "desc": "AI Agent 面试全攻略：200+ 面试题 + 企业级项目 + 漫画图解",
    },
    "2bpm": {
        "name": "StevenJokess/2bPM",
        "url": "https://github.com/StevenJokess/2bPM",
        "stars": "161",
        "desc": "AI PM 知识图谱 + 能力模型 + 在线书",
    },
    "aipm-skills": {
        "name": "chusimin/AIPM-Skills",
        "url": "https://github.com/chusimin/AIPM-Skills",
        "stars": "41",
        "desc": "Claude Skills 工具链：BRD/MRD/PRD/简历/面试诊断",
    },
    "genai-agents": {
        "name": "NirDiamant/GenAI_Agents",
        "url": "https://github.com/NirDiamant/GenAI_Agents",
        "stars": "19k+",
        "desc": "40+ Agent 实战场景（LangGraph 实用示例）",
    },
    "scodive-guide": {
        "name": "Scodive/AI-Agent-Guide",
        "url": "https://github.com/Scodive/AI-Agent-Guide",
        "stars": "1k+",
        "desc": "Agent 架构全景 + 关键技术论文索引",
    },
    "500-agents": {
        "name": "ashishpatel26/500-AI-Agents-Projects",
        "url": "https://github.com/ashishpatel26/500-AI-Agents-Projects",
        "stars": "18k+",
        "desc": "500+ Agent 落地案例库（分场景分类）",
    },
    "awesome-2026": {
        "name": "caramaschiHG/awesome-ai-agents-2026",
        "url": "https://github.com/caramaschiHG/awesome-ai-agents-2026",
        "stars": "863",
        "desc": "340+ Agent 资源、20 分类、月更新生态地图",
    },
    "agentguide-adong": {
        "name": "adongwanai/AgentGuide",
        "url": "https://github.com/adongwanai/AgentGuide",
        "stars": "4.9k",
        "desc": "Agent 面试指南 + 大厂真实现经 + 开放讨论题库",
    },
    "ai-eng-interview": {
        "name": "amitshekhariitbhu/ai-engineering-interview-questions",
        "url": "https://github.com/amitshekhariitbhu/ai-engineering-interview-questions",
        "stars": "10k+",
        "desc": "AI Engineering 面试题集：LLM/RAG/Agent/System Design",
    },
    "langgraph": {
        "name": "langchain-ai/langgraph",
        "url": "https://github.com/langchain-ai/langgraph",
        "stars": "13k+",
        "desc": "LangChain Graph 框架，构建状态化多 Actor Agent",
    },
    "crewai": {
        "name": "crewAIInc/crewAI",
        "url": "https://github.com/crewAIInc/crewAI",
        "stars": "30k+",
        "desc": "Multi-Agent 协作框架（角色分工 + 任务委派）",
    },
    "autogen": {
        "name": "microsoft/autogen",
        "url": "https://github.com/microsoft/autogen",
        "stars": "40k+",
        "desc": "微软多 Agent 对话框架（支持嵌套会话）",
    },
    "openai-agents-sdk": {
        "name": "openai/openai-agents-python",
        "url": "https://github.com/openai/openai-agents-python",
        "stars": "18k+",
        "desc": "OpenAI Agents SDK 官方框架",
    },
    "dify": {
        "name": "langgenius/dify",
        "url": "https://github.com/langgenius/dify",
        "stars": "80k+",
        "desc": "开源 LLM 应用开发平台（可视化 Agent 搭建）",
    },
    "crackpm": {
        "name": "crackpminterview.com (外部站点)",
        "url": "https://crackpminterview.com",
        "stars": "-",
        "desc": "英文 AI PM 面试 6 类核心题型",
    },
    "lockedinai": {
        "name": "lockedinai.com (外部站点)",
        "url": "https://lockedinai.com",
        "stars": "-",
        "desc": "56 道 AI PM 面试题 + 样答",
    },
}

# ========================= 按天关联 GitHub 项目 =========================
# key = day_number, value = list of project keys

DAY_GITHUB_LINKS = {
    # === Week 1: AI & Agent 基础 ===
    1: ["hello-agents", "scodive-guide", "2bpm"],
    2: ["hello-agents", "ai-eng-interview"],
    3: ["interview-guide", "genai-agents"],
    4: ["hello-agents", "interview-guide", "2bpm"],
    5: ["interview-guide", "openai-agents-sdk"],
    6: ["scodive-guide", "interview-guide", "genai-agents"],
    7: ["hello-agents", "2bpm", "500-agents"],

    # === Week 2: Agent 产品架构 ===
    8: ["langgraph", "crewai", "autogen", "openai-agents-sdk", "dify"],
    9: ["hello-agents", "genai-agents"],
    10: ["500-agents", "genai-agents"],
    11: ["genai-agents", "awesome-2026", "ai-eng-interview"],
    12: ["interview-guide", "scodive-guide"],
    13: ["langgraph", "crewai", "autogen", "openai-agents-sdk"],
    14: ["hello-agents", "scodive-guide", "2bpm"],

    # === Week 3: AI Agent 产品方法论 ===
    15: ["2bpm", "aipm-skills"],
    16: ["2bpm"],
    17: ["aipm-skills", "2bpm"],
    18: ["aipm-skills", "2bpm"],
    19: ["500-agents", "genai-agents"],
    20: ["interview-guide", "scodive-guide"],
    21: ["aipm-skills", "2bpm"],

    # === Week 4: Agent 产品需求与设计 ===
    22: ["aipm-skills", "2bpm"],
    23: ["genai-agents", "langgraph"],
    24: ["ai-eng-interview", "awesome-2026"],
    25: ["interview-guide"],
    26: ["interview-guide", "2bpm"],
    27: ["scodive-guide", "500-agents"],
    28: ["aipm-skills", "500-agents"],

    # === Week 5: Agent 产品开发与迭代 ===
    29: ["dify", "langgraph"],
    30: ["interview-guide", "genai-agents"],
    31: ["aipm-skills", "2bpm"],
    32: ["dify", "openai-agents-sdk", "crewai"],
    33: ["ai-eng-interview", "awesome-2026"],
    34: ["500-agents", "genai-agents"],
    35: ["aipm-skills", "2bpm", "500-agents"],

    # === Week 6: 行业实战 ===
    36: ["interview-guide", "agentguide-adong"],
    37: ["interview-guide", "agentguide-adong"],
    38: ["interview-guide", "genai-agents"],
    39: ["interview-guide", "openai-agents-sdk"],
    40: ["interview-guide", "crewai", "autogen"],
    41: ["ai-eng-interview", "scodive-guide"],
    42: ["interview-guide", "agentguide-adong"],

    # === Week 7: 商业化 ===
    43: ["crackpm", "ai-eng-interview"],
    44: ["crackpm", "lockedinai"],
    45: ["crackpm", "ai-eng-interview"],
    46: ["crackpm", "lockedinai"],
    47: ["lockedinai", "crackpm"],
    48: ["interview-guide", "agentguide-adong"],
    49: ["crackpm", "ai-eng-interview"],

    # === Week 8: 面试准备 ===
    50: ["interview-guide", "aipm-skills"],
    51: ["interview-guide", "aipm-skills", "agentguide-adong"],
    52: ["interview-guide", "aipm-skills"],
    53: ["crackpm", "lockedinai"],
    54: ["interview-guide", "aipm-skills", "agentguide-adong"],
    55: ["interview-guide", "agentguide-adong"],
    56: ["interview-guide", "2bpm", "ai-eng-interview"],
}

# ========================= 面试经验内容（按周/主题组织）=================

INTERVIEW_QUESTIONS = {
    "week1": [
        {
            "q": "请用非技术语言解释什么是 AI Agent？和简单的大模型对话有什么区别？",
            "answer_hint": "Agent = LLM + 规划能力 + 工具调用 + 记忆系统。Chat 只有对话，Agent 能自主执行任务。",
            "source": "ai-agent-interview-guide / 高频题",
        },
        {
            "q": "解释 ReAct 循环的工作流程？Agent 在什么情况下会陷入死循环？如何解决？",
            "answer_hint": "Reason → Act → Observe 循环。死循环可用 max_steps 上限 + 多样性惩罚。",
            "source": "adongwanai/AgentGuide 面经 / 字节算法岗",
        },
        {
            "q": "什么是 RAG？作为 PM，你怎么向业务方解释 RAG 的价值和局限性？",
            "answer_hint": "价值：解决知识时效性和幻觉问题。局限：检索质量依赖 chunk 策略、延迟增加。",
            "source": "juejin AI PM 面试必问 30 题",
        },
        {
            "q": "Agent 产品如何设计评估体系？列出至少 5 个关键指标。",
            "answer_hint": "准确率、任务完成率、幻觉率、用户修正率、平均处理时间、Token 成本。",
            "source": "lockedinai.com / igotanoffer.com",
        },
    ],
    "week2": [
        {
            "q": "如何选择 Agent 框架（LangGraph vs CrewAI vs AutoGen）？作为 PM 你的选型考量是什么？",
            "answer_hint": "看场景复杂度、团队技术栈、社区活跃度、扩展性。LangGraph 适合复杂工作流，CrewAI 适合分工清晰的多 Agent。",
            "source": "crackpminterview.com",
        },
        {
            "q": "Multi-Agent 协作中可能出现什么问题？如何设计冲突解决机制？",
            "answer_hint": "策略冲突、资源竞争、信息冗余。解决：引入仲裁 Agent / 投票机制 / 层级管理。",
            "source": "adongwanai/AgentGuide 面经案例",
        },
        {
            "q": "设计一个知识库 Agent 的 RAG 系统，你会如何设计 Chunking 策略？",
            "answer_hint": "考虑文档类型（Markdown 按标题/PDF 按段落）、语义重叠、Token 预算。",
            "source": "GenAI_Agents / ai-eng-interview",
        },
    ],
    "week3": [
        {
            "q": "AI 产品经理和传统 PM 最大的区别是什么？作为 PM 你如何管理 AI 产品的「不确定性」？",
            "answer_hint": "AI 产品输出不可预测 → 需要灰度发布、人工兜底、持续评估、用户教育。",
            "source": "juejin AI PM 面试 30 题",
        },
        {
            "q": "如何判断一个业务场景「适合用 Agent 而非传统 Chatbot 或规则引擎」？",
            "answer_hint": "看是否需要多步推理、工具调用、外部知识查询、记忆持久化。",
            "source": "2bPM / crackpminterview.com",
        },
        {
            "q": "设计一个 Agent 产品的 MVP，你会如何界定范围？什么功能必须砍掉？",
            "answer_hint": "用 RICE 打分。MVP 应聚焦核心闭环（输入→推理→输出），暂缓多模态、多语言、复杂记忆。",
            "source": "igotanoffer.com AI PM 题",
        },
    ],
    "week4": [
        {
            "q": "Agent PRD 和传统 PRD 有什么不同？需要特别定义哪些内容？",
            "answer_hint": "需补充：行为规范（System Prompt）、边界条件（什么不做）、错误处理模式、回退策略、安全规则。",
            "source": "AIPM-Skills prd skill / 2bPM",
        },
        {
            "q": "设计 Agent 的人机交互模式：什么场景用确认模式，什么场景用自动模式？",
            "answer_hint": "高风险场景（支付/删除/发送邮件）用确认模式；低风险场景（查询/摘要）用自动模式。",
            "source": "crackpminterview.com",
        },
        {
            "q": "如何设计 Agent 的反馈机制让用户感到可控、安全？",
            "answer_hint": "进度条、置信度显示、'think step by step' 可视化、一键否决快捷键。",
            "source": "interview-guide 产品设计篇",
        },
    ],
    "week5": [
        {
            "q": "Agent 的 Prompt 如何做版本管理和 A/B 测试？",
            "answer_hint": "Git 管理 Prompt 版本、LangSmith 实验记录、按用户分桶测试、关键指标对比。",
            "source": "LangChain 官方文档 / interview-guide",
        },
        {
            "q": "Agent 产品的灰度发布策略怎么设计？",
            "answer_hint": "按用户比例 → 按场景限制 → 按工具集开放 → 全量。每个阶段有明确回滚条件。",
            "source": "ai-eng-interview 行为面试篇",
        },
        {
            "q": "用户反馈驱动的 Agent 迭代：你如何从海量会话中提取有价值的改进方向？",
            "answer_hint": "日志聚类→错误模式识别→人工抽样验证→优先级排序→迭代。关注用户修正频率最高的场景。",
            "source": "igotanoffer.com",
        },
    ],
    "week6": [
        {
            "q": "设计一个企业客服 Agent 系统，从需求到上线你会怎么做？（系统设计）",
            "answer_hint": "定义边界→意图识别→RAG 知识库→转人工策略→评估指标→灰度上线。",
            "source": "juejin AI PM 30 题 / 多家大厂系统设计题",
        },
        {
            "q": "GitHub Copilot / Cursor 这类编码 Agent 的产品逻辑是什么？有什么可以改进的地方？",
            "answer_hint": "上下文嵌入 → 补全生成 → 多行建议 → 自然语言指令。改进点：更好的项目理解、引用准确性。",
            "source": "crackpminterview.com 产品分析题",
        },
        {
            "q": "金融领域的 Agent 有什么特殊要求？如何确保合规和安全？",
            "answer_hint": "必须可审计、可回滚、人工复核、延迟容忍（宁可慢不能错）、通过金融监管合规审查。",
            "source": "adongwanai/AgentGuide 面经",
        },
    ],
    "week7": [
        {
            "q": "AI Agent 产品的成本和传统 SaaS 有什么不同？如何控制推理成本？",
            "answer_hint": "Token 成本（推理+工具调用）+ 向量存储 + API 调用。控制：模型量化、缓存、路由到小模型。",
            "source": "igotanoffer.com 策略题",
        },
        {
            "q": "Agent 产品的合规与治理：有哪些必须考虑的法律和伦理风险？",
            "answer_hint": "数据隐私（GDPR/PIPL）、模型偏见、可解释性、AI 监管法规（欧盟 AI Act、中国生成式 AI 管理办法）。",
            "source": "crackpminterview.com 安全篇",
        },
        {
            "q": "你怎么看 2026 年 MCP 协议对 Agent 生态的影响？",
            "answer_hint": "MCP 标准化了 Agent 与外部工具的连接方式，降低了集成成本，加速生态繁荣。",
            "source": "Scodive AI-Agent-Guide / 开放讨论题",
        },
    ],
    "week8": [
        {
            "q": "用 STAR 法则讲一个你做过的 AI 项目（包括产品假设、数据支撑、量化结果）",
            "answer_hint": "Situation: 产品背景。Task: 你负责什么。Action: 具体做什么。Result: 量化数据。",
            "source": "AIPM-Skills interview-diagnosis",
        },
        {
            "q": "AI PM 面试中最常见的陷阱题：『如果 Agent 准确率不够但业务方要求上线，你怎么办？』",
            "answer_hint": "灰度 10% 用户 + 人工兜底 + 承诺 2 周内迭代 + 风险告知书。",
            "source": "juejin AI PM 30 题 / interview-guide",
        },
        {
            "q": "反问面试官的高质量问题推荐（至少准备 5 个）",
            "answer_hint": "①贵司 Agent 产品如何评估成功率？②数据反馈闭环怎么设计的？③评测数据集谁维护的？④有什么你们踩过的坑？⑤团队结构和分工？",
            "source": "AIPM-Skills / crackedpm",
        },
        {
            "q": "你如何描述 Agent 产品和推荐系统、搜索引擎的关系和差异？",
            "answer_hint": "搜索负责检索→推荐负责猜测偏好→Agent 负责任务执行。三者可融合但核心职责不同。",
            "source": "interview-guide 开放讨论 / 多公司高频题",
        },
    ],
}

# ========================= 学习计划 8 周大纲 =========================

WEEKS = [
    {
        "week": 1,
        "phase": "Phase 1: 认知构建",
        "theme": "AI 与 Agent 基础认知",
        "days": [
            "AI 发展简史与关键里程碑（深度学习→大模型→Agent 的演进脉络）",
            "大语言模型（LLM）工作原理：Transformer、预训练、微调、RLHF",
            "Prompt Engineering 核心技巧：思维链、Few-shot、System Prompt 设计",
            "AI Agent 定义与分类：ReAct、Plan-and-Execute、Multi-Agent 架构",
            "理解工具调用（Function Calling / Tool Use）机制与实现原理",
            "Agent 的记忆系统：短期记忆、长期记忆、RAG、向量数据库",
            "本周总结 + 实战练习：用 Coze/Dify 搭建一个简单的 Agent",
        ],
    },
    {
        "week": 2,
        "phase": "Phase 1: 认知构建",
        "theme": "Agent 产品架构与技术栈",
        "days": [
            "主流 Agent 框架对比：LangGraph / CrewAI / AutoGen / OpenAI Agents SDK",
            "Agent 的规划与推理能力：ReAct vs Plan-and-Solve vs Tree-of-Thought",
            "Multi-Agent 协作模式：管理者-工作者、辩论式、市场式",
            "RAG 系统深度解析：Chunking、Embedding、检索策略、重排序",
            "Agent 的安全边界：提示注入防御、权限控制、沙箱隔离",
            "评估 Agent 质量：准确率、召回率、延迟、成本、幻觉率",
            "本周总结：Agent 架构设计文档模板 + 技术选型决策树",
        ],
    },
    {
        "week": 3,
        "phase": "Phase 2: 产品实战",
        "theme": "AI Agent 产品方法论",
        "days": [
            "AI 产品经理与传统 PM 的核心差异：不确定性管理、能力边界认知",
            "Agent 产品的用户研究：如何发现适合 Agent 而非 Chatbot 的场景",
            "定义 Agent 产品愿景：Mission Scope 原则与能力边界文档",
            "AI 产品的关键指标：准确率、用户留存、任务完成率、Token 成本",
            "Agent 产品的 MVP 设计：最小可行系统的范围界定技巧",
            "失败案例复盘：Meta Galactica、Microsoft Tay 等教训",
            "本周总结：AI PM 决策检查清单 + 产品定义模板",
        ],
    },
    {
        "week": 4,
        "phase": "Phase 2: 产品实战",
        "theme": "Agent 产品需求与设计",
        "days": [
            "Agent 产品需求文档（PRD）写法：行为规范、边界条件、错误处理",
            "设计 Agent 的人机交互模式：确认模式 vs 自动模式 vs 监督模式",
            "Agent 的对话设计：人格设定、语气控制、引导用户表达意图",
            "设计 Agent 反馈机制：不确定性传达、进度展示、错误恢复",
            "Agent 产品的多模态设计：语音、图像、文件、代码的交互融合",
            "Agent 产品的国际化与本地化策略",
            "本周总结：Agent PRD 模板 + 交互设计评审清单",
        ],
    },
    {
        "week": 5,
        "phase": "Phase 2: 产品实战",
        "theme": "Agent 产品开发与迭代",
        "days": [
            "Agent 开发流程：数据准备 → Prompt 开发 → 工具集成 → 评估 → 上线",
            "Prompt 的版本管理与 A/B 测试方法论",
            "Agent 的评估体系：自动化评测 vs 人工评测 vs 用户反馈回路",
            "Agent 产品的灰度发布与上线策略：限制用户量、限制工具集、限制场景",
            "Agent 的质量保障：回归测试、边缘案例、压力测试、安全测试",
            "用户反馈驱动的 Agent 迭代：日志分析、会话回放、意图识别",
            "本周总结：Agent 开发迭代 SOP + 上线检查清单",
        ],
    },
    {
        "week": 6,
        "phase": "Phase 3: 面试准备",
        "theme": "行业实战与案例分析",
        "days": [
            "客服 Agent：智能客服系统的架构设计、意图识别、转人工策略",
            "编程 Agent：GitHub Copilot / Claude Code / Cursor 的产品逻辑",
            "企业知识库 Agent：RAG 落地实践、权限控制、审计追踪",
            "电商与营销 Agent：推荐 Agent、客服 Agent、内容生成 Agent",
            "金融 Agent：风控规则 Agent、投研助手、合规审查",
            "医疗与教育 Agent：专业领域 Agent 的特殊要求与挑战",
            "本周总结：行业 Agent 产品画布 + 自己产品方向的灵感地图",
        ],
    },
    {
        "week": 7,
        "phase": "Phase 3: 面试准备",
        "theme": "Agent 的商业化与趋势",
        "days": [
            "AI Agent 的商业化模式：按量计费、订阅制、结果付费、混合模式",
            "Agent 的定价策略：Token 消耗模型、价值定价、竞品对标",
            "Agent 产品的成本模型：推理成本、存储成本、API 调用、人力维护",
            "Agent 产品的合规与治理：AI 法规、数据隐私、可解释性要求",
            "AI Agent 行业生态全景：从基座模型到 Agent 平台到垂直应用",
            "2025-2026 Agent 发展趋势：MCP 协议、多模态 Agent、Agent-to-Agent",
            "本周总结：Agent 产品商业计划书模板 + 竞品分析框架",
        ],
    },
    {
        "week": 8,
        "phase": "Phase 3: 面试准备",
        "theme": "面试准备与职业发展",
        "days": [
            "AI PM 面试必考题型：产品设计题（设计一个客服 Agent）、策略题（如何评估 Agent 质量）",
            "技术面试准备：LLM 原理、Agent 架构、RAG、评估体系的高频问题",
            "行为面试：用 STAR 法则讲述你的 AI 项目经验",
            "系统设计面试：设计一个面向企业的知识库 Agent 系统",
            "案例分析面试：给定错误案例，诊断问题并提出改进方案",
            "面试策略与薪资谈判：AI PM 的市场薪资范围、如何谈 Offer",
            "终极总结：AI Agent PM 能力雷达图 + 持续学习路线图 + 作品集建议",
        ],
    },
]

# ========================= 日期计算 =========================

PLAN_START = date(2026, 5, 17)
PLAN_END = date(2026, 7, 17)

PHASE_MAP = {
    1: ("Phase 1", "认知构建 — 理解 Agent 是什么、能做什么、不能做什么"),
    2: ("Phase 2", "产品实战 — 用 PM 方法论走一遍 Agent 产品从 0 到 1"),
    3: ("Phase 3", "面试准备 — 系统刷题 + STAR 故事 + 简历打磨"),
}


def get_phase(week_number: int) -> tuple:
    """根据周数返回阶段信息"""
    if week_number <= 2:
        return PHASE_MAP[1]
    elif week_number <= 5:
        return PHASE_MAP[2]
    else:
        return PHASE_MAP[3]


def get_plan_context(progress: dict) -> str:
    """生成当日在整体计划中的定位上下文"""
    week = progress["week_number"]
    day = progress["day"]
    total = progress["total_days"]
    topic = progress["day_topic"]
    theme = progress["week_theme"]
    day_in_week = (day - 1) % 7 + 1

    phase_name, phase_desc = get_phase(week)
    pct = int(day / total * 100)

    # 本周已学天数
    week_idx = week - 1
    day_idx = (day - 1) % 7

    prev_topics = WEEKS[week_idx]["days"][:day_idx]
    next_topics = WEEKS[week_idx]["days"][day_idx + 1:]

    context_parts = [
        f"## 📍 今日定位\n",
        f"**阶段**: {phase_name} — {phase_desc}",
        f"**周次**: 第 {week}/8 周 · {theme}",
        f"**当天**: 第 {day}/{total} 天（Day {day_in_week}/7 · 总进度 {pct}%）",
        f"**主题**: {topic}",
    ]

    if prev_topics:
        context_parts.append(f"\n**本周已学**:\n" + "\n".join(f"  ✅ {t}" for t in prev_topics))

    if next_topics:
        context_parts.append(f"\n**本周剩余**:\n" + "\n".join(f"  ⏳ {t}" for t in next_topics))

    context_parts.append(f"\n**整体进度**: {'█' * (pct // 5)}{'░' * (20 - pct // 5)} {pct}%")

    return "\n".join(context_parts)


def get_github_links_for_day(day: int) -> str:
    """获取当日关联的 GitHub 项目链接（HTML 格式）"""
    keys = DAY_GITHUB_LINKS.get(day, [])
    if not keys:
        return ""

    parts = ['<div style="background:#f0f4ff; border-left:4px solid #667eea; padding:12px 16px; margin:16px 0; border-radius:0 6px 6px 0;">']
    parts.append('<p style="font-size:13px; color:#667eea; font-weight:bold; margin:0 0 8px 0;">🔗 关联 GitHub 项目 / 资源</p>')
    parts.append('<ul style="padding-left:18px; margin:0; font-size:13px;">')
    for k in keys:
        proj = CORE_PROJECTS.get(k, {})
        if proj:
            name = proj.get("name", k)
            url = proj.get("url", "#")
            stars = proj.get("stars", "")
            desc = proj.get("desc", "")
            stars_text = f" ⭐{stars}" if stars and stars != "-" else ""
            parts.append(f'<li style="margin:4px 0;"><a href="{url}" style="color:#2563eb; text-decoration:none;">{name}</a>{stars_text} — {desc}</li>')
    parts.append("</ul></div>")
    return "\n".join(parts)


def get_interview_questions_for_week(week: int) -> str:
    """获取当周关联的面试题（HTML 格式）"""
    key = f"week{week}"
    qs = INTERVIEW_QUESTIONS.get(key, [])
    if not qs:
        return ""

    parts = ['<div style="background:#fff8f0; border-left:4px solid #f59e0b; padding:12px 16px; margin:16px 0; border-radius:0 6px 6px 0;">']
    parts.append('<p style="font-size:13px; color:#d97706; font-weight:bold; margin:0 0 8px 0;">🎯 本周关联面试题 — 建议重点掌握</p>')
    for i, q_item in enumerate(qs, 1):
        q = q_item["q"]
        hint = q_item["answer_hint"]
        src = q_item["source"]
        parts.append(f'<div style="margin:8px 0; padding:8px 10px; background:#fff; border-radius:4px; border:1px solid #fde68a;">')
        parts.append(f'<p style="font-size:13px; margin:0 0 4px 0;"><strong>Q{i}.</strong> {q}</p>')
        parts.append(f'<p style="font-size:12px; color:#666; margin:0 0 2px 0;">💡 {hint}</p>')
        parts.append(f'<p style="font-size:11px; color:#999; margin:0;">📌 来源：{src}</p>')
        parts.append("</div>")
    parts.append("<p style='font-size:11px; color:#999; margin:4px 0 0 0;'>面试资料来源：<a href='https://github.com/bcefghj/ai-agent-interview-guide' style='color:#2563eb;'>ai-agent-interview-guide</a> · <a href='https://github.com/adongwanai/AgentGuide' style='color:#2563eb;'>AgentGuide</a> · <a href='https://crackpminterview.com' style='color:#2563eb;'>CrackPMInterview</a> · 掘金/牛客面经</p>")
    parts.append("</div>")
    return "\n".join(parts)


# ========================= 间隔复习 =========================

def get_review_context(progress: dict) -> str:
    """为当日内容生成「昨日回顾」上下文（前 1/3/7 天知识点）"""
    review_days = progress.get("review_days", {})
    if not review_days:
        return ""

    parts = ["## 📝 温故知新 — 关联回顾\n"]
    parts.append("请在内容开头增加一个「关联回顾」板块，帮助学员巩固之前的知识点：\n")

    offsets = [1, 3, 7]
    labels = {1: "昨天", 3: "3 天前", 7: "一周前"}

    for offset in offsets:
        if offset in review_days:
            info = review_days[offset]
            parts.append(
                f"- **{labels[offset]}（Day {info['day']}，第 {info['week']} 周）**: "
                f"{info['topic']}\n"
            )
    parts.append(
        "\n对于每个回顾项，用 1-2 句话简要串联它与今天新知识的逻辑关联"
        "（如「昨天学的 RAG 检索策略，今天我们将探讨如何在实际 Agent 产品中落地」）"
    )
    return "\n".join(parts)


# ========================= 周末小测验 =========================

QUIZ_SYSTEM_PROMPT = """你是一个 AI Agent 产品经理的面试教练，正在为学员生成一套周末小测验。

## 测验格式要求

请按以下模块组织内容：

### 1️⃣ 本周回顾（Brief Recap）
用 100-200 字总结本周 7 天的核心主线，帮助学员建立本周的知识脉络。

### 2️⃣ 选择题（3 道）
每题 4 个选项，标注正确答案。
题目要覆盖本周不同天的核心概念。
考察点：概念辨析、场景判断、PM 决策。

格式：
```
Q1. [题干]
A. [选项]
B. [选项]
C. [选项]
D. [选项]
✅ 正确答案：X
💡 解析：为什么对 + 为什么其他选项不准确
```

### 3️⃣ 简答题（2 道）
开放式问题，模拟真实 PM 面试。
每题给：
- 题目
- 评分要点（PM 视角关注什么）
- 优秀答案示例（200 字以内）

### 4️⃣ 本周 GitHub 项目速览
列出本周提及的最有价值的 2-3 个开源项目，一句话推荐理由。

### 5️⃣ 下周预告
用两三句话预告下周的学习主题，让学员有心理准备。

## 风格要求
- 难度适中：覆盖基础概念 + 1-2 道进阶题
- 鼓励思考：不要只给答案，要有「为什么」
- 长度：1500-2500 字
"""

WEEKLY_REVIEW_PROMPT = """你是一个 AI Agent 产品经理的学习教练，正在为学员撰写每周进度回顾（Week Review）。

## 内容结构要求

### 1️⃣ 本周概览（Top-Down Summary）
- 本周主题：一句话概括
- 本周学到的 3-5 个核心知识点（用列表 + 一句话解释）
- 本周在整体 8 周计划中的定位

### 2️⃣ 知识图谱
用 Markdown 表格列出本周每天学到了什么、关键概念、和前置/后置知识的关系：

| 天次 | 主题 | 关键概念 | 关联项目 |
|------|------|----------|----------|
| Day X | [主题] | [2-3 个概念] | [项目名] |

### 3️⃣ 掌握度评估（Self-Check）
列出 5-8 道 self-check 问题，学员可以在脑子里过一遍：
- 如果都答得上 → 掌握良好
- 如果有 2-3 道模糊 → 建议复习对应天的内容
- 如果有 4+ 道不会 → 建议重读本周内容

### 4️⃣ 本周面试题复盘
回顾本周邮件中出现的面试题，选 2 道最有价值的加深解析：
- 题目 + 为什么这道题有代表性
- 更多答题角度（比 Day 推送时更深入）
- PM 面试官的评分偏好

### 5️⃣ 实践回顾
- 本周有哪些可以动手实践的？完成了吗？
- 如果没完成，2-3 个轻量替代方案
- 下周需要哪些前置知识？

### 6️⃣ 下周预习
- 下周主题一句话预告
- 建议提前准备的 2-3 个方向（阅读/体验/调研）

## 风格要求
- 长度 1500-2500 字
- 用数据说话（第 X 周 / 已完成 Y 天 / 进度 Z%）
- 语气像一位关心学员进度的 PM mentor
"""

# ========================= DeepSeek API 调用 =========================

def call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 7000) -> str:
    """调用 DeepSeek Chat API（扩展输出以容纳更多内容）"""
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")

    req = Request(
        DEEPSEEK_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
    )

    try:
        with urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except URLError as e:
        return f"<p style='color:red'>DeepSeek API 调用失败: {e}</p>"
    except (KeyError, json.JSONDecodeError) as e:
        return f"<p style='color:red'>DeepSeek API 返回解析失败: {e}</p>"


# ========================= AI 内容生成（增强版 System Prompt）=========================

SYSTEM_PROMPT = """你是 AI Agent 产品经理导师，正在为一位转型 AI PM 的学员写每日邮件学习内容。内容要求如下：

## 核心定位
读者是一位有技术背景、正在系统学习 AI Agent 产品经理的学员。内容要达到「收到邮件就能打开学习」的标准。

## 内容结构要求
每篇内容必须包含以下 6 个模块：

### 0️⃣ 关联回顾（Warm Up — 间隔复习）
放在正文最前面，串联前一天/3天前/一周前的知识点与今天新内容的逻辑关系。
格式：
```
📌 关联回顾
- 昨天（Day X）：[知识点] → [和今天的关联]
- 3 天前（Day Y）：[知识点] → [和今天的关联]
- 一周前（Day Z）：[知识点] → [和今天的关联]
```
如果用户提供的回顾信息中没有对应项，就跳过。
目的是帮学员建立知识网络，而不是死记硬背。

### 1️⃣ 今天学什么（Where We Are）
开头先写一段「今日定位」：当前是第几周、哪个 Phase、这个 Week 的主题是什么。用一句话说明今天的知识点如何对应该 Week 整体目标。如果今天内容依赖前置知识，提醒一下。

### 2️⃣ 核心知识点（2-3 个关键概念）
每个概念用「是什么 → 为什么重要 → 实际怎么用」三层解释。
- 关键术语标注英文原文（如 思维链 Chain-of-Thought）
- 配一个具体案例（真实或高度拟真）

### 3️⃣ GitHub/资源关联
当今天的内容涉及以下主题时，务必在相应段落提及关联的开源项目或资源：
- Agent 框架 → 提及 LangGraph / CrewAI / AutoGen / OpenAI Agents SDK 等
- 面试题 → 提及 ai-agent-interview-guide / AgentGuide
- AI PM 方法论 → 提及 2bPM / AIPM-Skills
- RAG / 技术架构 → 提及 hello-agents / GenAI_Agents
- 行业案例 → 提及 500-AI-Agents-Projects
格式：用一句话说明「这个项目为什么值得看」（如：『hello-agents 的第 3 章详细讲解了 ReAct 循环的代码实现，推荐配合阅读』）不要只列名字。

### 4️⃣ 面试题实战（Interview Corner）
在内容尾部插入面试题板块，包含：
- 2-3 道与今天内容直接相关的面试题或面试经验
- 每题给出「考察点」和「答题思路（PM 视角）」
- 如果是大厂真题，标注公司名和题型
来源包括：ai-agent-interview-guide（200+ 题）、AgentGuide（4.9k⭐ 面经）、掘金 AI PM 30 题、crackpminterview

### 5️⃣ 今日行动 + 思考题
- 1 个可立刻做的行动（如：打开 xxx 体验一下 / 写一段 xxx 笔记 / 画一张 xxx 图）
- 2-3 道思考题（开放性问题，用来反思和内化）

## 风格要求
- 专业但不晦涩，用 PM 能理解的比喻和类比
- 长度 2000-3000 字中文
- 使用 Markdown 格式，注意邮件可读性
- 结尾附加最新面经或行业动态

## 可视化增强要求（请严格遵守）
邮件内容要「一眼能扫出结构」，使用以下手段增强可读性：

### 表格
- 对比两件事（如 RAG vs Function Calling）必须用 | 表格
- 学习路径/步骤序列用编号表格或列表
- 表格格式：
  | 维度 | 方案A | 方案B |
  |------|-------|-------|
  | 延迟 | XX | YY |

### 案例框
- 每个核心概念配 1 个真实或高度拟真的案例
- 案例用 `>` 引用块包裹，标注「💡 实战案例」
- 案例格式：
  > 💡 **实战案例：某 AI 客服 Agent**
  > 背景：... 问题：... 方案：... 结果：...

### 代码块
- 涉及 Prompt 示例、架构配置、API 调用时，用 \`\`\` 代码块
- 标注语言类型（\`\`\`json, \`\`\`python, \`\`\`yaml）
- 代码块不要超过 15 行，长示例分段展示

### 金句/强调
- 关键洞察用 **加粗** 或 `> **💎 关键洞察**` 强调
- 核心数字和指标用 **加粗**
- 不要过度使用（每篇不超过 3-5 处）

### 列表嵌套
- 层次超过 2 层的列表用缩进 + 项目符号区分
- 别名的概念用 `（即 ...）` 或 `- 别称：...`
- 数字列表用于步骤/流程，项目符号用于列举/分类
"""


def generate_daily_content(progress: dict) -> str:
    """生成当天内容（日常学习或周末测验）"""
    day = progress["day"]
    total = progress["total_days"]
    week = progress["week_number"]
    phase_name, phase_desc = get_phase(week)
    theme = progress["week_theme"]
    topic = progress["day_topic"]
    day_type = progress.get("day_type", "daily")
    is_weekend = progress["is_weekend"]

    if day_type == "weekly_review":
        # === 📊 周六：每周进度周报 ===
        user_prompt = f"""## 学员当前位置

Phase：{phase_name} 第 {week}/8 周
主题：{theme}
总进度：第 {day}/{total} 天

## 本周每日主题

以下为本周 7 天的学习主题，请基于这些生成一份全面的周报：

"""
        for i, d in enumerate(WEEKS[week - 1]["days"], 1):
            user_prompt += f"- Day {i}: {d}\n"

        user_prompt += f"""

## 关联项目

"""
        week_start_day = (week - 1) * 7 + 1
        seen = set()
        for d in range(week_start_day, min(week_start_day + 7, total + 1)):
            for k in DAY_GITHUB_LINKS.get(d, []):
                if k not in seen:
                    seen.add(k)
                    proj = CORE_PROJECTS.get(k, {})
                    if proj:
                        user_prompt += f"- {proj['name']} ({proj.get('stars','')}): {proj.get('desc','')}\n"

        llm_content = call_deepseek(WEEKLY_REVIEW_PROMPT, user_prompt, max_tokens=6000)
        return llm_content

    if day_type == "quiz":
        # === 🎯 周日：周末小测验 ===
        user_prompt = f"""## 学员当前位置

第 {week} 周 · 主题：{theme}

## 本周每日主题

以下为本周 7 天的学习主题，请基于这些内容生成一套小测验：
"""
        for i, d in enumerate(WEEKS[week - 1]["days"], 1):
            user_prompt += f"- Day {i}: {d}\n"

        user_prompt += f"""

## 关联项目

"""
        # 收集本周关联的 GitHub 项目
        week_start_day = (week - 1) * 7 + 1
        seen = set()
        for d in range(week_start_day, min(week_start_day + 7, total + 1)):
            for k in DAY_GITHUB_LINKS.get(d, []):
                if k not in seen:
                    seen.add(k)
                    proj = CORE_PROJECTS.get(k, {})
                    if proj:
                        user_prompt += f"- {proj['name']} ({proj.get('stars','')}): {proj.get('desc','')}\n"

        llm_content = call_deepseek(QUIZ_SYSTEM_PROMPT, user_prompt, max_tokens=6000)
        return llm_content

    # === 📖 日常学习模式（带间隔复习） ===
    plan_context = get_plan_context(progress)

    # 获取复习上下文
    review_ctx = get_review_context(progress)

    # 获取本周面试题（作为补充素材）
    week_q_key = f"week{week}"
    interview_material = INTERVIEW_QUESTIONS.get(week_q_key, [])
    interview_text = "本周相关面试题素材（请在 Interview Corner 板块中使用）：\n"
    if interview_material:
        for i, qi in enumerate(interview_material, 1):
            interview_text += f"\n【Q{i}】{qi['q']}\n考察点/答题思路：{qi['answer_hint']}\n来源：{qi['source']}\n"

    user_prompt = f"""## 学员当前位置

{plan_context}

## 阶段信息
- 阶段: {phase_name}
- 阶段描述: {phase_desc}
- 第 {week} 周共 8 周 ｜ 第 {day}/{total} 天

## 当日主题

{topic}

## 间隔复习 — 关联回顾提示

{review_ctx}

## 今日内容生成要求

请基于上述定位生成今日学习内容。务必遵守 SYSTEM PROMPT 中的 5 模块结构。

特别提醒：
1. 在正文之前先写「关联回顾」板块，串联昨日/3天前/一周前的知识点
2. 如果今天内容涉及具体技术和框架，请引用相关开源项目并说明为什么值得看
3. Interview Corner 板块要包含真实面试题的答题思路（可用下面给的素材）
4. 今天是在 {phase_name} 的第 {week} 周，请融合这个定位感

## 面试素材（可选参考，请融入 Interview Corner 板块）

{interview_text}"""

    llm_content = call_deepseek(SYSTEM_PROMPT, user_prompt, max_tokens=8000)
    return llm_content


# ========================= 邮件生成（增强版 HTML）=========================

def build_email_html(progress: dict, content: str, day_type: str = "daily") -> str:
    """生成完整 HTML 邮件（日常学习 / 周报 / 测验）"""
    day = progress["day"]
    total = progress["total_days"]
    week = progress["week_number"]
    phase_name, phase_desc = get_phase(week)
    theme = progress["week_theme"]
    topic = progress["day_topic"]
    today_str = progress["today"].strftime("%Y-%m-%d %A")
    pct = int(day / total * 100)

    # 将 markdown 内容转为 HTML
    body_html = markdown_to_html(content)

    # 生成 GitHub 项目链接区域（周报/测验模式跳过）
    github_links = "" if day_type != "daily" else get_github_links_for_day(day)

    # 生成面试题区域（周报/测验模式跳过）
    interview_section = "" if day_type != "daily" else get_interview_questions_for_week(week)

    # 周进度
    week_pct = int((day - 1) % 7 / 7 * 100)

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; margin:0; padding:0; background:#f5f5f5;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5; padding:20px 0;">
<tr><td align="center">
<table width="660" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding:30px 40px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td>
<h1 style="color:#ffffff; font-size:22px; margin:0 0 4px 0;">AI Agent PM 学习计划</h1>
<p style="color:rgba(255,255,255,0.85); font-size:13px; margin:0;">
{phase_name} · 第 {week}/8 周 · {today_str}
</p>
</td>
<td style="text-align:right; width:80px;">
<div style="background:rgba(255,255,255,0.2); border-radius:8px; padding:8px 6px; text-align:center;">
<span style="color:#fff; font-size:22px; font-weight:bold;">{day}</span><br>
<span style="color:rgba(255,255,255,0.7); font-size:11px;">/ {total}</span>
</div>
</td>
</tr>
</table>
</td></tr>

{'''<tr><td style="background:#fff3cd; border-left:6px solid #ffc107; padding:12px 40px;">
<table width="100%"><tr>
<td style="font-size:14px; color:#856404;">
<strong>🎯 周末小测验</strong> — 用 5 道题检验本周学习成果
</td>
<td style="text-align:right; font-size:12px; color:#856404;">
正确率 × 思考过程 &gt; 答案本身
</td>
</tr></table>
</td></tr>''' if is_quiz else ''}

<!-- Phase badge -->
<tr><td style="padding:0 40px; background:#fafafa;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="font-size:12px; color:#888; padding:8px 0 2px 0;">
{phase_desc}
</td>
</tr></table>
</td></tr>

<!-- Progress bars -->
<tr><td style="padding:0 40px 4px 40px; background:#fafafa;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="font-size:11px; color:#aaa; width:60px;">整体</td>
<td style="padding:2px 0;">
<div style="height:5px; background:#e0e0e0; border-radius:3px;">
<div style="height:5px; width:{pct}%; background:linear-gradient(90deg, #667eea, #764ba2); border-radius:3px;"></div>
</div>
</td>
<td style="font-size:11px; color:#aaa; width:40px; text-align:right;">{pct}%</td>
</tr>
<tr>
<td style="font-size:11px; color:#aaa; width:60px;">本周</td>
<td style="padding:2px 0;">
<div style="height:5px; background:#e0e0e0; border-radius:3px;">
<div style="height:5px; width:{week_pct}%; background:linear-gradient(90deg, #667eea, #764ba2); border-radius:3px;"></div>
</div>
</td>
<td style="font-size:11px; color:#aaa; width:40px; text-align:right;">{week_pct}%</td>
</tr>
</table>
</td></tr>

<!-- Week theme -->
<tr><td style="padding:4px 40px 0 40px; background:#fafafa;">
<p style="font-size:13px; color:#667eea; font-weight:600; margin:0 0 10px 0;">📌 第 {week} 周 · {theme}</p>
</td></tr>

<!-- Topic banner -->
<tr><td style="padding:16px 40px 8px 40px;">
<h2 style="font-size:19px; color:#333; margin:0 0 4px 0;">📖 {topic}</h2>
</td></tr>

<!-- GitHub Links (injected before content) -->
{("<tr><td style='padding:0 40px;'>" + github_links + "</td></tr>") if github_links else ""}

<!-- Content -->
<tr><td style="padding:8px 40px 20px 40px; font-size:15px; line-height:1.8; color:#333;">
{body_html}
</td></tr>

<!-- Interview Section (injected after content) -->
{("<tr><td style='padding:0 40px 8px 40px;'>" + interview_section + "</td></tr>") if interview_section else ""}

<!-- Footer -->
<tr><td style="background:#fafafa; border-top:1px solid #eee; padding:20px 40px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="font-size:12px; color:#999;">
📬 每日 07:00 自动推送 | 计划周期：{PLAN_START} → {PLAN_END}<br>
🤖 由 DeepSeek Chat 在线生成 · 内容仅供参考学习
</td>
<td style="text-align:right; font-size:11px; color:#ccc;">
<a href="https://github.com/bcefghj/ai-agent-interview-guide" style="color:#999; text-decoration:none;">面经</a>
· <a href="https://github.com/datawhalechina/hello-agents" style="color:#999; text-decoration:none;">教程</a>
· <a href="https://github.com/StevenJokess/2bPM" style="color:#999; text-decoration:none;">2bPM</a>
</td>
</tr>
</table>
</td></tr>

</table>
</td></tr></table>
</body></html>"""
    return html


def markdown_to_html(md: str) -> str:
    """极简 Markdown → HTML 转换，足够邮件阅读即可"""
    html = md

    # Code blocks (先处理，避免被其他规则污染)
    html = re.sub(r'```(\w*)\n(.*?)```', r'<pre style="background:#f6f8fa; padding:12px; border-radius:6px; font-size:13px; overflow-x:auto; border:1px solid #e1e4e8;"><code>\2</code></pre>', html, flags=re.DOTALL)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code style="background:#f0f0f0; padding:2px 5px; border-radius:3px; font-size:13px;">\1</code>', html)

    # Headings
    html = re.sub(r'^### (.+)$', r'<h3 style="font-size:17px; color:#2c3e50; margin:20px 0 8px 0; border-bottom:1px solid #eee; padding-bottom:4px;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2 style="font-size:19px; color:#2c3e50; margin:24px 0 10px 0; border-bottom:2px solid #667eea; padding-bottom:6px;">\1</h2>', html, flags=re.MULTILINE)

    # Bold + Italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Bullet lists
    html = re.sub(r'^- (.+)$', r'<li style="margin:4px 0;">\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li.*</li>\n)+', lambda m: '<ul style="padding-left:20px; margin:8px 0;">' + m.group(0) + '</ul>', html)

    # Numbered lists
    html = re.sub(r'^\d+\. (.+)$', r'<li style="margin:4px 0;">\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(?:<li.*</li>\n)+', lambda m: '<ol style="padding-left:20px; margin:8px 0;">' + m.group(0) + '</ol>', html)

    # Horizontal rules
    html = re.sub(r'^---+\s*$', r'<hr style="border:none; border-top:1px solid #ddd; margin:20px 0;">', html, flags=re.MULTILINE)

    # Blockquotes
    html = re.sub(r'^> (.+)$', r'<blockquote style="border-left:4px solid #667eea; padding:10px 15px; margin:12px 0; background:#f8f9ff; color:#555;">\1</blockquote>', html, flags=re.MULTILINE)

    # Paragraphs: wrap non-tag lines in <p>
    lines = html.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(('<h', '<li', '<ul', '<ol', '<pre', '<blockquote', '<hr', '<div', '<table')):
            result.append(f'<p style="margin:8px 0;">{stripped}</p>')
        else:
            result.append(line)
    html = '\n'.join(result)

    return html


def send_email(html_content: str, subject: str, max_retries: int = 3):
    """发送邮件到所有目标邮箱（带重试+本地备份兜底）"""
    import time

    all_ok = True
    ctx = ssl.create_default_context()

    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP_SSL(
                SMTP_CONFIG["host"], SMTP_CONFIG["port"],
                context=ctx, timeout=20
            ) as server:
                server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])

                for to_email in TO_EMAILS:
                    msg = MIMEMultipart("alternative")
                    msg["From"] = formataddr(("AI Agent PM Learning", SMTP_CONFIG["user"]))
                    msg["To"] = to_email
                    msg["Subject"] = Header(subject, "utf-8")
                    msg["Message-ID"] = (
                        f"<pm-plan-{date.today().isoformat()}"
                        f"-{abs(hash(to_email)) % 10000}@hermes>"
                    )
                    msg.attach(MIMEText(html_content, "html", "utf-8"))
                    server.sendmail(SMTP_CONFIG["user"], [to_email], msg.as_string())
                    print(f"✅ 已发送 → {to_email}")

            print("✅ 全部发送完成")
            return True

        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ 认证失败（授权码无效或被撤销）: {e}")
            save_email_locally(html_content, subject)
            raise

        except (smtplib.SMTPServerDisconnected, smtplib.SMTPException, ConnectionError,
                TimeoutError, OSError) as e:
            if attempt < max_retries:
                wait = 2 ** attempt * 5  # 指数退避：10s → 20s → 40s
                print(f"⚠️ 第 {attempt}/{max_retries} 次发送失败: {e}")
                print(f"   {wait} 秒后重试...")
                time.sleep(wait)
            else:
                print(f"❌ QQ SMTP {max_retries} 次均失败，切换备用方案")
                all_ok = False

    # —— 兜底：存本地 .eml 文件 ——
    if not all_ok:
        save_email_locally(html_content, subject)
    return False


def save_email_locally(html_content: str, subject: str):
    """QQ SMTP 不可用时将邮件存到本地（.eml 格式，双击即可打开）"""
    import os
    backup_dir = os.path.expanduser("~/.hermes/email_backups")
    os.makedirs(backup_dir, exist_ok=True)

    today_str = date.today().isoformat()
    for to_email in TO_EMAILS:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("AI Agent PM Learning", SMTP_CONFIG["user"]))
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8")
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
        msg["X-Fallback"] = "QQ SMTP was unavailable"
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        safe_email = to_email.replace("@", "_at_").replace(".", "_")
        filename = f"pm_plan_{today_str}_{safe_email}.eml"
        filepath = os.path.join(backup_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(msg.as_string())
        print(f"📁 已保存本地副本 → {filepath}")

    print(f"\n💡 本地 .eml 文件双击即可在 Apple Mail / Outlook 中打开")
    print(f"   或手动转发: 打开文件后点击「转发」发送到 {', '.join(TO_EMAILS)}")


# ========================= 计划进度计算 =========================

def get_plan_progress(today: date) -> Optional[dict]:
    """根据日期计算当天的学习进度"""
    if today < PLAN_START or today > PLAN_END:
        return None

    day = (today - PLAN_START).days + 1
    total = (PLAN_END - PLAN_START).days + 1

    # 计算周数 (1-based)
    week_number = (day - 1) // 7 + 1
    if week_number > 8:
        week_number = 8

    day_in_week = (day - 1) % 7
    week_idx = week_number - 1

    week_info = WEEKS[week_idx]
    day_topic = week_info["days"][day_in_week] if day_in_week < len(week_info["days"]) else week_info["days"][-1]

    day_in_week = day_in_week + 1  # 1-7

    # 计算前 1/3/7 天的 topic 用于回顾
    review_days = {}
    for offset in [1, 3, 7]:
        prev_day = day - offset
        if prev_day >= 1:
            prev_week_num = (prev_day - 1) // 7
            prev_day_in_week = (prev_day - 1) % 7
            if prev_week_num < len(WEEKS):
                prev_week = WEEKS[prev_week_num]
                if prev_day_in_week < len(prev_week["days"]):
                    review_days[offset] = {
                        "day": prev_day,
                        "topic": prev_week["days"][prev_day_in_week],
                        "week": prev_week_num + 1,
                    }

    return {
        "day": day,
        "total_days": total,
        "week_number": week_number,
        "day_in_week": day_in_week,
        "week_theme": week_info["theme"],
        "day_topic": day_topic,
        "today": today,
        "review_days": review_days,
        "is_weekend": day_in_week >= 6,
        "day_type": "weekly_review" if day_in_week == 6 else ("quiz" if day_in_week == 7 else "daily"),
    }


# ========================= 品质门禁 =========================

def validate_content(content: str, progress: dict) -> str:
    """质量检查：长度不足或关键术语缺失时，用模板内容补充"""
    min_len = 500
    if len(content) >= min_len:
        return content  # 合格，直接通过

    # 太短了，补一个后备内容
    topic = progress["day_topic"]
    week = progress["week_number"]
    theme = progress["week_theme"]
    fallback = f"""
## 📖 {topic}

> ⚠️ 今日内容生成较短（{len(content)} 字符），以下为补充要点：

{content}

---

### 学习建议

本日主题「{topic}」是第 {week} 周「{theme}」的重要组成部分。
建议：
1. 用自己话写一段 200 字总结
2. 找 2-3 个相关的开源项目或文章扩展阅读
3. 在本周剩余几天注意关联学习
"""
    return fallback.strip()


def archive_to_obsidian(content: str, progress: dict):
    """将当日学习内容归档到 Obsidian 对话归档"""
    import subprocess
    import tempfile
    import os

    today_str = progress["today"].strftime("%Y-%m-%d")
    week = progress["week_number"]
    day = progress["day"]
    topic = progress["day_topic"]
    phase_name, phase_desc = get_phase(week)

    # 写临时归档文件
    archive_text = f"""### 📍 定位

{phase_name} · 第 {week}/8 周 · 第 {day}/{progress['total_days']} 天
主题：{topic}

### 知识点

{content}

### 相关链接

- 学习计划：{PLAN_START} → {PLAN_END}
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(archive_text)
        tmp_path = f.name

    tags = f"AI Agent PM,学习计划,Phase{phase_name.replace(' ','')}"
    title = f"[AI Agent PM] Day{day} 第{week}周 {topic[:50]}"

    try:
        result = subprocess.run(
            ["bash", os.path.expanduser("~/.hermes/scripts/hermes-obsidian.sh"),
             "add", title, tags, tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print(f"✅ 已归档到 Obsidian（{title}）")
        else:
            print(f"⚠️ Obsidian 归档失败: {result.stderr[:200]}")
    except Exception as e:
        print(f"⚠️ Obsidian 归档异常: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ========================= 主流程 =========================

def main():
    today = date(2026, 5, 17)
    progress = get_plan_progress(today)

    if progress is None:
        print(f"📅 计划已结束（{PLAN_START} → {PLAN_END}），当前日期 {today}")
        return

    day = progress["day"]
    week = progress["week_number"]
    phase_name, _ = get_phase(week)
    theme = progress["week_theme"]
    topic = progress["day_topic"]
    is_weekend = progress["is_weekend"]
    day_type = progress.get("day_type", "daily")

    mode_labels = {
        "daily": "📖 日常学习",
        "weekly_review": "📊 每周进度周报",
        "quiz": "🎯 周末小测验",
    }
    mode_label = mode_labels.get(day_type, "📖 日常学习")
    print(f"📚 {phase_name} · 第 {week} 周 · 第 {day}/{progress['total_days']} 天 · {mode_label}：{topic}")

    # 1. 用 DeepSeek 生成内容
    print(f"🤖 正在调用 DeepSeek Chat API 生成{mode_label}（增强版 v3）...")
    content = generate_daily_content(progress)
    print(f"✅ 内容生成完成（{len(content)} 字符）")

    # 2. 质量门禁（仅日常内容）
    if day_type == "daily":
        content = validate_content(content, progress)

    # 3. 构建邮件
    html = build_email_html(progress, content, is_quiz=(day_type=="quiz"))
    day_labels = {"daily": f"Day{progress['day_in_week']}", "weekly_review": "周报", "quiz": "Quiz"}
    subject = f"[AI Agent PM] {phase_name} 第{week}周 {day_labels.get(day_type, '')} · {topic[:40]}"

    # 4. 发送
    print(f"📧 正在发送邮件...")
    send_email(html, subject)

    # 5. 归档到 Obsidian
    print("📝 正在归档到 Obsidian...")
    archive_to_obsidian(content, progress)


if __name__ == "__main__":
    main()
