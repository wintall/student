"""Concrete handlers for campus assistant tools."""
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.common import PageParams
from app.services import announcement_service, attendance_service, leave_service, schedule_service
from app.utils.entity_mappers import (
    attendance_record_to_dict,
    course_schedule_to_dict,
    leave_request_to_dict,
)
from app.utils.pagination import paginate


WEEKDAY_NAMES = {
    1: "周一",
    2: "周二",
    3: "周三",
    4: "周四",
    5: "周五",
    6: "周六",
    7: "周日",
}

STATUS_TEXT = {
    "normal": "正常",
    "present": "正常",
    "late": "迟到",
    "early_leave": "早退",
    "absent": "缺勤",
    "leave": "请假",
    "manual": "手工记录",
    "pending": "待审批",
    "approved": "已通过",
    "rejected": "已驳回",
    "cancelled": "已撤销",
}


def _limit(value: Any, default: int = 8, max_value: int = 20) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(1, min(number, max_value))


def _page_params(args: dict | None = None, default_size: int = 8) -> PageParams:
    args = args or {}
    return PageParams(
        page=1,
        page_size=_limit(args.get("limit"), default=default_size),
        keyword=args.get("keyword"),
    )


def _format_date(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _format_datetime(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _query_my_schedule(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=10)
    q = schedule_service.list_my_course_schedules(user, params, db, args.get("term_id"))
    if args.get("weekday"):
        q = q.filter_by(weekday=int(args["weekday"]))
    result = paginate(q, params)
    items = [course_schedule_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {
            "message": "没有查询到你的课表记录。",
            "data": {"total": result.get("total", 0), "items": []},
        }

    lines = [f"查询到 {result.get('total', len(items))} 条课表，先显示 {len(items)} 条："]
    for item in items:
        weekday = WEEKDAY_NAMES.get(item.get("weekday"), f"周{item.get('weekday')}")
        sections = f"{item.get('start_section')}-{item.get('end_section')}节"
        weeks = f"第{item.get('start_week')}-{item.get('end_week')}周"
        course_name = item.get("course_name") or "未知课程"
        teacher_name = item.get("teacher_name") or "未安排"
        room = item.get("classroom_name") or "未安排教室"
        lines.append(
            f"- {weekday} {sections}，{weeks}：{course_name}，"
            f"教师：{teacher_name}，地点：{room}"
        )

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_my_attendance(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = attendance_service.list_my_attendance(
        user=user,
        params=params,
        db=db,
        status=args.get("status"),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
    )
    result = paginate(q, params)
    items = [attendance_record_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {
            "message": "没有查询到你的考勤记录。",
            "data": {"total": result.get("total", 0), "items": []},
        }

    lines = [f"查询到 {result.get('total', len(items))} 条考勤记录，先显示 {len(items)} 条："]
    for item in items:
        status = STATUS_TEXT.get(item.get("status"), item.get("status") or "未知")
        period = item.get("period_type") or "day"
        remark = f"，备注：{item.get('remark')}" if item.get("remark") else ""
        lines.append(f"- {_format_date(item.get('attendance_date'))}，时段：{period}，状态：{status}{remark}")

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_my_leave(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = leave_service.list_my_leave_requests(
        user=user,
        params=params,
        db=db,
        status=args.get("status"),
        applicant_type=args.get("applicant_type"),
        leave_type=args.get("leave_type"),
    )
    result = paginate(q, params)
    items = [leave_request_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {
            "message": "没有查询到你的请假申请。",
            "data": {"total": result.get("total", 0), "items": []},
        }

    lines = [f"查询到 {result.get('total', len(items))} 条请假申请，先显示 {len(items)} 条："]
    for item in items:
        status = STATUS_TEXT.get(item.get("status"), item.get("status") or "未知")
        lines.append(
            f"- {item.get('leave_type', '请假')}：{_format_datetime(item.get('start_time'))} 至 "
            f"{_format_datetime(item.get('end_time'))}，状态：{status}，原因：{item.get('reason', '')}"
        )

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_announcements(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=6)
    q = announcement_service.list_announcements(params, db)
    result = paginate(q, params)
    items = []
    for ann in result.get("items", []):
        content = ann.content or ""
        items.append({
            "id": ann.id,
            "title": ann.title,
            "summary": content[:60],
            "status": ann.status,
            "is_top": ann.is_top,
            "published_at": _format_datetime(ann.published_at),
            "created_at": _format_datetime(ann.created_at),
        })

    if not items:
        return {"message": "没有查询到公告。", "data": {"total": result.get("total", 0), "items": []}}

    lines = [f"查询到 {result.get('total', len(items))} 条公告，先显示 {len(items)} 条："]
    for item in items:
        top = "置顶，" if item.get("is_top") else ""
        published = item.get("published_at") or item.get("created_at")
        summary = f"：{item.get('summary')}" if item.get("summary") else ""
        lines.append(f"- {top}{item.get('title')}（{published}）{summary}")

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def normalize_args(tool_code: str, message: str, args: dict | None = None) -> dict:
    normalized = dict(args or {})
    text = message or ""
    if tool_code == "query_my_schedule":
        today = date.today()
        if "今天" in text:
            normalized["weekday"] = today.isoweekday()
        elif "明天" in text:
            normalized["weekday"] = (today + timedelta(days=1)).isoweekday()
    if "待审批" in text or "待审核" in text:
        normalized["status"] = "pending"
    elif "已通过" in text or "通过" in text:
        normalized["status"] = "approved"
    elif "驳回" in text:
        normalized["status"] = "rejected"
    elif "请假" in text and tool_code == "query_my_attendance":
        normalized["status"] = "leave"
    return normalized


TOOL_HANDLERS = {
    "query_my_schedule": _query_my_schedule,
    "query_my_attendance": _query_my_attendance,
    "query_my_leave": _query_my_leave,
    "query_announcements": _query_announcements,
}


def execute_registered_tool(tool_code: str, user: User, args: dict, db: Session) -> dict | None:
    handler = TOOL_HANDLERS.get(tool_code)
    if not handler:
        return None
    return handler(user, args or {}, db)
