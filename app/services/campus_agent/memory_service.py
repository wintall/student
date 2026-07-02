"""Unified memory facade for assistant modules."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.agent import AgentLongTermMemory
from app.models.user import User
from app.services.campus_agent.memory import get_messages, last_tool_context, recent_tool_context
from app.services.campus_agent.task_drafts import draft_to_context, get_active_draft


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _memory_to_dict(item: AgentLongTermMemory) -> dict:
    return {
        "id": item.id,
        "module_code": item.module_code,
        "memory_type": item.memory_type,
        "content": item.content,
        "payload": _json_loads(item.payload_json, {}),
        "importance": item.importance,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
    }


@dataclass
class AgentMemoryContext:
    messages: list[dict]
    last_tool: dict | None
    recent_query_tool: dict | None
    active_draft: dict | None
    long_term: list[dict]

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "last_tool": self.last_tool,
            "recent_query_tool": self.recent_query_tool,
            "active_draft": self.active_draft,
            "long_term": self.long_term,
        }


class AgentMemoryService:
    """Common memory access layer shared by all assistant capabilities."""

    def __init__(self, db: Session):
        self.db = db

    def load_context(
        self,
        *,
        user: User,
        conversation: Conversation | None,
        session_id: str | None,
        module_code: str = "campus_agent",
    ) -> AgentMemoryContext:
        draft = get_active_draft(
            self.db,
            user=user,
            session_id=session_id,
            module_code=module_code,
        )
        return AgentMemoryContext(
            messages=get_messages(conversation),
            last_tool=last_tool_context(conversation),
            recent_query_tool=recent_tool_context(
                conversation,
                {
                    "query_student",
                    "query_teacher",
                    "query_course",
                    "query_score",
                    "query_class",
                    "query_department",
                    "query_classroom",
                    "query_term",
                    "query_announcements",
                },
            ),
            active_draft=draft_to_context(draft),
            long_term=self.recall_long_term(
                user=user,
                module_code=module_code,
                query=" ".join(
                    (msg.get("content") or "")
                    for msg in (get_messages(conversation)[-4:] if conversation else [])
                    if msg.get("role") == "user"
                ),
            ),
        )

    def recall_long_term(
        self,
        *,
        user: User,
        module_code: str,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        query_text = (query or "").strip()
        q = self.db.query(AgentLongTermMemory).filter(
            AgentLongTermMemory.user_id == user.id,
            AgentLongTermMemory.module_code == module_code,
            AgentLongTermMemory.status == "active",
        )
        if query_text:
            keywords = [part for part in query_text.replace("，", " ").replace(",", " ").split() if len(part) >= 2]
            for keyword in keywords[:3]:
                q = q.filter(AgentLongTermMemory.content.contains(keyword))
        items = q.order_by(
            AgentLongTermMemory.importance.desc(),
            AgentLongTermMemory.updated_at.desc(),
            AgentLongTermMemory.id.desc(),
        ).limit(max(1, min(limit, 20))).all()
        if items:
            now = datetime.now()
            for item in items:
                item.last_used_at = now
            self.db.commit()
        return [_memory_to_dict(item) for item in items]

    def remember_event(
        self,
        *,
        user: User,
        module_code: str,
        event_type: str,
        content: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        text = (content or "").strip()
        if not text:
            return None
        item = AgentLongTermMemory(
            user_id=user.id,
            module_code=module_code,
            memory_type=event_type or "event",
            content=text[:2000],
            payload_json=_json_dumps(payload or {}),
            importance=int((payload or {}).get("importance") or 1),
            status="active",
        )
        self.db.add(item)
        self.db.commit()
        return None
