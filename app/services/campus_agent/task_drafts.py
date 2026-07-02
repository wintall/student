"""Task draft helpers for multi-turn assistant workflows."""
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentTaskDraft
from app.models.user import User

DRAFT_EXPIRE_MINUTES = 30


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def draft_to_context(draft: AgentTaskDraft | None) -> dict | None:
    if not draft:
        return None
    return {
        "draft_id": draft.id,
        "tool_code": draft.tool_code,
        "tool_args": _json_loads(draft.args_json, {}),
        "tool_data": {
            "missing_fields": _json_loads(draft.missing_fields_json, []),
            "candidates": _json_loads(draft.candidates_json, []),
            "draft_id": draft.id,
        },
        "intent": draft.tool_code,
        "tool_status": "need_more_info",
        "mode": draft.mode,
        "module_code": draft.module_code,
    }


def is_draft_expired(draft: AgentTaskDraft) -> bool:
    return bool(draft.expires_at and draft.expires_at < datetime.now())


def get_active_draft(
    db: Session,
    *,
    user: User,
    session_id: str | None,
    module_code: str = "campus_agent",
) -> AgentTaskDraft | None:
    query = db.query(AgentTaskDraft).filter(
        AgentTaskDraft.user_id == user.id,
        AgentTaskDraft.module_code == module_code,
        AgentTaskDraft.status == "active",
    )
    if session_id:
        query = query.filter(AgentTaskDraft.session_id == session_id)
    draft = query.order_by(AgentTaskDraft.updated_at.desc(), AgentTaskDraft.id.desc()).first()
    if draft and is_draft_expired(draft):
        mark_draft_expired(db, draft)
        return None
    return draft


def upsert_task_draft(
    db: Session,
    *,
    user: User,
    session_id: str | None,
    mode: str | None,
    tool_code: str,
    args: dict,
    missing_fields: list | None = None,
    candidates: list | None = None,
    message: str | None = None,
    module_code: str = "campus_agent",
) -> AgentTaskDraft:
    draft = get_active_draft(db, user=user, session_id=session_id, module_code=module_code)
    if draft and draft.tool_code != tool_code:
        mark_draft_cancelled(db, draft)
        draft = None
    if not draft:
        draft = AgentTaskDraft(
            user_id=user.id,
            session_id=session_id,
            module_code=module_code,
            mode=mode,
            tool_code=tool_code,
            status="active",
            args_json=_json_dumps(args or {}),
            missing_fields_json=_json_dumps(missing_fields or []),
            candidates_json=_json_dumps(candidates or []),
            message=message,
            expires_at=datetime.now() + timedelta(minutes=DRAFT_EXPIRE_MINUTES),
        )
        db.add(draft)
    else:
        draft.mode = mode or draft.mode
        draft.args_json = _json_dumps(args or {})
        draft.missing_fields_json = _json_dumps(missing_fields or [])
        draft.candidates_json = _json_dumps(candidates or [])
        draft.message = message
        draft.expires_at = datetime.now() + timedelta(minutes=DRAFT_EXPIRE_MINUTES)
    db.commit()
    db.refresh(draft)
    return draft


def mark_draft_completed(db: Session, draft: AgentTaskDraft):
    draft.status = "completed"
    db.commit()
    db.refresh(draft)


def mark_draft_cancelled(db: Session, draft: AgentTaskDraft):
    draft.status = "cancelled"
    db.commit()
    db.refresh(draft)


def mark_draft_expired(db: Session, draft: AgentTaskDraft):
    draft.status = "expired"
    db.commit()
    db.refresh(draft)
