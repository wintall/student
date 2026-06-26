"""Short-term memory helpers for the campus assistant."""
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.user import User

MAX_MESSAGES = 20


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
            "tool_args": tool_args or {},
            "tool_status": tool_status,
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
                "intent": msg.get("intent"),
                "tool_status": msg.get("tool_status"),
            }
    return None


def clear_session(db: Session, conv: Conversation | None) -> bool:
    if not conv:
        return False
    conv.messages = []
    db.commit()
    db.refresh(conv)
    return True
