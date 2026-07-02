"""LLM-backed structured planner for the campus assistant."""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from typing import Any

from app.config import settings
from app.services.campus_agent.registry import AGENT_TOOLS
from app.services.campus_agent.schemas import AgentPlan
from app.services.campus_agent.tool_specs import specs_for_prompt

logger = logging.getLogger("app")

MAX_HISTORY_ITEMS = 8
LLM_TIMEOUT_SECONDS = 20
LLM_FAILURE_COOLDOWN_SECONDS = 120
_disabled_until = 0.0


def _strip_json_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, flags=re.I).strip()
        value = re.sub(r"```$", "", value).strip()
    first = value.find("{")
    last = value.rfind("}")
    if first >= 0 and last >= first:
        value = value[first : last + 1]
    return value


def _json_loads_loose(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(_strip_json_fence(text))
    except Exception:
        logger.warning("Campus agent LLM planner returned invalid JSON: %s", text[:500])
        return None
    return data if isinstance(data, dict) else None


def _provider() -> str:
    provider = (settings.CAMPUS_AGENT_INTENT_PROVIDER or "deepseek").strip().lower()
    return provider if provider in {"deepseek", "qwen"} else "deepseek"


def _provider_config() -> tuple[str, str, str]:
    provider = _provider()
    if provider == "qwen":
        return (
            settings.QWEN_API_KEY,
            settings.QWEN_API_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            settings.QWEN_MODEL or "qwen-plus",
        )
    return (
        settings.DEEPSEEK_API_KEY,
        settings.DEEPSEEK_API_URL or "https://api.deepseek.com/v1/chat/completions",
        settings.DEEPSEEK_MODEL or "deepseek-chat",
    )


def _llm_enabled() -> bool:
    api_key, api_url, _ = _provider_config()
    return bool(api_key and api_url and time.time() >= _disabled_until)


def _chat_completions_url() -> str:
    _, api_url, _ = _provider_config()
    url = api_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return f"{url}/chat/completions"


def _safe_history(memory_context: Any | None) -> list[dict]:
    if not memory_context:
        return []
    history = []
    for item in (getattr(memory_context, "messages", None) or [])[-MAX_HISTORY_ITEMS:]:
        history.append({
            "role": item.get("role"),
            "content": item.get("content"),
            "tool_code": item.get("tool_code"),
            "tool_args": item.get("tool_args"),
            "tool_status": item.get("tool_status"),
            "tool_data": item.get("tool_data"),
        })
    return history


def _compact_context(memory_context: Any | None) -> dict:
    if not memory_context:
        return {}
    return {
        "active_draft": getattr(memory_context, "active_draft", None),
        "last_tool": getattr(memory_context, "last_tool", None),
        "recent_messages": _safe_history(memory_context),
    }


def _build_messages(message: str, available_tool_codes: set[str], memory_context: Any | None) -> list[dict]:
    tool_specs = specs_for_prompt(available_tool_codes)
    system = (
        "你是校园管理系统的自然语言操作规划器。你的任务不是聊天，而是把用户中文请求转换为一个后端工具调用计划。\n"
        "必须只输出 JSON，不要输出解释、Markdown 或多余文字。\n"
        "只能选择给定 tool_specs 中存在的 tool_code；如果无法判断，tool_code 置为 null。\n"
        "写操作只做计划，不要声称已经执行；后端会统一做权限、确认、审计和真实执行。\n"
        "如果用户是在补充上一轮缺失参数、选择候选项、继续显示、确认执行，要结合 memory_context。\n"
        "字段约定：修改类工具使用 target_keyword 或 target_id 定位对象，要修改的字段放入 changes；查询类通常使用 keyword；邮件使用 recipient_keyword/recipient_email/subject/body；群发邮件使用 recipient_scope=students/teachers/all_users。\n"
        "性别字段 gender：男=1，女=2。状态字段按 tool_specs 描述转换。数字字段必须输出数字。\n"
        "输出 JSON 格式：{\"tool_code\": string|null, \"intent\": string, \"confidence\": number, \"args\": object, \"missing_fields\": string[], \"is_followup\": boolean, \"reason\": string}。"
    )
    user_payload = {
        "message": message,
        "tool_specs": tool_specs,
        "memory_context": _compact_context(memory_context),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
    ]


def _call_structured_llm(messages: list[dict]) -> str | None:
    global _disabled_until
    if not _llm_enabled():
        return None
    api_key, _, model = _provider_config()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _chat_completions_url(),
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
        result = json.loads(body)
        return result["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("Campus agent structured LLM planner failed: %s", exc)
        _disabled_until = time.time() + LLM_FAILURE_COOLDOWN_SECONDS
        return None


def _clean_args(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for key, item in value.items():
        if item in (None, "", [], {}):
            continue
        if key == "changes" and isinstance(item, dict):
            changes = {k: v for k, v in item.items() if v not in (None, "", [], {})}
            if changes:
                cleaned[key] = changes
        else:
            cleaned[key] = item
    return cleaned


class CampusAgentLLMPlanner:
    """Convert natural language into a whitelisted AgentPlan with DeepSeek."""

    def plan(
        self,
        message: str,
        *,
        available_tool_codes: set[str] | None = None,
        memory_context: Any | None = None,
    ) -> AgentPlan | None:
        if not _llm_enabled():
            return None

        allowed = set(available_tool_codes or AGENT_TOOLS.keys())
        raw = _call_structured_llm(_build_messages(message, allowed, memory_context))
        if not raw:
            return None
        data = _json_loads_loose(raw)
        if not data:
            return None

        tool_code = data.get("tool_code")
        confidence = float(data.get("confidence") or 0)
        if not tool_code or tool_code not in allowed or tool_code not in AGENT_TOOLS:
            return None
        if confidence < 0.45:
            return None

        return AgentPlan(
            tool_code=tool_code,
            args=_clean_args(data.get("args")),
            status="planned",
            intent=str(data.get("intent") or tool_code),
            confidence=confidence,
            response_mode="academic_ops",
            reason=f"{_provider()}_structured_intent:{data.get('reason') or 'llm_planner'}",
        )
