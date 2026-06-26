"""
RAG 问答对管理路由
- POST /rag/qa-pairs           创建
- GET /rag/qa-pairs            列表查询（分页）
- GET /rag/qa-pairs/{id}       详情
- PUT /rag/qa-pairs/{id}       更新
- DELETE /rag/qa-pairs/{id}    删除
- POST /rag/qa-pairs/match     测试匹配接口
全部要求已登录用户访问
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import rag_qa_service
from app.schemas.rag_qa import QaPairCreate, QaPairUpdate
from app.schemas.common import PageParams
from app.utils.response import success, page_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/rag/qa-pairs", tags=["名著问答-问答对管理"])


@router.post("")
def create(body: QaPairCreate,
           user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """创建问答对"""
    qa = rag_qa_service.create_qa_pair(db, body)
    return success(data=qa.to_dict())


@router.get("")
def list_items(page_params: PageParams = Depends(),
               category: Optional[str] = Query(None, description="分类筛选"),
               status: Optional[int] = Query(None, description="状态筛选"),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """列表查询（分页）"""
    items = rag_qa_service.list_qa_pairs(
        db,
        keyword=page_params.keyword,
        category=category,
        status=status,
        offset=page_params.offset,
        limit=page_params.page_size,
    )
    total = rag_qa_service.count_qa_pairs(
        db,
        keyword=page_params.keyword,
        category=category,
        status=status,
    )
    page_data = {
        "items": [qa.to_dict() for qa in items],
        "total": total,
        "page": page_params.page,
        "page_size": page_params.page_size,
    }
    return page_success(data=page_data)


@router.get("/{qa_id}")
def get_item(qa_id: int = Path(..., gt=0),
             user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """获取单个问答对详情"""
    qa = rag_qa_service.get_qa_pair(db, qa_id)
    if not qa:
        return success(data=None, message="问答对不存在")
    return success(data=qa.to_dict())


@router.put("/{qa_id}")
def update(qa_id: int,
           body: QaPairUpdate,
           user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """更新问答对"""
    qa = rag_qa_service.update_qa_pair(db, qa_id, body)
    if not qa:
        return success(data=None, message="问答对不存在")
    return success(data=qa.to_dict())


@router.delete("/{qa_id}")
def delete(qa_id: int = Path(..., gt=0),
           user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """删除问答对"""
    ok = rag_qa_service.delete_qa_pair(db, qa_id)
    if not ok:
        return success(data={"deleted": False}, message="问答对不存在")
    return success(data={"deleted": True})


@router.post("/match")
def test_match(body: dict,
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """测试匹配接口（用于调试/测试）"""
    question = (body.get("question") or "").strip()
    category = body.get("category")
    top_n = int(body.get("top_n") or 3)
    if not question:
        return success(data={"matches": []})
    matches = rag_qa_service.match_qa_pairs(db, question, top_n=top_n, category=category)
    return success(data={"question": question, "matches": matches})
