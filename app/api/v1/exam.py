"""
考试路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import exam_service
from app.schemas.exam import ExamCreate, ExamUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, exam_to_dict

router = APIRouter(prefix="/exams", tags=["考试管理"])


@router.post("")
def create(body: ExamCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    e = exam_service.create_exam(body, db)
    return success(data={"id": e.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    course_id: int = Query(None),
    clazz_id: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = exam_service.list_exams(params, db, course_id, clazz_id)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), exam_to_dict)
    return page_success(result)


@router.get("/{exam_id}")
def get(exam_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    e = exam_service.get_exam(exam_id, db)
    return success(data=exam_to_dict(e))


@router.put("/{exam_id}")
def update(exam_id: int, body: ExamUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    e = exam_service.update_exam(exam_id, body, db)
    return success(data={"id": e.id})


@router.delete("/{exam_id}")
def delete(exam_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    exam_service.delete_exam(exam_id, db)
    return success(message="删除成功")
