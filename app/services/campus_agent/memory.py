"""Short-term memory helpers for the campus assistant."""
from datetime import datetime
import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.user import User

MAX_MESSAGES = 20
MAX_HISTORY_SESSIONS = 20


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def create_session_id() -> str:
    return str(uuid4())


def get_or_create_session(db: Session, session_id: str | None, user: User) -> tuple[str, Conversation]:
    sid = session_id or create_session_id()
    conv = db.query(Conversation).filter(
        Conversation.session_id == sid,
        Conversation.user_id == user.id,
    ).first()
    if conv:
        return sid, conv

    conv = Conversation(
        session_id=sid,
        user_id=user.id,
        messages=[],
        book_codes=[],
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return sid, conv


def get_messages(conv: Conversation | None) -> list[dict]:
    if not conv or not isinstance(conv.messages, list):
        return []
    return conv.messages[-MAX_MESSAGES:]


def list_user_sessions(db: Session, user: User, limit: int = MAX_HISTORY_SESSIONS) -> list[Conversation]:
    limit = min(max(int(limit or MAX_HISTORY_SESSIONS), 1), 50)
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .limit(limit)
        .all()
    )


def get_user_session(db: Session, user: User, session_id: str) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.session_id == session_id)
        .first()
    )


def delete_user_session(db: Session, user: User, session_id: str) -> bool:
    conv = get_user_session(db, user, session_id)
    if not conv:
        return False
    db.delete(conv)
    db.commit()
    return True


def conversation_title(conv: Conversation) -> str:
    for msg in conv.messages or []:
        if msg.get("role") == "user" and str(msg.get("content") or "").strip():
            return str(msg["content"]).strip()[:32]
    return "新的对话"


def append_turn(
    db: Session,
    conv: Conversation,
    *,
    user_message: str,
    assistant_reply: str,
    mode: str,
    intent: str,
    tool_code: str | None = None,
    tool_args: dict | None = None,
    tool_status: str | None = None,
    tool_data: dict | None = None,
):
    messages = get_messages(conv)
    now = datetime.now().isoformat()
    messages.extend([
        {
            "role": "user",
            "content": user_message,
            "timestamp": now,
            "mode": mode,
        },
        {
            "role": "assistant",
            "content": assistant_reply,
            "timestamp": now,
            "mode": mode,
            "intent": intent,
            "tool_code": tool_code,
            "tool_args": _json_safe(tool_args or {}),
            "tool_status": tool_status,
            "tool_data": _json_safe(tool_data or {}),
        },
    ])
    conv.messages = messages[-MAX_MESSAGES:]
    db.commit()
    db.refresh(conv)


def last_tool_context(conv: Conversation | None) -> dict[str, Any] | None:
    for msg in reversed(get_messages(conv)):
        if msg.get("role") != "assistant":
            continue
        tool_code = msg.get("tool_code")
        if tool_code:
            return {
                "tool_code": tool_code,
                "tool_args": msg.get("tool_args") or {},
                "tool_data": msg.get("tool_data") or {},
                "intent": msg.get("intent"),
                "tool_status": msg.get("tool_status"),
            }
    return None


def recent_tool_context(conv: Conversation | None, tool_codes: set[str] | None = None) -> dict[str, Any] | None:
    for msg in reversed(get_messages(conv)):
        if msg.get("role") != "assistant":
            continue
        tool_code = msg.get("tool_code")
        if not tool_code:
            continue
        if tool_codes and tool_code not in tool_codes:
            continue
        return {
            "tool_code": tool_code,
            "tool_args": msg.get("tool_args") or {},
            "tool_data": msg.get("tool_data") or {},
            "intent": msg.get("intent"),
            "tool_status": msg.get("tool_status"),
        }
    return None


def _teacher_from_course_relation(item: dict) -> dict | None:
    teacher = item.get("teacher") if isinstance(item, dict) else None
    if not isinstance(teacher, dict):
        return None
    result = dict(teacher)
    result["relation"] = item.get("course_name") or "任课教师"
    result["course_name"] = item.get("course_name")
    result["course_id"] = item.get("course_id")
    return result


def extract_entities_from_tool_context(context: dict[str, Any] | None) -> dict[str, list[dict]]:
    """Extract reusable entities from the last tool result for follow-up turns."""
    if not context:
        return {"students": [], "teachers": [], "courses": []}
    data = context.get("tool_data") or {}
    tool_code = context.get("tool_code")
    students: list[dict] = []
    teachers: list[dict] = []
    courses: list[dict] = []

    if isinstance(data.get("student"), dict):
        students.append(data["student"])
    if isinstance(data.get("teacher"), dict):
        teachers.append(data["teacher"])
    if isinstance(data.get("counselor"), dict):
        item = dict(data["counselor"])
        item["relation"] = "班主任/辅导员"
        teachers.append(item)
    for item in data.get("course_teachers") or []:
        teacher = _teacher_from_course_relation(item)
        if teacher:
            teachers.append(teacher)
            courses.append({
                "id": item.get("course_id"),
                "name": item.get("course_name"),
                "teacher": teacher,
            })
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("student_no") or tool_code == "query_student":
            students.append(item)
        if item.get("employee_no") or tool_code == "query_teacher":
            teachers.append(item)
        if item.get("course_name") or item.get("code") or tool_code == "query_course":
            courses.append(item)

    def unique(items: list[dict], keys: tuple[str, ...]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            marker = next((item.get(key) for key in keys if item.get(key)), None)
            marker = marker or item.get("id") or item.get("name")
            if not marker or marker in seen:
                continue
            seen.add(marker)
            result.append(item)
        return result

    return {
        "students": unique(students, ("student_no", "id", "name")),
        "teachers": unique(teachers, ("employee_no", "id", "name", "email")),
        "courses": unique(courses, ("code", "id", "name", "course_name")),
    }


def recent_entities(conv: Conversation | None) -> dict[str, list[dict]]:
    aggregate = {"students": [], "teachers": [], "courses": []}
    for msg in reversed(get_messages(conv)):
        if msg.get("role") != "assistant" or not msg.get("tool_code"):
            continue
        extracted = extract_entities_from_tool_context({
            "tool_code": msg.get("tool_code"),
            "tool_data": msg.get("tool_data") or {},
        })
        for key in aggregate:
            aggregate[key].extend(extracted.get(key) or [])
        if any(aggregate.values()):
            break
    return aggregate


def clear_session(db: Session, conv: Conversation | None) -> bool:
    if not conv:
        return False
    conv.messages = []
    db.commit()
    db.refresh(conv)
    return True
