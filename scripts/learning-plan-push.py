#!/usr/bin/env python3
"""
AI Agent PM 学习计划每日推送 — DeepSeek 在线版 (增强版 v3)
每天早上 07:00 生成当日详细学习内容，推送到两个邮箱
功能增强：
1. 明确标注当天内容在整体计划中的位置（Phase/Week/Day/进度）
2. 关联 GitHub 项目链接（当日相关项目 + 链接）
3. 补充面试经验内容（相关面试题 + 面经要点）
4. 贯穿项目实操路线：8 周从 0 到 1 构建一个 Agent 产品 Portfolio
5. STAR 故事系统性积累：面试时信手拈来的实战案例
6. 语音版推送：macOS TTS 生成精华摘要 MP3 并作为邮件附件发送
"""

import smtplib
import ssl
import json
import re
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
from urllib.request import Request, urlopen
from urllib.error import URLError
from http.client import IncompleteRead
from typing import Optional
import os
import argparse

# ========================= 配置（优先从 .env 读取）=========================

def _load_env(key: str, default: str = "") -> str:
    """从 ~/.hermes/.env 读取变量"""
    env_path = "/Users/liuwei/.hermes/.env"
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    val = line[len(key) + 1:]
                    # 去掉可选的引号
                    return val.strip("\"'")
                if line.startswith("export " + key + "="):
                    val = line[len("export " + key + "="):]
                    return val.strip("\"'")
    except (FileNotFoundError, IOError):
        pass
    return default

SMTP_PASSWORD = _load_env("SMTP_PASSWORD", "tokhhpbgyavkcbdi")
SMTP_CONFIG = {
    "host": "smtp.qq.com",
    "port": 465,
    "user": "453169854@qq.com",
    "password": SMTP_PASSWORD,
}

TO_EMAILS = [
    "liuwei634@huawei.com",
    "stwilliam503388@gmail.com",
]

