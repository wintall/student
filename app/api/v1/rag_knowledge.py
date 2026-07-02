from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.rag_knowledge import (
    KnowledgeAskRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeSearchRequest,
    PathImportRequest,
    TextImportRequest,
)
from app.services import rag_knowledge_service
from app.utils.response import success

router = APIRouter(prefix="/rag/knowledge", tags=["综合知识库 RAG"])


@router.post("/bases")
def create_base(body: KnowledgeBaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    kb = rag_knowledge_service.create_kb(db, user, body)
    return success(data=rag_knowledge_service.kb_to_dict(kb))


@router.get("/bases")
def list_bases(
    keyword: Optional[str] = Query(None),
    include_public: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(data=rag_knowledge_service.list_kbs(db, user, keyword, include_public))


@router.put("/bases/{kb_id}")
def update_base(kb_id: int, body: KnowledgeBaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    kb = rag_knowledge_service.update_kb(db, user, kb_id, body)
    return success(data=rag_knowledge_service.kb_to_dict(kb))


@router.delete("/bases/{kb_id}")
def delete_base(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.delete_kb(db, user, kb_id), message="删除成功")


@router.get("/bases/{kb_id}/documents")
def list_documents(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.list_documents(db, user, kb_id))


@router.get("/bases/{kb_id}/detail")
def base_detail(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.kb_detail(db, user, kb_id))


@router.post("/bases/{kb_id}/evaluate")
def evaluate_base(kb_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.evaluate_kb(db, user, kb_id), message="评估完成")


@router.post("/documents/text")
def import_text(body: TextImportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = rag_knowledge_service.import_text(db, user, body.kb_id, body.title, body.text)
    return success(data=rag_knowledge_service.doc_to_dict(doc), message="导入成功")


@router.post("/documents/path")
def import_path(body: PathImportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = rag_knowledge_service.import_path(db, user, body.kb_id, body.path, body.title)
    return success(data=rag_knowledge_service.doc_to_dict(doc), message="导入成功")


@router.post("/documents/upload")
def import_upload(
    kb_id: int = Form(...),
    title: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = rag_knowledge_service.import_upload(db, user, kb_id, file, title)
    return success(data=rag_knowledge_service.doc_to_dict(doc), message="导入成功")


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.delete_document(db, user, document_id), message="删除成功")


@router.post("/search")
def search(body: KnowledgeSearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.search(db, user, body.question, body.kb_ids, body.top_k, body.min_score))


@router.post("/ask")
def ask(body: KnowledgeAskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.answer(db, user, body.question, body.kb_ids, body.top_k, body.min_score))


@router.get("/health")
def health(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return success(data=rag_knowledge_service.health(db))
