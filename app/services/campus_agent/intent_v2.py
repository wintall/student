"""Clean intent and slot layer for the campus assistant.

This module intentionally avoids the older mojibake-heavy rule files.  It
handles high-frequency intents deterministically first, then lets the existing
LLM planner handle flexible CRUD when available.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from app.services.campus_agent.github_tools import should_use_github
from app.services.campus_agent.schemas import AgentPlan


LEAVE_TYPE_ALIASES = {
    "病假": "sick",
    "生病": "sick",
    "发烧": "sick",
    "感冒": "sick",
    "事假": "personal",
    "有事": "personal",
    "公假": "official",
    "公出": "official",
    "婚假": "marriage",
    "丧假": "funeral",
    "产假": "maternity",
}

LEAVE_TYPE_TEXT = {
    "sick": "病假",
    "personal": "事假",
    "official": "公假",
    "funeral": "丧假",
    "marriage": "婚假",
    "maternity": "产假",
    "other": "其他",
}

ACADEMIC_KEYWORDS = [
    "学生", "同学", "学号", "教师", "老师", "教职工", "工号", "课程", "成绩",
    "课表", "考勤", "请假", "班级", "院系", "学院", "教室", "学期", "公告",
    "通知", "邮件", "发信", "写信", "我是谁", "我的信息", "我的身份", "我的老师",
    "我的班主任", "我的辅导员", "任课老师", "我的课程",
]

EMOTION_KEYWORDS = [
    "心情不好", "焦虑", "抑郁", "压力", "压力大", "难受", "绝望", "崩溃", "撑不住",
    "不想活", "想死", "轻生", "心理建议", "烦", "很累", "好累", "痛苦", "失眠",
    "害怕", "担心", "自责", "内耗", "被催", "催我", "push我", "push 我",
]


def _is_emotion_intent(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "").lower()
    return any(word.lower().replace(" ", "") in compact for word in EMOTION_KEYWORDS)


def _contains_any(text: str, words: list[str] | tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()
    return None


def _normalize_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _parse_date_base(text: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now()
    if "后天" in text:
        return now + timedelta(days=2)
    if "明天" in text or "明日" in text:
        return now + timedelta(days=1)
    if "今天" in text or "今日" in text:
        return now
    date_match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?", text)
    if date_match:
        return datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
    md_match = re.search(r"(\d{1,2})月(\d{1,2})日?", text)
    if md_match:
        return datetime(now.year, int(md_match.group(1)), int(md_match.group(2)))
    return None


def _parse_time_range(text: str, now: datetime | None = None) -> tuple[str | None, str | None]:
    base = _parse_date_base(text, now)
    if not base:
        return None, None
    day = _normalize_date(base)

    if "上午" in text:
        return f"{day} 08:00:00", f"{day} 12:00:00"
    if "下午" in text:
        return f"{day} 14:00:00", f"{day} 18:00:00"
    if "晚上" in text:
        return f"{day} 18:00:00", f"{day} 22:00:00"
    if "全天" in text or "一天" in text or "1天" in text:
        return f"{day} 08:00:00", f"{day} 18:00:00"

    hour_range = re.search(r"(\d{1,2})点(?:到|至|-)(\d{1,2})点", text)
    if hour_range:
        return f"{day} {int(hour_range.group(1)):02d}:00:00", f"{day} {int(hour_range.group(2)):02d}:00:00"

    return f"{day} 08:00:00", f"{day} 18:00:00"


def _parse_leave_type(text: str) -> str | None:
    for key, value in LEAVE_TYPE_ALIASES.items():
        if key in text:
            return value
    if "请假" in text:
        return None
    return None


def _parse_reason(text: str) -> str | None:
    reason = _first_match(text, [
        r"(?:原因是|原因|因为|由于)(.+)$",
        r"(?:理由是|理由)(.+)$",
    ])
    if reason:
        return reason.strip(" ，。,.")
    if "发烧" in text:
        return "发烧"
    if "感冒" in text:
        return "感冒"
    if "身体不舒服" in text or "不舒服" in text:
        return "身体不舒服"
    return None


def parse_leave_args(text: str, base_args: dict | None = None) -> dict:
    args = dict(base_args or {})
    leave_type = _parse_leave_type(text)
    if leave_type:
        args["leave_type"] = leave_type
    start_time, end_time = _parse_time_range(text)
    if start_time and end_time:
        args["start_time"] = start_time
        args["end_time"] = end_time
    reason = _parse_reason(text)
    if reason:
        args["reason"] = reason
    destination = _first_match(text, [r"(?:去|到)(医院|家|校外|.+?)(?:，|。|,|$)"])
    if destination:
        args["destination"] = destination
    return args


def _is_leave_create_intent(text: str, memory_context: Any | None = None) -> bool:
    if _contains_any(text, [
        "我想请假", "我要请假", "帮我请假", "请个假", "提交请假", "申请请假", "请病假", "请事假",
        "向老师请假", "跟老师请假", "给老师请假", "向班主任请假", "跟班主任请假",
    ]):
        return True
    active = getattr(memory_context, "active_draft", None) if memory_context else None
    if not (active and active.get("tool_code") == "create_leave_request"):
        return False
    return bool(
        _contains_any(text, list(LEAVE_TYPE_ALIASES.keys()))
        or _contains_any(text, ["今天", "明天", "后天", "上午", "下午", "全天", "原因", "因为", "发烧", "感冒", "不舒服"])
    )


def _is_leave_query_intent(text: str) -> bool:
    return _contains_any(text, ["我的请假", "请假进度", "请假状态", "请假记录"]) and not _contains_any(text, ["申请", "提交", "想请", "我要请"])


def _personal_profile_field(text: str) -> str | None:
    if _contains_any(text, ["哪个班", "哪班", "班级"]):
        return "class"
    if _contains_any(text, ["学院", "院系", "系部"]):
        return "department"
    if _contains_any(text, ["角色", "身份", "学生还是老师"]):
        return "role"
    return None


def _is_my_profile_intent(text: str) -> bool:
    return _contains_any(text, [
        "我是谁",
        "我的信息",
        "我的资料",
        "我的个人资料",
        "我的身份",
        "我的账号",
        "我是什么身份",
        "我是学生还是老师",
        "我在哪个班",
        "我属于哪个学院",
        "我的班级",
        "我的学院",
        "我的院系",
    ])


def _parse_my_teachers_args(text: str) -> dict:
    args: dict[str, Any] = {"teacher_scope": "all"}
    if _contains_any(text, ["班主任", "辅导员"]):
        args["teacher_scope"] = "counselor"
    if _contains_any(text, ["谁教我", "教我", "任课", "课程老师", "这门课"]):
        args["teacher_scope"] = "course"
    course = _first_match(text, [
        r"谁教我(.+?)(?:这门课|这课|课程)?[？?。]?$",
        r"教我(.+?)(?:的是谁|的老师是谁|老师是谁)[？?。]?$",
        r"(.+?)(?:是谁教|谁教)[？?。]?$",
    ])
    if course:
        course = course.strip(" 的课程课老师")
        if course and course not in {"谁", "我", "我的"}:
            args["course_keyword"] = course
            args["teacher_scope"] = "course"
    return args


def _is_my_teacher_courses_followup(text: str, memory_context: Any | None = None) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if not any(word in compact for word in ["老师", "他们", "她们", "他", "她", "这个老师", "这些老师"]):
        return False
    if not any(word in compact for word in ["教什么", "教哪些", "负责什么课", "上什么课", "课程"]):
        return False
    for msg in reversed(getattr(memory_context, "messages", []) or []):
        if msg.get("role") == "assistant" and msg.get("tool_code") == "query_my_teachers":
            return True
    return "我的老师" in compact or "任课老师" in compact


def _is_my_teachers_intent(text: str) -> bool:
    return _contains_any(text, [
        "我的老师",
        "我的班主任",
        "我的辅导员",
        "我的任课老师",
        "任课老师",
        "谁教我",
        "教我的老师",
        "教我课",
    ])


def _is_my_courses_intent(text: str) -> bool:
    return _contains_any(text, [
        "我的课程",
        "我有哪些课",
        "我有什么课",
        "我这学期学什么",
        "我学什么课",
        "我教哪些课",
        "我教什么课",
    ])


def _email_args(text: str) -> dict:
    args: dict[str, Any] = {}
    email = _first_match(text, [r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"])
    if email:
        args["recipient_email"] = email
    recipient = _first_match(text, [
        r"给(?:学生|老师|教师|同学)?\s*([\u4e00-\u9fa5A-Za-z0-9_@.\-]+)\s*(?:发|发送|写)",
        r"发(?:一封|个|一份)?邮件给\s*([\u4e00-\u9fa5A-Za-z0-9_@.\-]+)",
    ])
    if recipient and "@" not in recipient:
        args["recipient_keyword"] = recipient.strip("<> ")
    subject = _first_match(text, [r"主题(?:是|为|:|：)\s*([^，。,\n]+)", r"标题(?:是|为|:|：)\s*([^，。,\n]+)"])
    body = _first_match(text, [r"(?:正文|内容)(?:是|为|:|：)\s*(.+)$"])
    if subject:
        args["subject"] = subject
    if body:
        args["body"] = body.strip()
    return args


def _email_tool(text: str) -> str | None:
    if not _contains_any(text, ["邮件", "发信", "写信", "站内信"]):
        return None
    if _contains_any(text, ["所有学生", "全体学生", "所有老师", "全体教师", "全体用户", "群发"]):
        return "send_bulk_email"
    return "send_email"


def _bulk_email_args(text: str) -> dict:
    args = _email_args(text)
    if _contains_any(text, ["所有学生", "全体学生"]):
        args["recipient_scope"] = "students"
    elif _contains_any(text, ["所有老师", "全体教师", "所有教师"]):
        args["recipient_scope"] = "teachers"
    elif _contains_any(text, ["全体用户", "所有用户"]):
        args["recipient_scope"] = "all_users"
    return args


def _teacher_update_plan(text: str) -> AgentPlan | None:
    teacher_no = re.search(r"[Tt]\d{6,}", text or "")
    if not teacher_no:
        return None
    if not _contains_any(text, ["修改", "更新", "调整", "更改", "设置", "改为", "改成"]):
        return None
    changes: dict[str, Any] = {}
    if _contains_any(text, ["岗位", "职位"]):
        for value in ["院系主任", "班主任", "辅导员", "教师", "管理员"]:
            if value in text:
                changes["position"] = value
                break
    if "职称" in text:
        for value in ["副教授", "教授", "讲师", "助教"]:
            if value in text:
                changes["title"] = value
                break
    if not changes:
        return None
    return AgentPlan(
        tool_code="update_teacher",
        args={"target_keyword": teacher_no.group(0).upper(), "changes": changes},
        status="planned",
        intent="update_teacher",
        confidence=0.96,
        response_mode="academic_ops",
        reason="intent_v2_teacher_update_employee_no",
    )


def route_mode_v2(text: str) -> str | None:
    if should_use_github(text):
        return "github"
    if _is_emotion_intent(text):
        return "emotion"
    if _is_my_profile_intent(text) or _is_my_teachers_intent(text) or _is_my_courses_intent(text):
        return "academic_ops"
    if _contains_any(text, [
        "我想请假", "我要请假", "帮我请假", "请个假", "提交请假", "申请请假", "我的请假", "请假进度",
        "向老师请假", "跟老师请假", "给老师请假", "向班主任请假", "跟班主任请假",
    ]):
        return "academic_ops"
    if _email_tool(text):
        return "academic_ops"
    if _contains_any(text, ACADEMIC_KEYWORDS) or re.search(r"[SsTt]\d{6,}", text):
        return "academic_ops"
    if _contains_any(text, ["赏析", "讲解", "学习", "题目", "牛顿", "将进酒", "诗词", "复习计划"]):
        return "study"
    if _contains_any(text, ["路线", "怎么去", "怎么走", "附近", "周边", "吃喝玩乐", "餐厅", "景点"]):
        return "map"
    if _contains_any(text, ["搜索", "最新", "新闻", "热搜", "股价", "政策"]):
        return "search"
    if _contains_any(text, ["知识库", "根据文档", "根据资料", "导入的文档"]):
        return "rag"
    if _contains_any(text, ["分析项目", "代码体检", "分析代码", "项目路径"]):
        return "code_review"
    if _contains_any(text, ["OCR", "识别图片", "提取图片文字", "翻译", "总结文件"]):
        return "document"
    return None


def plan_v2(message: str, *, memory_context: Any | None = None) -> AgentPlan | None:
    text = (message or "").strip()
    if not text:
        return None

    active = getattr(memory_context, "active_draft", None) if memory_context else None
    teacher_update = _teacher_update_plan(text)
    if teacher_update:
        return teacher_update
    if _is_my_profile_intent(text):
        args = {}
        field = _personal_profile_field(text)
        if field:
            args["profile_field"] = field
        return AgentPlan(
            tool_code="query_my_profile",
            args=args,
            status="planned",
            intent="query_my_profile",
            confidence=0.95,
            response_mode="academic_ops",
            reason="intent_v2_my_profile",
        )
    if _is_my_teachers_intent(text):
        return AgentPlan(
            tool_code="query_my_teachers",
            args=_parse_my_teachers_args(text),
            status="planned",
            intent="query_my_teachers",
            confidence=0.94,
            response_mode="academic_ops",
            reason="intent_v2_my_teachers",
        )
    if _is_my_teacher_courses_followup(text, memory_context):
        return AgentPlan(
            tool_code="query_my_teachers",
            args={"teacher_scope": "all", "_relation_followup": "teacher_courses"},
            status="planned",
            intent="query_my_teacher_courses_followup",
            confidence=0.91,
            response_mode="academic_ops",
            reason="intent_v2_teacher_courses_followup",
        )
    if _is_my_courses_intent(text):
        return AgentPlan(
            tool_code="query_my_courses",
            args={},
            status="planned",
            intent="query_my_courses",
            confidence=0.9,
            response_mode="academic_ops",
            reason="intent_v2_my_courses",
        )
    if _is_leave_create_intent(text, memory_context):
        base_args = (active or {}).get("tool_args") if active and active.get("tool_code") == "create_leave_request" else {}
        return AgentPlan(
            tool_code="create_leave_request",
            args=parse_leave_args(text, base_args),
            status="planned",
            intent="create_leave_request",
            confidence=0.96,
            response_mode="academic_ops",
            reason="intent_v2_leave",
        )
    if _is_leave_query_intent(text):
        return AgentPlan(
            tool_code="query_my_leave",
            args={},
            status="planned",
            intent="query_my_leave",
            confidence=0.9,
            response_mode="academic_ops",
            reason="intent_v2_leave_query",
        )

    email_tool = _email_tool(text)
    if email_tool == "send_email":
        base_args = (active or {}).get("tool_args") if active and active.get("tool_code") == "send_email" else {}
        return AgentPlan(
            tool_code="send_email",
            args={**base_args, **_email_args(text)},
            status="planned",
            intent="send_email",
            confidence=0.88,
            response_mode="academic_ops",
            reason="intent_v2_email",
        )
    if email_tool == "send_bulk_email":
        base_args = (active or {}).get("tool_args") if active and active.get("tool_code") == "send_bulk_email" else {}
        return AgentPlan(
            tool_code="send_bulk_email",
            args={**base_args, **_bulk_email_args(text)},
            status="planned",
            intent="send_bulk_email",
            confidence=0.88,
            response_mode="academic_ops",
            reason="intent_v2_bulk_email",
        )

    return None