DEEPSEEK_API_KEY = _load_env("DEEPSEEK_API_KEY", "sk-1fce5227c29a49749f8cc7c5637fcbed")
DEEPSEEK_API_URL = _load_env("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = _load_env("DEEPSEEK_MODEL", "deepseek-chat")

OLLAMA_BASE_URL = _load_env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _load_env("OLLAMA_MODEL", "qwen3:32b")

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

# ========================= STAR 故事库（产品经理面试）=========================
# 每个故事对应一个场景，按 Phase 分类，供面试时使用

STAR_STORIES: dict[str, list[dict]] = {
    "通用": [
        {
            "title": "推动 AI Agent 从 POC 到生产",
            "situation": "所在公司探索 AI Agent 落地，团队做了多个 POC 但都没有上线。CEO 质疑 ROI。",
            "task": "负责主导一个 Agent 项目的产品化推进，在 3 个月内展示可量化的业务价值。",
            "action": "1) 筛选高价值场景（客服分流 → 目标减少 30% 人工量）\n2) 设计 MVP：只做 3 种工单类型，用 LangGraph 编排多步 Agent\n3) 建立评估指标：首次解决率(FCR) + 平均处理时长(AHT) + 用户满意度\n4) 与工程团队协作搭建反馈循环：用户 ⭐ 打分 → 自动纠偏\n5) 分阶段上线：先 10% 流量 → 优化 → 全量",
            "result": "3 个月内 FCR 提升 22%，AHT 降低 35%，获得 CEO 批准 Phase 2 扩展预算。学到的关键：没有评估体系就上 Agent 是灾难。",
            "lessons": "产品经理的核心贡献不在于定义 Agent 做什么，而在于定义「怎么知道 Agent 做好了」。",
        },
        {
            "title": "跨团队协调 Agent 策略冲突",
            "situation": "客服部和运营部都想要 Agent 产品团队为其开发 Agent，但资源只够做一条线。",
            "task": "在资源约束下做优先级决策，同时两个部门都不能得罪。",
            "action": "1) 统一需求评估框架：用价值-成本-风险三维打分\n2) 引入「Agent 共享池」概念：核心能力（意图识别、FAQ RAG、情绪判断）一次搭建，多部门复用\n3) 用 2x2 矩阵展示双方 ROI，获得 VP 级支持\n4) 承诺客服部 6 周 MVP + 运营部 8 周 MVP",
            "result": "核心 Agent 能力复用率达 70%，两个部门都在各自时间线内上线。学会了 PM 不能做单选题，要做「多选题的资源分配」",
            "lessons": "Agent 的核心复用价值体现在底层能力层，不是应用层。",
        },
        {
            "title": "应对 Agent 幻觉导致的生产事故",
            "situation": "内部知识库 Agent 上线后第 2 天，生成了错误的合规建议，被合规团队发现并紧急下线。",
            "task": "修复信任危机，重新设计安全机制后再次上线。",
            "action": "1) 紧急下线的同时进行根本原因分析：发现 RAG 检索结果不够精确，LLM 自行「脑补」了没有来源的结论\n2) 增加三层防护：RAG 结果相关性阈值 → LLM 必须引用来源 → 后处理检查（answers without citation → 拦截）\n3) 建立「Agent 安全审查清单」产品文档\n4) 与法务/合规团队建立 Agent 发布的审批流程\n5) 灰度发布（5% → 30% → 100%），每阶段收集反馈",
            "result": "重新上线后正确率 99.3%，合规团队主动参与后续 Agent 产品设计。PM 在 Agent 产品的核心价值 = 定义「安全边界」。",
            "lessons": "Agent 产品不是功能型产品，是信任型产品。一次幻觉事故 = 三次正确的成本才能挽回。",
        },
    ],
    "Phase1": [
        {
            "title": "说服团队放弃 Rule-based 转向 Agent",
            "situation": "团队已有一个基于规则的工作流引擎（2 年维护史），稳定性尚可。有人提议用 LLM Agent 重写，被质疑「为了 AI 而 AI」。",
            "task": "证明 Agent 方案的价值，同时不否定现有系统的功绩，减少团队抵触。",
            "action": "1) 选取现有系统处理最差的 5 个长尾场景做 AB 测试\n2) 定义量化标准：处理成功率 + 平均人机协同时间 + 维护成本\n3) Agent 方案在 3/5 场景显著优于现有方案\n4) 设计混合架构：核心稳定流程沿用规则引擎 + 长尾场景用 Agent\n5) 用数据驱动决策，避免「技术选型之争」",
            "result": "6 个月后 Agent 接管了 40% 流量，团队从抵触变成主动提 Agent 优化需求。学会：不要做颠覆者，做渐进优化者。",
            "lessons": "Agent 产品经理第一课：永远不要和现有系统 PK 稳定性，要 PK 灵活性和处理长尾的能力。",
        },
    ],
    "Phase2": [
        {
            "title": "设计多 Agent 协作的用户体验",
            "situation": "一个复杂业务流程需要 3 个 Agent 协作（客服 Agent → 审批 Agent → 数据分析 Agent），用户反馈「不知道 Agent 在做什么」。",
            "task": "重新设计多 Agent 协作的用户体验，让用户有透明度和控制感。",
            "action": "1) 梳理 13 个 Agent 协作的状态流转图\n2) 设计「Agent 协作看板」：用户看到每个 Agent 当前状态、输入输出、预-计完成时间\n3) 增加「人工介入点」：在任何步骤用户可以打断并接管\n4) 引入「Agent 任务 ID」串联所有 Agent 在同一流程中的日志\n5) 用户测试：5 人可用性测试 → 迭代 → 正式上线",
            "result": "用户满意度提升 45%，协作 Agent 的完成率从 62% 提升到 88%。学到了：多 Agent 产品的 UX 比单 Agent 难 10 倍。",
            "lessons": "好的 Agent 产品不是「Agent 自己做所有事」，而是「用户和 Agent 高效协作」。",
        },
    ],
    "Phase3": [
        {
            "title": "Agent 上线后的数据分析闭环",
            "situation": "第一个 Agent MVP 上线 2 周后，产品组说「看不出来效果怎么样」，只知道用了多少 token。",
            "task": "建立 Agent 产品的数据分析体系，让业务方看到 ROI。",
            "action": "1) 定义 5 个北极星指标：任务完成率、平均交互轮数、用户反馈评分、转人工率、token 成本\n2) 用 LangSmith 做 trace 分析，定位失败模式\n3) 按场景（20 个细分场景）× Agent 版本做埋点和 A/B 比较\n4) 建立每周数据周报 + 每周智能分析\n5) 用数据驱动产品迭代优先级",
            "result": "第 3 个月成功识别 7 个 Agent 失败模式并修复，任务完成率提升 32%。成为公司内部 Agent 产品数据标准。",
            "lessons": "没有数据体系的 Agent 产品 = 没有方向盘的船。PM 应该在上线前就设计好数据方案。",
        },
    ],
    "Phase4": [
        {
            "title": "Agent 成本优化：从 1 次调用 2 元到 0.2 元",
            "situation": "Agent MVP 上线后 token 消耗严重超预期，每个任务平均 2 元 API 成本，CTO 要求降低。",
            "task": "在不显著降低用户体验的前提下，将单次 Agent 任务成本降低 80%。",
            "action": "1) 分析 trace：发现 60% token 消耗在「Agent 自己对话工具选择」的循环推理中\n2) 精简 Agent 规划逻辑：短路径用预设模板（少推理），复杂路径才用 full reasoning\n3) 引入分级模型：简单任务用小模型（qwen-turbo），复杂任务用大模型\n4) 缓存 RAG 检索结果（相似问题命中率 40%）\n5) 设置单次任务 token 上限 + 自动降级策略",
            "result": "2 月内单次成本降至 0.18 元（降幅 91%），用户满意度仅下降 2%。学会：Agent 的 80% 成本在推理阶段。",
            "lessons": "做好成本产品化：给用户不同的成本/质量选择（经济版 vs 旗舰版 Agent）。",
        },
    ],
    "Phase5": [
        {
            "title": "Agent 产品面对隐私合规审查",
            "situation": "Agent 产品需要处理用户个人数据，法务要求做 DPIA（数据保护影响评估），否则不能上线。",
            "task": "协调法务、安全、产品和工程团队，在规定时间内通过合规审查。",
            "action": "1) 梳理 Agent 数据流：输入 → LLM 推理 → 工具调用 → 输出 → 存储\n2) 识别 3 个数据暴露点：RAG 知识库、LLM 上下文、Agent 执行日志\n3) 设计隐私优先方案：对 PII 数据做脱敏 → 推理 → 再映射回原始数据\n4) 制定数据保留策略：执行日志 7 天后自动匿名化\n5) 编写 Agent 产品数据隐私白皮书（法务要求）",
            "result": "2 周内通过 DPIA，Agent 产品按时上线。该方案成为公司 Agent 产品的隐私基线。",
            "lessons": "Agent 产品的隐私设计比传统 SaaS 复杂，因为 Agent 的输入输出可能包含推理过程中产生的间接 PII。",
        },
    ],
    "Phase6": [
        {
            "title": "推动 Agent 平台化：从项目到产品",
            "situation": "公司内部有 5 个团队各自开发 Agent，重复造轮子，维护成本高。",
            "task": "构建 Agent 内部平台（Agent as a Platform），统一能力层。",
            "action": "1) 调研 5 个团队的 Agent 需求，提炼公共能力层（LLM 路由、RAG、工具注册、监控）\n2) 设计平台架构：能力层 + 业务层 + 编排层三层模型\n3) 平台 API 优先，不限制各团队的 Agent 业务逻辑\n4) 建立 Agent 平台文档和最佳实践指南\n5) 用 1 个团队做试点 → 推广到其他团队",
            "result": "新 Agent 开发时间从 3 个月缩短到 2 周，平台层代码复用率 85%。晋升为 Senior PM。",
            "lessons": "做 Agent 产品最值钱的能力是抽象——从具体场景中抽离出可复用的 Agent 模式。",
        },
    ],
    "Phase7": [
        {
            "title": "Agent 产品的定价策略设计",
            "situation": "公司把 Agent 产品作为独立 SKU 对外销售，但不知道怎么定价。",
            "task": "设计 Agent 产品的定价模型，平衡客户价值和公司收入。",
            "action": "1) 竞品分析：OpenAI GPTs（免费+使用权）、CrewAI（开源+企业版）、主要竞品\n2) 客户调研：20 个潜在客户访谈，了解付费意愿和能力\n3) 设计三级定价：基础版（预设 Agent，按调用次数付费）→ 专业版（自定义 Agent，月费）→ 企业版（私有部署，年费）\n4) 引入「Agent 信用分」作为计费单元：一个复杂 Agent 任务 = 3 个信用分\n5) 以 token 成本为下限，客户感知价值为上限定价",
            "result": "首季度 47 个付费客户，MRR $58K。定价模型被 PMF（Product-Market Fit）验证通过。",
            "lessons": "Agent 产品不能用 API Token 定价（客户不懂），要用「价值单元」定价。",
        },
    ],
    "Phase8": [
        {
            "title": "从 0 到 1 带领团队转型 AI Agent",
            "situation": "传统 SaaS 团队被要求转型做 AI Agent 产品，团队成员不懂 LLM，士气低落。",
            "task": "在 6 个月内完成团队能力转型并交付第一个 Agent 产品。",
            "action": "1) 设计「AI PM 学习路径」给团队（自己先学再教）\n2) 每周一次 Agent 动手实验（从调用 GPT API 到搭建多 Agent 系统）\n3) 用设计思维工作坊找到第一个 Agent 场景\n4) 和工程团队建立「Agent 原型→ MVP 的标准化流程」\n5) 成功案例内部宣传，提升团队信心",
            "result": "6 个月后团队交付了第一个 Agent MVP，团队满意度调研提升了 28%。个人获得年度产品创新奖。",
            "lessons": "转型 PM 的核心能力不是技术，而是「快速学习 + 将其翻译成团队能理解的路径」。",
        },
    ],
}


def get_star_story_for_day(day: int, week: int) -> Optional[dict]:
    """根据进度返回当日匹配的 STAR 故事"""
    phase_map = {
        1: "Phase1", 2: "Phase1",
        3: "Phase2", 4: "Phase2",
        5: "Phase3", 6: "Phase3",
        7: "Phase4", 8: "Phase4",
        9: "Phase5", 10: "Phase5",
        11: "Phase6", 12: "Phase6",
        13: "Phase7", 14: "Phase7",
        15: "Phase8", 16: "Phase8",
    }
    # 每 2 天换一个 STAR 故事循环
    phase_key = phase_map.get(week, "通用")
    stories = STAR_STORIES.get(phase_key, STAR_STORIES.get("通用", []))
    if not stories:
        return None
    # 按天轮流选择，确保不重复
    idx = (day - 1) % len(stories)
    return stories[idx]


def build_star_section(star: dict) -> str:
    """将 STAR 故事转为邮件插入片段"""
    if not star:
        return ""
    return f"""
## 📋 面经积累：STAR 故事库

> **{star['title']}**

**S - Situation（背景）**：{star['situation']}

**T - Task（任务）**：{star['task']}

**A - Action（行动）**：
{star['action']}

**R - Result（结果）**：{star['result']}

> 💎 **PM 视角反思**：{star['lessons']}
"""


# ========================= 贯穿项目实操路线 =========================
# 从 0 到 1 构建「企业知识库 Agent」产品，8 周渐进交付
# 每个阶段对应一个里程碑，最终产出可展示的 Portfolio

PRACTICAL_PROJECT = {
    "name": "📦 企业知识库 Agent · 贯穿项目",
    "desc": "从 0 到 1 设计并落地一个面向企业客户的知识库 Agent 产品",
    "deliverable_framework": "每个阶段产出独立交付物，终局是一个完整的 Agent 产品 Portfolio",
    "weeks": {
        1: {
            "phase_name": "项目启动与产品愿景",
            "deliverable": "Project Charter",
            "outline": "定义产品名称、目标用户、核心场景、差异化定位、成功指标",
            "action": "用一页纸写清：①这个 Agent 帮谁解决什么问题 ②为什么不用已有方案 ③怎么判断做成了",
            "example": "例如：帮企业 HR 部门用自然语言查询员工手册、请假政策、培训资料，替代传统 FAQ 搜索",
        },
        2: {
            "phase_name": "技术选型与架构设计",
            "deliverable": "Architecture Decision Record (ADR)",
            "outline": "Agent 框架选型分析（LangGraph vs CrewAI vs AutoGen）、RAG 架构设计、工具注册方案",
            "action": "画一张 Agent 架构图 + 写 300 字选型理由：为什么选 X 不选 Y",
            "example": "选 LangGraph：因为知识库 Agent 需要复杂的状态流转（多轮追问→检索→摘要→确认）",
        },
        3: {
            "phase_name": "用户研究与场景定义",
            "deliverable": "用户故事地图 (User Story Map)",
            "outline": "用户访谈提纲、场景优先级排序（核心场景 vs 长尾场景）、人机分工边界",
            "action": "列出 10 个用户场景 → 按 RICE 打分 → 选出 MVP 的 3 个场景",
            "example": "MVP 场景：①查询政策/制度 ②查询个人档案信息 ③转人工（兜底）",
        },
        4: {
            "phase_name": "PRD 与交互设计",
            "deliverable": "Agent PRD v1",
            "outline": "行为规范（System Prompt 草稿）、交互模式（确认 vs 自动 vs 监督）、错误处理策略、安全边界",
            "action": "写一份完整的 Agent PRD：至少包含行为规范、边界条件、错误处理、评估指标 4 个章节",
            "example": "PRD 关键条款：涉及员工薪资/绩效等敏感数据时，Agent 必须确认用户身份后再查询",
        },
        5: {
            "phase_name": "评估体系与灰度策略",
            "deliverable": "评估方案 + GTM Plan",
            "outline": "5 个北极星指标、自动化评测数据集、灰度发布阶段划分、回滚条件",
            "action": "设计灰度方案：5% → 30% → 100%，每个阶段定义通过条件、回滚条件、数据收集方式",
            "example": "Phase 1（5%）：仅查询类问题 + 必须有转人工兜底 → 通过标准：FCR ≥ 80%",
        },
        6: {
            "phase_name": "行业对标与方案迭代",
            "deliverable": "竞品分析 + 方案优化报告",
            "outline": "对标 3 个真实知识库 Agent 产品（如 Notion AI、Glean、Zendesk AI），识别差距并优化方案",
            "action": "找出自家方案与竞品的 3 个差异点 → 判断是否值得改进 → 更新 PRD 到 v2",
            "example": "Glean 支持跨系统搜索（Slack+Notion+Gmail），自家方案也要考虑多数据源接入",
        },
        7: {
            "phase_name": "商业化与成本模型",
            "deliverable": "商业模式画布 (Business Model Canvas)",
            "outline": "定价策略、成本结构（推理/存储/人力）、收入预测、盈亏平衡分析",
            "action": "算一笔账：假设 1000 个企业用户，每日 3 万次 Agent 调用 → 月成本多少？定价多少？",
            "example": "Token 成本：日均 3 万次 × 500 token/次 × $0.15/1M token = $2.25/天 → 年 $821 → 定价参考",
        },
        8: {
            "phase_name": "作品集打磨与面试展示",
            "deliverable": "Agent Product Portfolio + Pitch Deck",
            "outline": "将所有交付物整合成一份完整的 Portfolio，准备 3 分钟面试 Pitch",
            "action": "写一篇 1000 字的产品案例分析文章 → 准备 3 分钟口头 Pitch → 预演 3 个版本（1min/3min/5min）",
            "example": "Portfolio 结构：项目背景 → 用户调研 → 产品设计 → 技术选型 → 评估体系 → 商业化 → 反思",
        },
    },
}


def get_project_for_week(week: int) -> Optional[dict]:
    """返回指定周的贯穿项目里程碑"""
    return PRACTICAL_PROJECT["weeks"].get(week)


def get_project_progress_bar(week: int) -> str:
    """生成项目进度条（基于总进度）"""
    completed = week - 1
    total = 8
    filled = "▓" * completed
    empty = "░" * (total - completed)
    pct = int(completed / total * 100)
    mile = "🏁" if completed == total else "🚧" if completed > 0 else "🏗️"
    return f"{mile} 项目进度 [{filled}{empty}] {pct}%  (已完成 {completed}/{total} 个里程碑)"


def get_project_summary_context(week: int) -> str:
    """生成贯穿项目的摘要上下文，供 LLM 注入到日常内容中"""
    project = get_project_for_week(week)
    if not project:
        return ""
    prev_week = week - 1
    prev_project = get_project_for_week(prev_week) if prev_week >= 1 else None

    lines = [
        "\n## 📦 贯穿项目实操（本周里程碑）\n",
        f"**项目**: {PRACTICAL_PROJECT['name']}",
        f"**本周目标**: {project['phase_name']}",
        f"**本周交付物**: {project['deliverable']}",
        f"**概要**: {project['outline']}",
        f"**本周行动**: {project['action']}",
    ]

    if prev_project:
        lines.append(f"\n**上周交付物回顾**: {prev_project['deliverable']} — {prev_project['phase_name']}")
        lines.append(f"  上行行动: {prev_project['action']}")

    lines.append(f"\n**参考案例**: {project['example']}")

    lines.append("""
**请在今天的日常内容中，融合一个「项目实操」板块（约 200-300 字）**：
- 位置：放在「今日行动 + 思考题」板块之前
- 内容：结合今天的学习主题，给出本周项目里程碑的具体推进建议
- 格式：用 > 💡 **项目实操** 引用块包裹
- 目的：让学员「学完用得上」，每学一个知识点就立刻应用于项目""")

    return "\n".join(lines)


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
    day_in_week = (day - 2) % 7 + 1 if day > 1 else 7

    phase_name, phase_desc = get_phase(week)
    pct = int(day / total * 100)

    # 本周已学天数
    week_idx = week - 1
    day_idx = (day - 2) % 7
    if day_idx < 0:
        day_idx = 0

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

### 6️⃣ 模拟面试（Mock Interview）
根据本周主题生成 2-3 道模拟面试题，模拟真实 AI PM 面试场景。

题目类型（按周的阶段混搭）：
- **产品设计题（Product Design）**：设计一个特定场景下的 Agent 产品（如"设计一个面向电商的客服 Agent"）
- **策略题（Strategy）**：如何衡量 Agent 产品效果 / 上线决策 / 质量评估策略
- **行为题（STAR）**：用 STAR 法则回答"请分享一个你推动产品决策的案例"
- **技术认知题（Technical Understanding）**：解释 Agent 相关概念或技术选型的理由
- **案例分析题**：给定一个失败案例，要求诊断并给出改进方案

每题格式：
```
【类型】产品设计题
题目：设计一个面向 XX 场景的 Agent 产品。

⏱ 建议思考时间：2-3 分钟

📝 答题框架（PM 视角）：
1. 明确用户场景与痛点
2. 核心功能与优先级
3. 评估指标设计
4. 边界情况与风险
5. 落地路线图

⭐ 评分标准：
- 优秀（8-10分）：场景洞察深入，方案有创新点，考虑到了风险评估
- 良好（5-7分）：结构完整，逻辑清晰，但缺少独特洞察
- 需提升（1-4分）：思路跳跃，缺少系统性分析

💡 PM 面试官关注点：
分析该问题从面试官视角考察什么

📖 参考回答：
300-400 字的完整范例回答，含具体架构/数据指标/落地细节
```

## 风格要求
- 难度适中：覆盖基础概念 + 1-2 道进阶题
- 鼓励思考：不要只给答案，要有「为什么」
- 模拟面试题的答案要体现 PM 思维：用户导向、数据驱动、优先级取舍
- 关键术语标注英文原文（如 检索增强生成 Retrieval-Augmented Generation, RAG）
- 长度：2500-3500 字（含模拟面试板块）

### 7️⃣ 英文核心术语（English Key Terms）
在内容末尾添加 3-5 个本周核心术语的中英对照表格：

| 中文术语 | English Term | 一句话解释 |
|----------|-------------|-----------|
| 示例 | RAG | A technique to enhance LLM with external knowledge retrieval |
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

### 7️⃣ 英文核心术语（English Key Terms）
在内容末尾添加 3-5 个本周核心术语的中英对照表格：

| 中文术语 | English Term | 一句话解释 |
|----------|-------------|-----------|
| 示例 | RAG | A technique to enhance LLM with external knowledge retrieval |

### 8️⃣ English Weekly Summary
用 3-5 句英文总结本周核心学习成果，放在 Key Terms 之后。帮助建立英文思维和简历话术。
格式：bullet points，每句包含一个本周关键技术/方法/工具的英文术语。
"""

# ========================= DeepSeek API 调用 =========================

def call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 7000) -> str:
    """调用 DeepSeek Chat API（含指数退避重试），失败后自动 fallback 到本地 Ollama"""
    import time

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

    last_error = ""
    for attempt in range(1, 4):  # 最多重试 3 次
        try:
            with urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except (URLError, IncompleteRead) as e:
            err_type = type(e).__name__
            last_error = f"DeepSeek API 调用失败 — {err_type} (尝试 {attempt}/3): {e}"
            print(last_error)
            if attempt < 3:
                wait = 2 ** attempt * 5  # 10s → 20s → 40s
                print(f"  等待 {wait}s 后重试...")
                time.sleep(wait)
        except (KeyError, json.JSONDecodeError) as e:
            last_error = f"DeepSeek API 返回解析失败 (尝试 {attempt}/3): {e}"
            print(last_error)
            if attempt < 3:
                time.sleep(10)

    # —— 全部重试失败，fallback 到本地 Ollama ——
    print(f"⚠️ DeepSeek 全部重试失败，尝试本地 Ollama fallback...")
    fallback = _call_ollama(system_prompt, user_prompt, max_tokens)
    if fallback:
        return fallback

    return f"<p style='color:red'>DeepSeek + Ollama fallback 均失败: {last_error}</p>"


def _call_ollama(system_prompt: str, user_prompt: str, max_tokens: int = 7000) -> Optional[str]:
    """调用本地 Ollama 作为备用（qwen3:32b）"""
    import urllib.request

    ollama_url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.7,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("message", {}).get("content", "")
            if content:
                print(f"✅ Ollama fallback ({OLLAMA_MODEL}) 成功")
                return content
        print(f"⚠️ Ollama 返回为空")
        return None
    except Exception as e:
        print(f"❌ Ollama fallback 失败: {e}")
        return None


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

### 6️⃣ English Executive Summary（英文核心摘要）
在内容末尾添加 3-5 句英文摘要，用 bullet points 总结今天学到的核心知识点。
这是给双语学习者准备的快速回顾，帮助建立英文术语记忆。

格式：
```
📌 Executive Summary (English)

- [Key takeaway 1 in English — include the core technical term]
- [Key takeaway 2 in English]
- [Key takeaway 3 in English]

Key terms: [term1 / term2 / term3] — learn them in both languages.
```

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
        # === 🎯 周日：周末小测验 + 模拟面试 ===
        phase_name, phase_desc = get_phase(week)
        user_prompt = f"""## 学员当前位置

第 {week} 周 · 主题：{theme}
阶段：{phase_name} — {phase_desc}

## 本周每日主题

以下为本周 7 天的学习主题，请基于这些内容生成一套小测验和模拟面试题：
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

        # 贯穿项目上下文（让模拟面试题融入项目背景）
        project = get_project_for_week(week)
        if project:
            user_prompt += f"""

## 贯穿项目（Prcatical Project）
项目名称：{PRACTICAL_PROJECT["name"]}
本周阶段：{project["phase_name"]}
本周交付物：{project["deliverable"]}
项目描述：{project.get("summary", PRACTICAL_PROJECT.get("summary", ""))[:500]}
"""

        user_prompt += f"""

## 模拟面试题生成指引

根据学员当前阶段（{phase_name}）和本周主题，生成合适的模拟面试题：

- Phase 1（认知构建周1-2）：侧重基础概念理解 + 产品直觉题 → 题目偏"解释概念/对比选型/场景判断"
- Phase 2（产品实战周3-5）：侧重产品设计 + 策略题 → "设计一个Agent产品/如何做A/B测试/评估指标体系"
- Phase 3（面试准备周6-8）：侧重真实面试场景 → 综合行为/系统设计/案例诊断，接近大厂真实面经

请根据以上指引在「模拟面试（Mock Interview）」板块中生成 2-3 道匹配当前阶段的题目。
"""

        llm_content = call_deepseek(QUIZ_SYSTEM_PROMPT, user_prompt, max_tokens=7000)
        return llm_content

    # === 📖 日常学习模式（带间隔复习 + 项目实操） ===
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

    # 获取贯穿项目上下文
    project_ctx = get_project_summary_context(week)

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

{project_ctx}

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

    # 贯穿项目信息（用于日常模式）
    project = get_project_for_week(week)
    project_progress_bar = get_project_progress_bar(week)

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

{'''<tr><td style="background:#e8f5e9; border-left:6px solid #4caf50; padding:12px 40px;">
<table width="100%"><tr>
<td style="font-size:14px; color:#2e7d32;">
<strong>📊 每周进度周报</strong> — 回顾本周学习成果，规划下周方向
</td>
<td style="text-align:right; font-size:12px; color:#2e7d32;">
第 {week}/8 周 · Day {day}/{total}
</td>
</tr></table>
</td></tr>''' if day_type == 'weekly_review' else '''<tr><td style="background:#fff3cd; border-left:6px solid #ffc107; padding:12px 40px;">
<table width="100%"><tr>
<td style="font-size:14px; color:#856404;">
<strong>🎯 周末小测验</strong> — 用 5 道题检验本周学习成果
</td>
<td style="text-align:right; font-size:12px; color:#856404;">
正确率 × 思考过程 &gt; 答案本身
</td>
</tr></table>
</td></tr>''' if day_type == 'quiz' else ''}

<!-- Mock Interview Banner (only for quiz mode) -->
{'''<tr><td style="background:#f3e5f5; border-left:6px solid #9c27b0; padding:12px 40px;">
<table width="100%"><tr>
<td style="font-size:14px; color:#6a1b9a;">
<strong>🎤 模拟面试</strong> — 每周 2-3 道真题，练习 PM 思维，对标大厂标准
</td>
<td style="text-align:right; font-size:12px; color:#6a1b9a;">
自测后看参考回答 >
</td>
</tr></table>
</td></tr>''' if day_type == 'quiz' else ''}

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
{("" + interview_section + "") if interview_section else ""}

<!-- Practical Project Section (日常模式显示) -->
{('''
<tr><td style="padding:8px 40px 16px 40px;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0faf0; border:1px solid #c8e6c9; border-radius:8px;">
<tr>
<td style="padding:14px 18px;">
<p style="font-size:14px; color:#2e7d32; font-weight:bold; margin:0 0 6px 0;">
📦 ''' + PRACTICAL_PROJECT["name"] + '''</p>
<p style="font-size:12px; color:#558b2f; margin:0 0 8px 0;">
本周里程碑: ''' + (project["phase_name"] if project else "—") + ''' · 交付物: ''' + (project["deliverable"] if project else "—") + '''</p>
<p style="font-size:12px; color:#666; margin:0 0 4px 0;">''' + (project_progress_bar if project else "") + '''</p>
</td>
</tr>
</table>
</td></tr>
''') if day_type == "daily" and project else ""}

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

    # Markdown tables (英语关键术语表等)
    table_pattern = re.compile(
        r'^\|(.+)\|\s*$\n^\|[-| :]+\|\s*$\n((?:^\|.+\|\s*$\n?)+)',
        re.MULTILINE
    )
    def convert_table(match):
        header_row = match.group(1)
        body = match.group(2)
        cells = [c.strip() for c in header_row.split('|') if c.strip()]
        header_html = ''.join(
            f'<th style="background:#667eea; color:white; padding:8px 12px; text-align:left; font-size:13px; border:1px solid #ddd;">{c}</th>'
            for c in cells
        )
        thead = f'<thead><tr>{header_html}</tr></thead>'

        rows_html = ''
        for line in body.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('|--'):
                continue
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                row_cells = ''.join(
                    f'<td style="padding:6px 12px; font-size:13px; border:1px solid #ddd;">{c}</td>'
                    for c in cells
                )
                rows_html += f'<tr>{row_cells}</tr>\n'

        return (
            '<table style="border-collapse:collapse; width:100%; margin:12px 0; '
            'font-size:14px; border:1px solid #ddd;">\n'
            f'{thead}\n'
            f'<tbody>\n{rows_html}</tbody>\n'
            '</table>'
        )
    html = table_pattern.sub(convert_table, html)

    # Paragraphs: wrap non-tag lines in <p>
    lines = html.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(('<h', '<li', '<ul', '<ol', '<pre', '<blockquote', '<hr', '<div', '<table', '<thea', '<tbod', '<tr', '<td', '<th', '</tab')):
            result.append(f'<p style="margin:8px 0;">{stripped}</p>')
        else:
            result.append(line)
    html = '\n'.join(result)

    return html


# ========================= 语音版推送（TTS）=========================

def generate_tts_audio(content: str, progress: dict) -> Optional[str]:
    """从学习内容中提取摘要并生成语音版 MP3（macOS say + ffmpeg）"""
    import re, os, subprocess, tempfile

    today_str = progress["today"].strftime("%Y-%m-%d")
    week = progress["week_number"]
    topic = progress["day_topic"]

    # 1. 提取关键语句：标题 + 列表项 + 首段文字
    lines = content.split("\n")
    script_lines = []
    seen = set()

    for line in lines:
        stripped = line.strip()
        # 跳过空行、代码块、水平线
        if not stripped or stripped.startswith(("```", "---", ">")):
            continue
        # 标题 → 直接读
        if stripped.startswith("#"):
            script_lines.append(stripped.lstrip("#").strip())
            continue
        # 列表项 → 提取内容
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            # 去粗体标记
            item = re.sub(r"\*\*", "", item)
            if item and item not in seen and len(item) < 200:
                seen.add(item)
                script_lines.append(item)
                continue
        # 非空非标记段落的首句（第一段非空连续文本）
        if not stripped.startswith(("<", "[", "|", "`", "!")):
            # 取每段前 1-2 句
            clean = re.sub(r"\*\*", "", stripped)
            if len(clean) > 20 and clean not in seen:
                # 取第一个句号/问号前的部分（第 1 句）
                sentences = re.split(r"[。！？\n]", clean)
                first = sentences[0].strip()
                if first and len(first) > 20 and first not in seen:
                    seen.add(first)
                    script_lines.append(first)

    # 2. 组合成朗读稿（控制在 1500 字符内 = 约 2-3 分钟）
    script = f"早上好！今天是{today_str}，第{week}周的学习主题是：「{topic}」。\n\n"
    char_count = len(script)
    for s in script_lines:
        if char_count + len(s) + 1 > 1500:
            break
        script += s + "。\n"
        char_count += len(s) + 1

    script += "\n以上就是今天的精华内容，祝你学习愉快！"

    # 3. 用 say 生成 AIFF
    os.makedirs("/Users/liuwei/voice-memos", exist_ok=True)
    aiff_path = f"/Users/liuwei/voice-memos/pm_tts_{today_str}.aiff"
    mp3_path = f"/Users/liuwei/voice-memos/pm_tts_{today_str}.mp3"

    try:
        subprocess.run(
            ["say", "-v", "Tingting", "-o", aiff_path, script],
            check=True, capture_output=True, text=True, timeout=60,
        )
        if os.path.getsize(aiff_path) < 1000:
            print(f"⚠️ TTS 生成文件过小: {os.path.getsize(aiff_path)} 字节，跳过")
            return None
    except subprocess.TimeoutExpired:
        print("⚠️ TTS 超时，跳过语音版")
        return None
    except subprocess.CalledProcessError as e:
        print(f"⚠️ TTS 失败: {e.stderr[:200]}")
        return None

    # 4. 转 MP3
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", aiff_path, "-codec:a", "libmp3lame",
             "-q:a", "4", mp3_path],
            check=True, capture_output=True, text=True, timeout=30,
        )
        size_kb = os.path.getsize(mp3_path) // 1024
        print(f"🎧 语音版已生成: {mp3_path} ({size_kb}KB)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg 不可用时直接用 AIFF
        mp3_path = aiff_path
        size_kb = os.path.getsize(mp3_path) // 1024
        print(f"🎧 语音版已生成（未转码）: {mp3_path} ({size_kb}KB)")

    # 清理 AIFF（如果已转码成功）
    if mp3_path != aiff_path:
        try:
            os.unlink(aiff_path)
        except OSError:
            pass

    return mp3_path


def send_email(html_content: str, subject: str, max_retries: int = 3,
               attachment_path: Optional[str] = None):
    """发送邮件到所有目标邮箱（带重试+本地备份兜底）"""
    import time, os

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
                    msg = MIMEMultipart("mixed" if attachment_path else "alternative")
                    msg["From"] = formataddr(("AI Agent PM Learning", SMTP_CONFIG["user"]))
                    msg["To"] = to_email
                    msg["Subject"] = Header(subject, "utf-8")
                    msg["Message-ID"] = (
                        f"<pm-plan-{date.today().isoformat()}"
                        f"-{abs(hash(to_email)) % 10000}@hermes>"
                    )
                    # HTML 正文
                    msg.attach(MIMEText(html_content, "html", "utf-8"))
                    # 语音附件
                    if attachment_path and os.path.exists(attachment_path):
                        with open(attachment_path, "rb") as af:
                            att = MIMEBase("audio", "mpeg", filename=os.path.basename(attachment_path))
                            att.set_payload(af.read())
                            encoders.encode_base64(att)
                            att.add_header(
                                "Content-Disposition",
                                "attachment",
                                filename=os.path.basename(attachment_path),
                            )
                            att.add_header("Content-ID", "<tts-audio>")
                            msg.attach(att)
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
    backup_dir = "/Users/liuwei/.hermes/email_backups"
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

    # 映射：Mon→1, Tue→2, ..., Sat→6(周报), Sun→7(测验)
    day_in_week = (day - 2) % 7 + 1
    # 周内索引（用于 WEEKS["days"] 数组，0=Mon, 5=Sat, 6=Sun）
    week_idx = week_number - 1
    day_topic_idx = (day - 2) % 7
    if day_topic_idx < 0:
        day_topic_idx = 6  # 计划第一天(周日)用 "本周总结" topic

    week_info = WEEKS[week_idx]
    day_topic = week_info["days"][day_topic_idx] if day_topic_idx < len(week_info["days"]) else week_info["days"][-1]

    # 计算前 1/3/7 天的 topic 用于回顾
    review_days = {}
    for offset in [1, 3, 7]:
        prev_day = day - offset
        if prev_day >= 1:
            prev_week_num = (prev_day - 1) // 7
            # 用新索引方案定位 topic
            prev_topic_idx = (prev_day - 2) % 7
            if prev_topic_idx < 0:
                prev_topic_idx = 6
            if prev_week_num < len(WEEKS):
                prev_week = WEEKS[prev_week_num]
                if prev_topic_idx < len(prev_week["days"]):
                    review_days[offset] = {
                        "day": prev_day,
                        "topic": prev_week["days"][prev_topic_idx],
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
    """将当日学习内容归档到 Obsidian — 完整笔记存学习计划目录，对话归档只留引用"""
    import subprocess
    import tempfile
    import os

    vault = "/Users/liuwei/Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
    today_str = progress["today"].strftime("%Y-%m-%d")
    week = progress["week_number"]
    day = progress["day"]
    topic = progress["day_topic"]
    phase_name, phase_desc = get_phase(week)

    # ====== 1. 写完整笔记到 学习计划/AI Agent PM 每日学习/ ======
    pm_dir = os.path.join(vault, "学习计划", "AI Agent PM 每日学习")
    os.makedirs(pm_dir, exist_ok=True)

    safe_topic = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic[:40])
    filename = f"Day{day:02d}_Week{week}_{today_str}_{safe_topic.strip()}.md"
    filepath = os.path.join(pm_dir, filename)

    full_note = f"""---
tags: [AI-Agent-PM, 学习计划, Phase{week}]
week: {week}
day: {day}
date: {today_str}
topic: "{topic}"
---

# {phase_name} · 第 {week}/8 周 · 第 {day}/{progress['total_days']} 天

> **日期**: {today_str}
> **主题**: {topic}

---

{content}

---

*生成时间: {today_str} | 计划: {PLAN_START} → {PLAN_END}*
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_note)
    print(f"📝 已写入 Obsidian 学习笔记 → {filepath}")

    # ====== 2. 往今日对话归档追加短引用（含 Obsidian wikilink） ======
    ref_text = f"""### 🎯 AI Agent PM 学习笔记 - Day{day} 第{week}周

**主题**: {topic[:80]}
**完整笔记**: [[学习计划/AI Agent PM 每日学习/{filename}|📖 打开]]

"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(ref_text)
        tmp_path = f.name

    tags = "AI-Agent-PM,学习计划,笔记"   # 注意：无空格，Obsidian 标签安全
    title = f"[AI Agent PM] Day{day} 第{week}周 · {topic[:50]}"

    try:
        obsidian_script = "/Users/liuwei/.hermes/scripts/hermes-obsidian.sh"
        if not os.path.exists(obsidian_script):
            obsidian_script = "/Users/liuwei/.hermes/scripts/hermes-obsidian.sh"
        result = subprocess.run(
            ["bash", obsidian_script, "add", title, tags, tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print(f"✅ 引用已追加到今日对话归档")
        else:
            print(f"⚠️ 对话归档失败: {result.stderr[:200]}")
    except Exception as e:
        print(f"⚠️ 对话归档异常: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ========================= 本地 Markdown 缓存 =========================


def save_local_markdown(content: str, progress: dict):
    """将当日学习内容保存为本地 Markdown 文件"""
    import os

    today_str = progress["today"].strftime("%Y-%m-%d")
    week = progress["week_number"]
    day = progress["day"]
    topic = progress["day_topic"]
    phase_name, phase_desc = get_phase(week)

    # 确保目录存在
    cache_dir = "/Users/liuwei/.hermes/learning-plans"
    os.makedirs(cache_dir, exist_ok=True)

    # 文件名：Day{day:02d}_Week{week}_{date}_{topic[:40]}.md
    safe_topic = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic[:40])
    filename = f"Day{day:02d}_Week{week}_{today_str}_{safe_topic.strip()}.md"
    filepath = os.path.join(cache_dir, filename)

    md_content = f"""# {phase_name} · 第 {week}/8 周 · 第 {day}/{progress['total_days']} 天

> **日期**: {today_str}
> **主题**: {topic}

---

{content}

---

*生成时间: {today_str} | 计划: {PLAN_START} → {PLAN_END}*
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"📄 已缓存本地 Markdown → {filepath}")
    return filepath


# ========================= 主流程 =========================

def main(dry_run: bool = False):
    today = date.today()
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

    if dry_run:
        print(f"🔍 DRY RUN 模式 — 仅生成内容，不发邮件、不缓存、不归档\n")

    # 1. 用 DeepSeek 生成内容
    print(f"🤖 正在调用{DEEPSEEK_MODEL} 生成{mode_label}（增强版 v3）...")
    content = generate_daily_content(progress)
    print(f"✅ 内容生成完成（{len(content)} 字符）")

    # 2. 质量门禁（仅日常内容）
    if day_type == "daily":
        content = validate_content(content, progress)

    # 2.5 STAR 故事积累（仅日常内容）
    if day_type == "daily":
        star = get_star_story_for_day(day, week)
        star_section = build_star_section(star)
        if star_section:
            content += star_section
            print(f"💼 已追加 STAR 故事：{star['title']}")

    # 3.5 语音版推送（仅日常模式）
    audio_path = None
    if day_type == "daily" and not dry_run:
        print("🎙️ 正在生成语音版摘要...")
        audio_path = generate_tts_audio(content, progress)

    # —— DRY RUN 直接退出（不发邮件、不缓存、不归档）——
    if dry_run:
        html = build_email_html(progress, content, day_type=day_type)
        day_labels = {"daily": f"Day{progress['day_in_week']}", "weekly_review": "周报", "quiz": "Quiz"}
        subject = f"[AI Agent PM] {phase_name} 第{week}周 {day_labels.get(day_type, '')} · {topic[:40]}"
        print(f"\n{'='*60}")
        print(f"📋 [DRY RUN] 即将发送的邮件摘要")
        print(f"   收件人: {', '.join(TO_EMAILS)}")
        print(f"   主题: {subject}")
        print(f"   内容长度: {len(content)} 字符 / 音频: {'跳过(DRY)' if day_type == 'daily' else '无'}")
        print(f"   关键词检查: {'跳过(非日常)' if day_type != 'daily' else '通过'}")
        print(f"{'='*60}")
        return

    # 4. 发送邮件（含语音附件）
    html = build_email_html(progress, content, day_type=day_type)
    day_labels = {"daily": f"Day{progress['day_in_week']}", "weekly_review": "周报", "quiz": "Quiz"}
    subject = f"[AI Agent PM] {phase_name} 第{week}周 {day_labels.get(day_type, '')} · {topic[:40]}"
    print(f"📧 正在发送邮件{'（含语音附件）' if audio_path else '...'}")
    send_email(html, subject, attachment_path=audio_path)

    # 4.5 缓存本地 Markdown
    print("📄 正在缓存到本地...")
    save_local_markdown(content, progress)

    # 5. 归档到 Obsidian
    print("📝 正在归档到 Obsidian...")
    archive_to_obsidian(content, progress)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent PM 学习计划每日推送")
    parser.add_argument("--dry-run", action="store_true", help="仅生成内容，不发邮件/不缓存/不归档")
    parser.add_argument("--model", help="临时覆盖 DeepSeek 模型名（如 deepseek-chat）")
    args = parser.parse_args()

    if args.model:
        globals()["DEEPSEEK_MODEL"] = args.model
        print(f"🔧 临时覆盖模型 → {args.model}")

    main(dry_run=args.dry_run)
