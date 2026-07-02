"""Unified intent routing for the football assistant.

This layer decides which assistant capability should handle a message.  It is
not allowed to execute tools or bypass permissions; execution still happens in
the existing module handlers and the academic executor.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.campus_agent.github_tools import should_use_github
from app.services.campus_agent.intent_v2 import route_mode_v2
from app.services.campus_agent.data_analysis_tools import should_use_data_analysis
from app.services.campus_agent.learning_tools import should_use_learning
from app.services.campus_agent.llm_client import call_deepseek
from app.services.campus_agent.topic_qa_tools import should_use_ai_knowledge, should_use_worldcup
from app.services.campus_agent.memory import recent_tool_context
from app.services.campus_agent.web_search_tools import should_use_web_search

logger = logging.getLogger("app")


ROUTABLE_MODES = {
    "academic_ops",
    "github",
    "search",
    "code_review",
    "document",
    "emotion",
    "study",
    "map",
    "rag",
    "data_analysis",
    "worldcup",
    "ai_knowledge",
}

ACADEMIC_WORDS = [
    "学生",
    "同学",
    "学号",
    "教师",
    "老师",
    "教职工",
    "工号",
    "课程",
    "成绩",
    "课表",
    "考勤",
    "请假",
    "班级",
    "院系",
    "学院",
    "教室",
    "学期",
    "公告",
    "通知",
    "岗位",
    "职称",
    "邮件",
    "发信",
    "写信",
    "我是谁",
    "我的信息",
    "我的资料",
    "我的个人资料",
    "我的身份",
    "我的账号",
    "我的成绩",
    "我的分数",
    "我的老师",
    "我的班主任",
    "我的辅导员",
    "我的课程",
]

CONTINUATION_WORDS = [
    "继续",
    "下一页",
    "下页",
    "显示更多",
    "更多",
    "全部显示",
    "显示全部",
    "都显示",
    "完整显示",
    "显示所有",
    "能显示全部",
    "可以显示全部",
]

DOCUMENT_WORDS = ["翻译", "英译中", "中译英", "总结", "概括", "提取重点", "OCR", "图片文字", "识别图片", "提取图片"]
EMOTION_WORDS = ["压力", "焦虑", "难受", "崩溃", "绝望", "撑不住", "不想活", "轻生", "想死", "抑郁", "心情不好", "心理", "心理建议", "更专业"]
MAP_WORDS = ["路线", "线路", "怎么走", "怎么去", "途经", "经过", "中途", "中间地", "附近", "周边", "餐厅", "咖啡", "景点", "商场", "吃喝玩乐"]
CODE_WORDS = [
    "分析项目", "项目分析", "代码体检", "分析代码", "代码分析", "项目结构", "模块关系", "接口调用链", "表关系",
    "权限风险", "代码风险", "优化方向", "代码整改", "代码审查", "代码评审", "架构分析", "项目架构",
    "编程", "写代码", "生成代码", "解释代码", "这段代码", "报错", "debug", "bug", "单元测试",
    "接口怎么写", "组件怎么写", "代码在哪", "哪个文件", "文件位置",
]
SEARCH_PUBLIC_WORDS = ["世界杯", "欧洲杯", "欧冠", "NBA", "新闻", "热搜", "股价", "股票", "汇率", "政策", "版本", "最新消息"]


@dataclass
class IntentRoute:
    mode: str | None = None
    intent: str = "unmatched"
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    reason: str = ""
    source: str = "none"

    @property
    def is_valid(self) -> bool:
        return bool(self.mode in ROUTABLE_MODES and self.confidence >= 0.45)


def route_intent(message: str, *, conversation=None, memory_context: Any | None = None, allow_llm: bool = True) -> IntentRoute:
    """Route a user message to a capability mode.

    The deterministic pass handles high-confidence cases and common regressions.
    The LLM pass is optional and only returns a mode, intent and lightweight
    slots; it cannot select arbitrary tools or execute anything.
    """
    text = (message or "").strip()
    if not text:
        return IntentRoute(reason="empty")

    deterministic = _deterministic_route(text, conversation=conversation, memory_context=memory_context)
    if deterministic.is_valid and deterministic.confidence >= 0.78:
        return deterministic

    if allow_llm:
        llm_route = _llm_route(text, conversation=conversation, memory_context=memory_context, fallback=deterministic)
        if llm_route.is_valid and llm_route.confidence >= max(0.55, deterministic.confidence):
            return llm_route

    return deterministic


def route_mode(message: str, *, conversation=None, memory_context: Any | None = None, allow_llm: bool = True) -> str | None:
    route = route_intent(message, conversation=conversation, memory_context=memory_context, allow_llm=allow_llm)
    return route.mode if route.is_valid else None


def should_override_current_mode(current_mode: str, route: IntentRoute) -> bool:
    """Decide whether an explicit new intent may escape the selected mode."""
    if not route.is_valid:
        return False
    if current_mode in {"auto", route.mode}:
        return False
    if current_mode in {"academic_tools", "academic_ops"}:
        return route.mode in {"github", "search", "code_review", "document", "emotion", "study", "map", "rag", "data_analysis", "worldcup", "ai_knowledge"} and route.confidence >= 0.78 and route.source == "deterministic"
    if current_mode == "emotion" and route.mode == "academic_ops":
        return False
    if current_mode in {"rag", "search", "code_review", "document", "emotion", "study", "map", "life", "github", "data_analysis", "worldcup", "ai_knowledge"}:
        # Manual non-academic modes should remain sticky unless the new message
        # contains a very explicit cross-module signal.
        return route.source == "deterministic" and route.confidence >= 0.86
    return route.confidence >= 0.72


def _deterministic_route(text: str, *, conversation=None, memory_context: Any | None = None) -> IntentRoute:
    if re.fullmatch(r"#?\d+", text) or re.search(r"(确认|执行|同意|取消|放弃)\s*(?:动作|操作|ID|id)?\s*#?\d*", text):
        return IntentRoute(mode="academic_ops", intent="confirm_or_cancel", confidence=0.95, reason="confirmation", source="deterministic")

    if should_use_data_analysis(text):
        return IntentRoute(mode="data_analysis", intent="data_analysis", confidence=0.9, reason="data_analysis_signal", source="deterministic")

    v2_mode = route_mode_v2(text)
    if v2_mode == "academic_ops":
        return IntentRoute(mode="academic_ops", intent="academic_query", confidence=0.92, slots={"_raw_message": text}, reason="intent_v2_academic", source="deterministic")
    if v2_mode in ROUTABLE_MODES:
        return IntentRoute(mode=v2_mode, intent=f"{v2_mode}_task", confidence=0.9, slots={"_raw_message": text}, reason=f"intent_v2_{v2_mode}", source="deterministic")

    if _looks_like_emotion(text):
        return IntentRoute(mode="emotion", intent="emotion_companion", confidence=0.9, reason="emotion_signal", source="deterministic")
    if _has_academic_signal(text):
        if any(word in text for word in CONTINUATION_WORDS) or _looks_like_academic_mutation(text):
            return IntentRoute(mode="academic_ops", intent="academic_operation", confidence=0.9, reason="academic_signal", source="deterministic")
        if any(word in text for word in ["查", "查询", "搜索", "找", "看", "列出", "显示", "多少", "什么", "所有", "全部"]):
            return IntentRoute(mode="academic_ops", intent="academic_query", confidence=0.88, reason="academic_query_signal", source="deterministic")
        return IntentRoute(mode="academic_ops", intent="academic_query", confidence=0.82, reason="academic_signal", source="deterministic")

    if any(word in text for word in CONTINUATION_WORDS):
        if _recent_query_context(conversation, memory_context):
            return IntentRoute(mode="academic_ops", intent="continue_previous_query", confidence=0.86, reason="query_followup", source="deterministic")
        return IntentRoute(mode="academic_ops", intent="continue_previous", confidence=0.65, reason="continuation", source="deterministic")

    if should_use_github(text):
        return IntentRoute(mode="github", intent="github_task", confidence=0.9, reason="github_signal", source="deterministic")
    if recent_tool_context(conversation, {"code_analysis"}) and any(
        word in text for word in ["继续", "这个项目", "这个文件", "风险", "优化", "模块", "接口", "表关系", "架构", "技术栈", "优缺点", "整改"]
    ):
        return IntentRoute(mode="code_review", intent="code_analysis_followup", confidence=0.86, reason="code_followup", source="deterministic")
    if _looks_like_code_analysis(text):
        return IntentRoute(mode="code_review", intent="code_analysis", confidence=0.88, reason="code_signal", source="deterministic")
    if _looks_like_document_task(text):
        return IntentRoute(mode="document", intent="document_process", confidence=0.86, reason="document_signal", source="deterministic")
    if _looks_like_map(text):
        return IntentRoute(mode="map", intent="map_task", confidence=0.88, reason="map_signal", source="deterministic")
    if should_use_worldcup(text):
        return IntentRoute(mode="worldcup", intent="worldcup_qa", confidence=0.84, reason="worldcup_signal", source="deterministic")
    if should_use_ai_knowledge(text):
        return IntentRoute(mode="ai_knowledge", intent="ai_knowledge_qa", confidence=0.84, reason="ai_knowledge_signal", source="deterministic")
    if should_use_learning(text):
        return IntentRoute(mode="study", intent="learning", confidence=0.84, reason="learning_signal", source="deterministic")
    if should_use_web_search(text) and not _has_academic_signal(text):
        return IntentRoute(mode="search", intent="web_search", confidence=0.82, reason="search_signal", source="deterministic")
    if _looks_like_public_search(text):
        return IntentRoute(mode="search", intent="web_search", confidence=0.7, reason="public_search_topic", source="deterministic")
    return IntentRoute(reason="no_deterministic_route", source="deterministic")


def _has_academic_signal(text: str) -> bool:
    if re.search(r"[Ss]\d{6,}|[Tt]\d{6,}", text):
        return True
    return any(word in text for word in ACADEMIC_WORDS)


def _looks_like_academic_mutation(text: str) -> bool:
    return any(word in text for word in ["新增", "添加", "创建", "录入", "新建", "发布", "修改", "更新", "调整", "改为", "改成", "设置", "删除", "停用", "禁用", "移除", "发邮件", "发一份邮件"])


def _looks_like_code_analysis(text: str) -> bool:
    if any(word in text for word in CODE_WORDS):
        return True
    return bool(re.search(r"[A-Za-z]:\\[^？?，,\s]+", text)) and any(word in text for word in ["分析", "体检", "看看", "审查"])


def _looks_like_document_task(text: str) -> bool:
    return any(word in text for word in DOCUMENT_WORDS)


def _looks_like_emotion(text: str) -> bool:
    return any(word in text for word in EMOTION_WORDS)


def _looks_like_map(text: str) -> bool:
    if any(word in text for word in MAP_WORDS):
        return True
    return bool(re.search(r"从.+?到.+?(?:再到|然后到|再去|然后去)?.+", text)) and len(text) <= 120


def _looks_like_public_search(text: str) -> bool:
    if _has_academic_signal(text) or _looks_like_map(text) or should_use_learning(text):
        return False
    return any(word in text for word in SEARCH_PUBLIC_WORDS)


def _recent_query_context(conversation, memory_context: Any | None) -> dict | None:
    if memory_context:
        context = getattr(memory_context, "recent_query_tool", None) or getattr(memory_context, "last_tool", None)
        if context and str(context.get("tool_code") or "").startswith("query_"):
            return context
    return recent_tool_context(conversation, None)


def _llm_route(text: str, *, conversation=None, memory_context: Any | None = None, fallback: IntentRoute | None = None) -> IntentRoute:
    prompt = (
        "你是校园足球助手的统一意图路由器。你的任务只是在多个能力模块中选择入口，不执行任何操作。\n"
        "必须只输出 JSON，不要输出解释或 Markdown。\n"
        "可选 mode 只能是：academic_ops, github, search, code_review, document, emotion, study, map, rag, data_analysis, worldcup, ai_knowledge。\n"
        "判断原则：\n"
        "1. 查询/新增/修改/删除学生、教师、课程、班级、院系、教室、学期、成绩、课表、考勤、请假、公告、邮件，选 academic_ops。\n"
        "2. 课程知识讲解、学习计划、题目解析、诗词鉴赏，选 study。\n"
        "3. 真实世界最新信息、搜索引擎式问题、新闻、体育数据、价格政策，选 search。\n"
        "4. GitHub 仓库、issue、PR、repo，选 github。\n"
        "5. 路线规划、附近地点、吃喝玩乐，选 map。\n"
        "6. 编程助手、项目体检、项目代码分析、架构审查，选 code_review。\n"
        "7. 文件总结、翻译、OCR、图片文字提取，选 document。\n"
        "8. 情绪、心理压力、陪伴、危机表达，选 emotion。\n"
        "9. 数据体检、成绩趋势、考勤/请假统计、异常分析，选 data_analysis。\n"
        "10. 世界杯专题知识、赛制、球星、射手榜，选 worldcup。\n"
        "11. LangChain、LangGraph、FastAPI、Dify、Python、Linux、SQL 等技术知识，选 ai_knowledge。\n"
        "12. 不确定时 confidence 低于 0.45。\n"
        "输出格式：{\"mode\": string|null, \"intent\": string, \"confidence\": number, \"slots\": object, \"missing\": array, \"reason\": string}。"
    )
    payload = {
        "message": text,
        "fallback": fallback.__dict__ if fallback else None,
        "memory_context": _compact_memory(memory_context),
        "recent_conversation": _recent_conversation(conversation),
    }
    raw = call_deepseek(
        system_prompt=prompt,
        user_message=json.dumps(payload, ensure_ascii=False, default=str),
        temperature=0,
        max_tokens=450,
    )
    data = _json_loads(raw)
    if not data:
        return IntentRoute(reason="llm_unavailable", source="llm")
    mode = data.get("mode")
    try:
        confidence = float(data.get("confidence") or 0)
    except Exception:
        confidence = 0.0
    if mode not in ROUTABLE_MODES:
        mode = None
    return IntentRoute(
        mode=mode,
        intent=str(data.get("intent") or mode or "unmatched"),
        confidence=max(0.0, min(1.0, confidence)),
        slots=data.get("slots") if isinstance(data.get("slots"), dict) else {},
        missing=data.get("missing") if isinstance(data.get("missing"), list) else [],
        reason=str(data.get("reason") or "llm_route"),
        source="llm",
    )


def _json_loads(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, flags=re.I).strip()
        value = re.sub(r"```$", "", value).strip()
    first = value.find("{")
    last = value.rfind("}")
    if first >= 0 and last >= first:
        value = value[first : last + 1]
    try:
        data = json.loads(value)
    except Exception:
        logger.warning("Campus agent intent router returned invalid JSON: %s", text[:500])
        return None
    return data if isinstance(data, dict) else None


def _compact_memory(memory_context: Any | None) -> dict[str, Any]:
    if not memory_context:
        return {}
    return {
        "active_draft": getattr(memory_context, "active_draft", None),
        "last_tool": getattr(memory_context, "last_tool", None),
        "recent_query_tool": getattr(memory_context, "recent_query_tool", None),
    }


def _recent_conversation(conversation) -> list[dict[str, Any]]:
    messages = getattr(conversation, "messages", None)
    if not isinstance(messages, list):
        return []
    return [
        {
            "role": item.get("role"),
            "content": item.get("content"),
            "mode": item.get("mode"),
            "intent": item.get("intent"),
            "tool_code": item.get("tool_code"),
        }
        for item in messages[-8:]
    ]
