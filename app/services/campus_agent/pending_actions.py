"""Pending action helpers for assistant write operations."""
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentPendingAction
from app.models.user import OperationLog, User

PENDING_EXPIRE_MINUTES = 10


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def create_pending_action(
    db: Session,
    *,
    user: User,
    session_id: str | None,
    tool_code: str,
    args: dict,
    summary: str,
    risk: str,
) -> AgentPendingAction:
    item = AgentPendingAction(
        user_id=user.id,
        session_id=session_id,
        tool_code=tool_code,
        risk=risk,
        status="pending",
        args_json=_json_dumps(args),
        summary=summary,
        expires_at=datetime.now() + timedelta(minutes=PENDING_EXPIRE_MINUTES),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_pending_action(db: Session, action_id: int, user: User) -> AgentPendingAction | None:
    return db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == user.id,
    ).first()


def parse_action_args(action: AgentPendingAction) -> dict:
    try:
        data = json.loads(action.args_json or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_action_expired(action: AgentPendingAction) -> bool:
    return bool(action.expires_at and action.expires_at < datetime.now())


def mark_action_executed(db: Session, action: AgentPendingAction, result: dict | None = None):
    action.status = "executed"
    action.result_json = _json_dumps(result or {})
    action.executed_at = datetime.now()
    db.commit()
    db.refresh(action)


def mark_action_failed(db: Session, action: AgentPendingAction, message: str):
    action.status = "failed"
    action.error_message = message
    db.commit()
    db.refresh(action)


def mark_action_cancelled(db: Session, action: AgentPendingAction):
    action.status = "cancelled"
    db.commit()
    db.refresh(action)


def mark_action_expired(db: Session, action: AgentPendingAction):
    action.status = "expired"
    db.commit()
    db.refresh(action)


def log_agent_operation(
    db: Session,
    *,
    user: User,
    tool_code: str,
    module: str,
    action: str,
    target_id: int | None,
    detail: dict,
):
    log = OperationLog(
        user_id=user.id,
        module=module,
        action=action,
        target_id=target_id,
        detail=_json_dumps({"tool_code": tool_code, **detail}),
    )
    db.add(log)
    db.commit()
