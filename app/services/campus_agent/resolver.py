"""Context resolver for multi-turn campus assistant operations."""
from __future__ import annotations

import re
from typing import Any

from app.services.campus_agent.planner import (
    CREATE_TOOL_CODES,
    QUERY_TOOL_CODES,
    TOOL_OBJECTS,
    parse_tool_args,
)
from app.services.campus_agent.schemas import AgentPlan


ENTITY_TOOL_CODES = {
    "student": {"query_student", "update_student", "delete_student", "create_student"},
    "teacher": {"query_teacher", "update_teacher", "delete_teacher", "create_teacher"},
}

ENTITY_CODE_FIELDS = {
    "student": "student_no",
    "teacher": "employee_no",
}

ENTITY_NAME_FIELDS = {
    "student": "name",
    "teacher": "name",
}

CONTINUATION_WORDS = ["继续", "下一页", "下页", "显示更多", "更多", "全部显示", "显示全部", "显示所有", "显示全部的", "能显示全部", "可以显示全部", "都显示", "完整显示"]
SHOW_ALL_WORDS = ["全部显示", "显示全部", "显示所有", "显示全部的", "能显示全部", "可以显示全部", "都显示", "完整显示"]


def deep_merge_tool_args(base: dict | None, incoming: dict | None) -> dict:
    merged = dict(base or {})
    for transient_key in ["pending_action_id", "draft_id"]:
        merged.pop(transient_key, None)
    for key, value in (incoming or {}).items():
        if value in (None, "", [], {}):
            continue
        if key == "changes" and isinstance(value, dict):
            existing = merged.get("changes") if isinstance(merged.get("changes"), dict) else {}
            merged["changes"] = {**existing, **value}
        else:
            merged[key] = value
    return merged


def _merge_plan_args(tool_code: str | None, base: dict | None, incoming: dict | None) -> dict:
    merged = deep_merge_tool_args(base, incoming)
    if tool_code == "send_email" and incoming:
        if incoming.get("recipient_email") or incoming.get("recipient_keyword") or incoming.get("recipient_user_id"):
            for key in ["recipient_email", "recipient_keyword", "recipient_user_id"]:
                if key not in incoming:
                    merged.pop(key, None)
            merged = deep_merge_tool_args(merged, incoming)
    return merged


def _candidate_selection_index(message: str) -> int | None:
    text = (message or "").strip()
    match = re.search(r"(?:选|选择|用|就)?\s*第?\s*([一二三四五六七八九十\d]+)\s*(?:个|条|项)?", text)
    if not match:
        return None
    raw = match.group(1)
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if raw.isdigit():
        return int(raw) - 1
    return cn_map.get(raw, 0) - 1


def _extract_candidate_target_args(message: str, previous_context: dict | None) -> dict:
    if not previous_context:
        return {}
    direct_id = re.search(r"(?:ID|id)[:： ]*#?(\d+)", message or "")
    previous_tool = previous_context.get("tool_code") or ""
    data = previous_context.get("tool_data") or {}
    candidates = data.get("candidates") or []
    if direct_id:
        selected_id = int(direct_id.group(1))
        if previous_tool in TOOL_OBJECTS:
            return {"target_id": selected_id}
        for candidate in candidates:
            if int(candidate.get("id") or 0) == selected_id:
                return _candidate_to_args(previous_tool, candidate)
    if not candidates:
        return {}
    idx = _candidate_selection_index(message)
    if idx is None or idx < 0 or idx >= len(candidates):
        return {}
    return _candidate_to_args(previous_tool, candidates[idx])


def _candidate_to_args(previous_tool: str, candidate: dict) -> dict:
    selected_id = candidate.get("id")
    if not selected_id:
        return {}
    if previous_tool in TOOL_OBJECTS:
        return {"target_id": selected_id}
    if previous_tool == "create_student":
        return {"clazz_id": selected_id}
    if previous_tool == "send_email":
        return {"recipient_user_id": selected_id}
    if previous_tool in {"create_teacher", "create_course", "create_class"}:
        if candidate.get("employee_no") or candidate.get("position"):
            if previous_tool == "create_class":
                return {"counselor_id": selected_id}
            return {"teacher_id": selected_id}
        return {"department_id": selected_id}
    return {}


def _has_pronoun_reference(message: str) -> bool:
    return any(word in (message or "") for word in ["这个", "这个人", "这个学生", "这名学生", "该学生", "他", "她", "TA", "ta"])


def _first_previous_item(previous_context: dict | None, tool_code: str) -> dict | None:
    if not previous_context or previous_context.get("tool_code") != tool_code:
        return None
    data = previous_context.get("tool_data") or {}
    items = data.get("items") or []
    return items[0] if items else None


def _recent_student_item(memory_context: Any, previous_context: dict | None) -> dict | None:
    return _recent_entity_item(memory_context, previous_context, "student")


