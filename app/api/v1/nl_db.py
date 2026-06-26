"""
自然语言数据库操作 API 路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.services import nl_db_service
from app.utils.response import success

router = APIRouter(prefix="/nl-db", tags=["自然语言数据库操作"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    has_data: bool


@router.post("/chat")
def chat(
    body: ChatRequest,
    user: User = Depends(require_permission("nl-db:access")),
    db: Session = Depends(get_db),
):
    """自然语言数据库操作 - 发送消息"""
    result = nl_db_service.chat(user, body.message, db)
    return success(data={
        "reply": result["reply"],
        "has_data": result["has_data"],
        "tool_calls": result.get("tool_calls", []),
        "tool_results": result.get("tool_results", []),
    })


@router.get("/history")
def get_history(user: User = Depends(require_permission("nl-db:access"))):
    """获取对话历史"""
    result = nl_db_service.get_history(user.id)
    return success(data=result)


@router.delete("/history")
def clear_history(user: User = Depends(require_permission("nl-db:access"))):
    """清除对话历史"""
    result = nl_db_service.clear_history(user.id)
    return success(message=result["message"])
