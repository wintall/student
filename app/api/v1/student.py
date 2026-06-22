"""
学生路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import student_service
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import student_to_dict, map_entities

router = APIRouter(prefix="/students", tags=["学生管理"])


@router.post("")
def create(body: StudentCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = student_service.create_student(body, db)
    return success(data={"id": s.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    clazz_id: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = student_service.list_students(params, db, clazz_id)
    result = paginate(q, params)
    # 将 ORM 对象转换为前端可读的扁平 dict
    result["items"] = map_entities(result.get("items", []), student_to_dict)
    return page_success(result)


@router.get("/{student_id}")
def get(student_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = student_service.get_student(student_id, db)
    return success(data=student_to_dict(s))


@router.put("/{student_id}")
def update(student_id: int, body: StudentUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = student_service.update_student(student_id, body, db)
    return success(data={"id": s.id})


@router.delete("/{student_id}")
def delete(student_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    student_service.delete_student(student_id, db)
    return success(message="删除成功")
