"""
RAG 名著问答路由
- POST /ask              提问并获得答案（含引用片段）
- POST /chat             带记忆的对话提问
- GET  /conversations    获取对话列表
- GET  /conversation/{session_id} 获取对话详情
- DELETE /conversation/{session_id} 删除对话
- POST /conversation/{session_id}/clear 清空对话历史
- GET  /books            列出所有知识库书籍
- GET  /health           健康检查（MySQL/Milvus 状态）
- 全部要求已登录用户访问
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import rag_service, conversation_service
from app.utils.response import success

router = APIRouter(prefix="/rag", tags=["名著问答 (RAG)"])


class AskRequest(BaseModel):
    question: str
    book_codes: Optional[List[str]] = None
    top_k: Optional[int] = None


class ChatRequest(BaseModel):
    question: str
    session_id: str
    book_codes: Optional[List[str]] = None
    top_k: Optional[int] = None


@router.post("/ask")
def ask(body: AskRequest,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)):
    """提问，基于四大名著知识库回答（无记忆）"""
    result = rag_service.ask_question(
        db=db,
        question=body.question,
        book_codes=body.book_codes or None,
        top_k=body.top_k or 0,
    )
    return success(data=result)


@router.post("/chat")
def chat(body: ChatRequest,
         user: User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    """带记忆的对话提问"""
    result = conversation_service.ask_with_memory(
        db=db,
        session_id=body.session_id,
        question=body.question,
        book_codes=body.book_codes or None,
        top_k=body.top_k or 0,
    )
    return success(data=result)


@router.post("/session")
def create_session(user: User = Depends(get_current_user)):
    """创建新会话"""
    session_id = conversation_service.create_session()
    return success(data={"session_id": session_id})


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db),
                       limit: int = 20):
    """获取对话列表"""
    convs = conversation_service.list_conversations(db, user.id, limit)
    data = [c.to_dict() for c in convs]
    return success(data=data)


@router.get("/conversation/{session_id}")
def get_conversation(session_id: str = Path(...),
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """获取对话详情"""
    conv = conversation_service.get_conversation(db, session_id)
    if conv:
        return success(data=conv.to_dict())
    return success(data=None, message="对话不存在")


@router.delete("/conversation/{session_id}")
def delete_conversation(session_id: str = Path(...),
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """删除对话"""
    success_flag = conversation_service.delete_conversation(db, session_id)
    return success(data={"deleted": success_flag})


@router.post("/conversation/{session_id}/clear")
def clear_conversation(session_id: str = Path(...),
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """清空对话历史"""
    success_flag = conversation_service.clear_conversation(db, session_id)
    return success(data={"cleared": success_flag})


@router.get("/conversation/{session_id}/history")
def get_conversation_history(session_id: str = Path(...),
                             user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """获取对话历史消息"""
    history = conversation_service.get_conversation_history(db, session_id)
    return success(data=history)


@router.post("/search")
def search(body: AskRequest,
           user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """仅检索（不生成 LLM 答案），返回参考段落"""
    result = rag_service.retrieve(
        db=db,
        question=body.question,
        book_codes=body.book_codes or None,
        top_k=body.top_k or 0,
    )
    return success(data=result)


@router.get("/books")
def list_books(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """列出所有书籍"""
    data = rag_service.list_books(db)
    return success(data=data)


@router.get("/health")
def health(user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """健康检查：MySQL / Milvus 状态"""
    data = rag_service.health_check(db)
    return success(data=data)
