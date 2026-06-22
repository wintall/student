"""
RAG 名著问答路由
- POST /ask              提问并获得答案（含引用片段）
- GET  /books            列出所有知识库书籍
- GET  /health           健康检查（MySQL/Milvus 状态）
- 全部要求已登录用户访问
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import rag_service
from app.utils.response import success

router = APIRouter(prefix="/rag", tags=["名著问答 (RAG)"])


class AskRequest(BaseModel):
    question: str
    book_codes: Optional[List[str]] = None
    top_k: Optional[int] = None


@router.post("/ask")
def ask(body: AskRequest,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)):
    """提问，基于四大名著知识库回答"""
    result = rag_service.ask_question(
        db=db,
        question=body.question,
        book_codes=body.book_codes or None,
        top_k=body.top_k or 0,
    )
    return success(data=result)


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