def _recent_entity_item(memory_context: Any, previous_context: dict | None, entity_type: str) -> dict | None:
    query_tool = f"query_{entity_type}"
    item = _first_previous_item(previous_context, query_tool)
    if item:
        return item
    if previous_context and previous_context.get("tool_code") in ENTITY_TOOL_CODES.get(entity_type, set()):
        data = previous_context.get("tool_data") or {}
        if isinstance(data, dict):
            if data.get("id") or data.get(ENTITY_CODE_FIELDS[entity_type]) or data.get(ENTITY_NAME_FIELDS[entity_type]):
                return data
            args = data.get("args") if isinstance(data.get("args"), dict) else {}
            if args:
                return args
    for msg in reversed(getattr(memory_context, "messages", []) or []):
        if msg.get("role") != "assistant" or msg.get("tool_code") not in ENTITY_TOOL_CODES.get(entity_type, set()):
            continue
        data = msg.get("tool_data") or {}
        items = data.get("items") or []
        if items:
            return items[0]
        if isinstance(data, dict) and (data.get("id") or data.get(ENTITY_CODE_FIELDS[entity_type]) or data.get(ENTITY_NAME_FIELDS[entity_type])):
            return data
    return None


def _extract_student_reference_args(
    message: str,
    memory_context: Any,
    previous_context: dict | None,
    tool_code: str | None,
) -> dict:
    return _extract_entity_reference_args(message, memory_context, previous_context, tool_code)


def _extract_entity_reference_args(
    message: str,
    memory_context: Any,
    previous_context: dict | None,
    tool_code: str | None,
) -> dict:
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", " ", message or "")
    teacher_no_match = re.search(r"[Tt]\d{6,}", text)
    if teacher_no_match:
        if tool_code in {"query_teacher", "update_teacher", "delete_teacher"}:
            key = "target_keyword" if tool_code in {"update_teacher", "delete_teacher"} else "keyword"
            return {key: teacher_no_match.group(0).upper()}
        return {}

    student_no_match = re.search(r"[Ss]\d{6,}", text)
    if student_no_match:
        if tool_code in {"query_student", "query_score", "update_student", "delete_student"}:
            key = "target_keyword" if tool_code in {"update_student", "delete_student"} else "keyword"
            return {key: student_no_match.group(0).upper()}
        return {}

    if not _has_pronoun_reference(text):
        return {}

    entity_type = None
    if tool_code in {"query_teacher", "update_teacher", "delete_teacher"}:
        entity_type = "teacher"
    elif tool_code in {"query_student", "query_score", "update_student", "delete_student"}:
        entity_type = "student"
    if not entity_type:
        return {}

    item = _recent_entity_item(memory_context, previous_context, entity_type)
    if not item:
        return {}

    code_field = ENTITY_CODE_FIELDS[entity_type]
    name_field = ENTITY_NAME_FIELDS[entity_type]
    keyword = item.get(code_field) or item.get("code") or item.get(name_field) or item.get("target_keyword")
    if not keyword and entity_type == "teacher":
        keyword = item.get("employee_no")
    if not keyword and entity_type == "student":
        keyword = item.get("student_no")

    if tool_code == "query_score":
        return {"keyword": keyword} if keyword else {}
    if tool_code in {"query_student", "query_teacher"}:
        return {"keyword": keyword} if keyword else {}
    if tool_code in {"update_student", "delete_student", "update_teacher", "delete_teacher"}:
        return {"target_keyword": keyword} if keyword else {}
    return {}


def _infer_followup_tool(message: str, previous_context: dict | None) -> str | None:
    if not previous_context:
        return None
    previous_tool = previous_context.get("tool_code")
    if not previous_tool:
        return None
    text = message or ""
    if previous_context.get("tool_status") in {"need_more_info", "confirm_required"} and previous_tool in {
        "send_email",
        "send_bulk_email",
        *CREATE_TOOL_CODES,
        *TOOL_OBJECTS.keys(),
    }:
        return previous_tool
    if previous_tool == "query_student" and any(word in text for word in ["性别", "手机号", "电话", "邮箱", "班级", "院系", "学院", "状态", "学号"]):
        return "query_student"
    if previous_tool in {"query_teacher", "update_teacher", "delete_teacher"} and any(word in text for word in ["工号", "岗位", "职位", "职称", "手机号", "电话", "邮箱", "院系", "学院", "状态"]):
        return "query_teacher"
    if _has_pronoun_reference(text):
        if previous_tool == "query_student" and any(word in text for word in ["成绩", "分数"]):
            return "query_score"
        if previous_tool == "query_student":
            return "query_student"
        if previous_tool in {"query_teacher", "update_teacher", "delete_teacher"}:
            return "query_teacher"
    if previous_tool == "query_my_schedule" and any(word in text for word in ["今天", "明天", "课", "上课"]):
        return previous_tool
    if previous_tool == "query_my_attendance" and any(word in text for word in ["请假", "迟到", "缺勤", "考勤", "只看"]):
        return previous_tool
    if previous_tool == "query_my_leave" and any(word in text for word in ["待审批", "通过", "驳回", "请假", "只看"]):
        return previous_tool
    if previous_tool in QUERY_TOOL_CODES and any(word in text for word in ["再", "换成", "查", "查询", "搜索", "只看", "详细", "那"]):
        return previous_tool
    return None


