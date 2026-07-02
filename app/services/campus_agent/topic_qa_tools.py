"""Topic QA tools for AI knowledge and World Cup modes."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import rag_knowledge_service
from app.services.campus_agent.llm_client import call_deepseek
from app.services.campus_agent.web_search_tools import search_web


AI_KNOWLEDGE_WORDS = [
    "LangChain",
    "LangGraph",
    "DeepAgents",
    "MCP",
    "Dify",
    "FastAPI",
    "Python",
    "Linux",
    "SQL",
    "数据库",
    "面试题",
    "八股",
    "Agent",
    "大模型",
    "RAG",
    "向量库",
    "Milvus",
]

WORLDCUP_WORDS = ["世界杯", "FIFA", "梅西", "C罗", "姆巴佩", "克洛泽", "贝利", "马拉多纳", "冠军", "射手王", "小组赛", "淘汰赛"]


def should_use_ai_knowledge(message: str) -> bool:
    text = message or ""
    return any(word.lower() in text.lower() for word in AI_KNOWLEDGE_WORDS)


def should_use_worldcup(message: str) -> bool:
    text = message or ""
    return any(word.lower() in text.lower() for word in WORLDCUP_WORDS)


def handle_ai_knowledge_message(*, user: User, db: Session, message: str, context_messages: list[str] | None = None) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    return _handle_topic_message(
        user=user,
        db=db,
        message=message,
        topic="ai_knowledge",
        title="AI知识问答",
        system_prompt=(
            "你是校园助手的 AI 技术知识专家，擅长 LangChain、LangGraph、MCP、DeepAgents、Dify、"
            "FastAPI、Python、Linux、SQL、数据库和面试题讲解。请回答得专业、清晰、可落地。"
        ),
        context_messages=context_messages,
    )


def handle_worldcup_message(*, user: User, db: Session, message: str, context_messages: list[str] | None = None) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    return _handle_topic_message(
        user=user,
        db=db,
        message=message,
        topic="worldcup",
        title="世界杯问答",
        system_prompt=(
            "你是校园助手的世界杯专题问答专家，擅长世界杯历史、赛制、球队、球星、冠军、射手榜和经典比赛。"
            "请优先给出准确结论；遇到实时或可能变化的信息，要说明需要以最新权威数据为准。"
        ),
        context_messages=context_messages,
    )


def _handle_topic_message(
    *,
    user: User,
    db: Session,
    message: str,
    topic: str,
    title: str,
    system_prompt: str,
    context_messages: list[str] | None = None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    rag_result = rag_knowledge_service.search(
        db=db,
        user=user,
        question=message,
        kb_ids=None,
        top_k=5,
        min_score=0.25,
    )
    sources = _filter_topic_sources(topic, message, rag_result.get("items") or rag_result.get("sources") or [])
    search_data: dict[str, Any] = {"ok": False, "results": []}
    if _needs_search(topic, message, bool(sources)):
        search_data = search_web(_topic_search_query(topic, message), limit=5)

    authoritative_reply = _authoritative_worldcup_reply(message, search_data.get("results") or []) if topic == "worldcup" else None
    if authoritative_reply:
        reply = authoritative_reply
    else:
        reply = _generate_topic_reply(
            title=title,
            system_prompt=system_prompt,
            message=message,
            sources=sources,
            search_results=search_data.get("results") or [],
            context_messages=context_messages or [],
            force_search_priority=_needs_search(topic, message, bool(sources)),
        )
        if not reply:
            reply = _fallback_reply(title, message, sources, search_data.get("results") or [])

    references = _references(sources, search_data.get("results") or [])
    data = {
        "task": topic,
        "rag_source_count": len(sources),
        "search_count": len(search_data.get("results") or []),
        "provider": search_data.get("provider"),
        "used_search": bool(search_data.get("results")),
    }
    return reply, data, references


def _needs_search(topic: str, message: str, has_sources: bool) -> bool:
    text = message or ""
    if any(word in text for word in ["最新", "今天", "现在", "近期", "新闻", "版本", "2026", "当前"]):
        return True
    if topic == "worldcup" and any(word in text for word in ["射手王", "排名", "赛程", "结果", "冠军"]):
        return True
    return not has_sources


def _topic_search_query(topic: str, message: str) -> str:
    text = (message or "").strip()
    if topic == "worldcup" and _looks_like_worldcup_all_time_scorer(text):
        return "FIFA World Cup all-time leading scorers Lionel Messi Miroslav Klose latest 2026"
    if topic == "worldcup" and any(word in text for word in ["射手榜", "射手排名", "金靴", "Golden Boot"]):
        return f"2026 FIFA World Cup top scorers Golden Boot latest {text}"
    if topic == "worldcup" and any(word in text for word in ["赛程", "结果", "比分", "冠军"]):
        return f"FIFA World Cup 2026 latest {text}"
    return text


def _looks_like_worldcup_all_time_scorer(message: str) -> bool:
    text = message or ""
    return any(word in text for word in ["历史射手王", "总射手王", "历史总射手", "世界杯射手王", "世界杯历史射手", "all-time"])


def _authoritative_worldcup_reply(message: str, search_results: list[dict[str, Any]]) -> str | None:
    if not _looks_like_worldcup_all_time_scorer(message):
        return None
    haystack = "\n".join(
        f"{item.get('title') or ''}\n{item.get('snippet') or ''}\n{item.get('source') or ''}\n{item.get('url') or ''}"
        for item in search_results
    )
    lower = haystack.lower()
    if "messi" not in lower and "梅西" not in haystack:
        return None
    if not any(word in lower for word in ["top scorer", "leading scorer", "all-time", "overtaken", "surpass", "surpassed", "超越", "登顶"]):
        return None

    goals = _extract_messi_goal_count(haystack)
    goal_text = f"，目前检索到的最新数字是 **{goals} 球**" if goals else ""
    return (
        f"世界杯历史总射手王现在是 **利昂内尔·梅西**{goal_text}。\n\n"
        "以前的纪录保持者是德国球员 **米洛斯拉夫·克洛泽**，他的世界杯总进球是 16 球。"
        "这个问题属于会随 2026 年世界杯进程变化的实时统计，后续如果梅西或姆巴佩继续进球，数字还会更新。"
    )


def _extract_messi_goal_count(text: str) -> str | None:
    patterns = [
        r"Messi[^.\n]{0,80}?(?:with|to|record(?: of)?|goalscorer with)\s*(\d{2})\s*(?:goals|goal)",
        r"梅西[^。\n]{0,80}?(\d{2})\s*球",
        r"all-time[^.\n]{0,80}?(\d{2})\s*(?:goals|goal)",
        r"leading scorer[^.\n]{0,80}?(\d{2})\s*(?:goals|goal)",
    ]
    candidates: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            try:
                value = int(match.group(1))
            except Exception:
                continue
            if 17 <= value <= 30:
                candidates.append(value)
    if candidates:
        return str(max(candidates))
    return None


def _filter_topic_sources(topic: str, message: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not sources:
        return []
    words = AI_KNOWLEDGE_WORDS if topic == "ai_knowledge" else WORLDCUP_WORDS
    text = message.lower()
    topic_hits = [word for word in words if word.lower() in text]
    filtered = []
    for item in sources:
        haystack = f"{item.get('title') or ''} {item.get('content') or ''}".lower()
        if topic_hits and any(word.lower() in haystack for word in topic_hits):
            filtered.append(item)
        elif not topic_hits and any(word.lower() in haystack for word in words):
            filtered.append(item)
    return filtered[:5]


def _generate_topic_reply(
    *,
    title: str,
    system_prompt: str,
    message: str,
    sources: list[dict[str, Any]],
    search_results: list[dict[str, Any]],
    context_messages: list[str],
    force_search_priority: bool = False,
) -> str | None:
    material = []
    if context_messages:
        material.append("最近对话：\n" + "\n".join(context_messages[-4:]))
    if sources:
        material.append("本地知识库资料：\n" + "\n".join(
            f"- {item.get('title')}: {(item.get('content') or '')[:500]}" for item in sources[:5]
        ))
    if search_results:
        material.append("搜索结果摘要：\n" + "\n".join(
            f"- {item.get('title')}: {(item.get('snippet') or '')[:400]}" for item in search_results[:5]
        ))
    prompt = (
        system_prompt
        + "\n回答要求：1. 先直接回答结论；2. 再解释关键原因或知识点；3. 给出学习/使用建议；"
        + "4. 不要暴露内部工具名；5. 不要列出 URL 清单；6. 没有把握时明确说明不确定。"
    )
    if force_search_priority:
        prompt += "\n重要：该问题属于可能变化的实时信息，必须以搜索结果摘要为最高优先级；如果搜索结果与模型记忆冲突，以搜索结果为准，不要使用旧知识。"
    return call_deepseek(
        system_prompt=prompt,
        user_message=f"模块：{title}\n用户问题：{message}\n\n{chr(10).join(material)}",
        temperature=0.35,
        max_tokens=1200,
    )


def _fallback_reply(title: str, message: str, sources: list[dict[str, Any]], search_results: list[dict[str, Any]]) -> str:
    lines = [f"{title}已收到你的问题：{message}"]
    if sources:
        lines.append("我在本地知识库里找到了相关资料，可以先这样理解：")
        for item in sources[:3]:
            content = (item.get("content") or "").strip()
            lines.append(f"- {item.get('title') or '资料'}：{content[:120]}")
    elif search_results:
        lines.append("我检索到一些相关信息，先给你整理要点：")
        for item in search_results[:3]:
            lines.append(f"- {item.get('title') or item.get('source')}：{(item.get('snippet') or '')[:120]}")
    else:
        lines.append("当前没有检索到足够资料。你可以换一个更具体的问题，或者先把资料导入综合知识库。")
    return "\n".join(lines)


def _references(sources: list[dict[str, Any]], search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for idx, item in enumerate(sources[:5], 1):
        refs.append({
            "id": f"kb-{idx}",
            "title": item.get("title") or f"知识库资料 {idx}",
            "content": item.get("content") or "",
            "score": item.get("score") or 0,
            "metadata": {"source": "knowledge_base", "document_id": item.get("document_id"), "chunk_id": item.get("chunk_id")},
        })
    for idx, item in enumerate(search_results[:5], 1):
        refs.append({
            "id": f"search-{idx}",
            "title": item.get("title") or item.get("source") or f"搜索结果 {idx}",
            "content": item.get("snippet") or "",
            "score": 1,
            "metadata": {"source": item.get("source"), "url": item.get("url"), "published_at": item.get("published_at")},
        })
    return refs
