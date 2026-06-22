"""
AI 智能助手路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import ai_service
from app.utils.response import success

router = APIRouter(prefix="/ai", tags=["AI 智能助手"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送消息给 AI 助手"""
    result = ai_service.chat(user, body.message, db)
    return success(data=result)


@router.post("/clear")
def clear_context(user: User = Depends(get_current_user)):
    """清空当前用户的对话上下文"""
    ai_service.clear_context(user.id)
    return success(message="对话上下文已清空")
