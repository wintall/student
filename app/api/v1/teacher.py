"""
教职工路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import teacher_service
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, teacher_to_dict

router = APIRouter(prefix="/teachers", tags=["教职工管理"])


@router.post("")
def create(body: TeacherCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = teacher_service.create_teacher(body, db)
    return success(data={"id": t.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    department_id: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = teacher_service.list_teachers(params, db, department_id)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), teacher_to_dict)
    return page_success(result)


@router.get("/{teacher_id}")
def get(teacher_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = teacher_service.get_teacher(teacher_id, db)
    return success(data=teacher_to_dict(t))


@router.put("/{teacher_id}")
def update(teacher_id: int, body: TeacherUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = teacher_service.update_teacher(teacher_id, body, db)
    return success(data={"id": t.id})


@router.delete("/{teacher_id}")
def delete(teacher_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    teacher_service.delete_teacher(teacher_id, db)
    return success(message="删除成功")