def _continuation_args(message: str, previous_context: dict | None) -> tuple[str | None, dict]:
    if not previous_context:
        return None, {}
    previous_tool = previous_context.get("tool_code")
    if not previous_tool:
        return None, {}
    if previous_context.get("tool_status") in {"need_more_info", "confirm_required"}:
        return previous_tool, {}

    text = message or ""
    if not any(word in text for word in CONTINUATION_WORDS):
        return None, {}

    args = dict(previous_context.get("tool_args") or {})
    data = previous_context.get("tool_data") or {}
    total = int(data.get("total") or 0)
    current_page = int(args.get("page") or 1)
    current_limit = int(args.get("limit") or len(data.get("items") or []) or 8)
    if any(word in text for word in SHOW_ALL_WORDS):
        if total:
            args["page"] = 1
            args["limit"] = min(total, 100)
        else:
            args["limit"] = 100
        return previous_tool, args
    args["page"] = current_page + 1
    args["limit"] = max(1, min(current_limit, 100))
    return previous_tool, args


class CampusAgentResolver:
    """Merge planner output with conversation memory and task drafts."""

    def resolve(self, plan: AgentPlan, message: str, memory_context: Any) -> AgentPlan:
        previous_context = (memory_context.active_draft or memory_context.last_tool) if memory_context else None
        recent_query_context = getattr(memory_context, "recent_query_tool", None) if memory_context else None
        is_continuation_message = any(word in (message or "") for word in CONTINUATION_WORDS)

        if plan.intent == "continue_previous":
            continuation_context = previous_context
            if recent_query_context and (not previous_context or previous_context.get("tool_status") not in {"need_more_info", "confirm_required"}):
                continuation_context = recent_query_context
            tool_code, args = _continuation_args(message, continuation_context)
            if not tool_code and continuation_context:
                tool_code = continuation_context.get("tool_code")
                args = dict(continuation_context.get("tool_args") or {})
            if tool_code:
                parsed = parse_tool_args(tool_code, message)
                candidate_args = _extract_candidate_target_args(message, continuation_context)
                args = _merge_plan_args(tool_code, args, parsed)
                args = deep_merge_tool_args(args, candidate_args)
                plan.tool_code = tool_code
                plan.args = args
                plan.intent = tool_code
                plan.status = "planned"
                plan.response_mode = "academic_ops"
            return plan

        if not plan.tool_code:
            followup_tool = _infer_followup_tool(message, previous_context)
            if followup_tool:
                plan.tool_code = followup_tool
                plan.args = parse_tool_args(followup_tool, message)
                plan.intent = followup_tool
                plan.status = "planned"
                plan.response_mode = "academic_ops"

        if not plan.tool_code:
            return plan

        if (
            plan.tool_code in {"query_student", "query_teacher"}
            and not (plan.args or {}).get("keyword")
            and not is_continuation_message
            and previous_context
            and previous_context.get("tool_code") in ENTITY_TOOL_CODES.get(plan.tool_code.replace("query_", ""), set())
        ):
            item = _recent_entity_item(memory_context, previous_context, plan.tool_code.replace("query_", ""))
            if item:
                code = item.get(ENTITY_CODE_FIELDS[plan.tool_code.replace("query_", "")])
                name = item.get(ENTITY_NAME_FIELDS[plan.tool_code.replace("query_", "")])
                text = message or ""
                if code or (name and name in text):
                    plan.args = deep_merge_tool_args(plan.args, {"keyword": code or name})

        base_args = {}
        if previous_context and previous_context.get("tool_status") in {"need_more_info", "confirm_required"}:
            previous_tool = previous_context.get("tool_code")
            if previous_tool == plan.tool_code:
                base_args = dict(previous_context.get("tool_args") or {})

        candidate_args = _extract_candidate_target_args(message, previous_context)
        reference_args = {} if is_continuation_message else _extract_student_reference_args(message, memory_context, previous_context, plan.tool_code)
        merged = _merge_plan_args(plan.tool_code, base_args, plan.args)
        merged = deep_merge_tool_args(merged, candidate_args)
        merged = deep_merge_tool_args(merged, reference_args)
        plan.args = merged
        return plan


def should_store_draft(tool_code: str, tool_result) -> bool:
    return (tool_code in CREATE_TOOL_CODES or tool_code in TOOL_OBJECTS) and tool_result.status == "need_more_info"


def should_finish_draft(tool_result) -> bool:
    return tool_result.status in {"confirm_required", "success"}


def draft_payload_from_tool_result(tool_result) -> tuple[list, list]:
    data = tool_result.data if isinstance(tool_result.data, dict) else {}
    missing_fields = data.get("missing_fields") or []
    candidates = data.get("candidates") or []
    return missing_fields, candidates
