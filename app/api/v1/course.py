"""
课程路由
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.services import course_service
from app.schemas.course import CourseCreate, CourseUpdate
from app.schemas.common import PageParams
from app.utils.pagination import paginate
from app.utils.response import success, page_success
from app.utils.entity_mappers import map_entities, course_to_dict

router = APIRouter(prefix="/courses", tags=["课程管理"])


@router.post("")
def create(body: CourseCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:course:create"))):
    c = course_service.create_course(body, db)
    return success(data={"id": c.id})


@router.get("")
def list_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    department_id: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("teaching:course:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = course_service.list_courses(params, db, department_id)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), course_to_dict)
    return page_success(result)


@router.get("/{course_id}")
def get(course_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:course:list"))):
    c = course_service.get_course(course_id, db)
    return success(data=course_to_dict(c))


@router.put("/{course_id}")
def update(course_id: int, body: CourseUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:course:update"))):
    c = course_service.update_course(course_id, body, db)
    return success(data={"id": c.id})


@router.delete("/{course_id}")
def delete(course_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("teaching:course:delete"))):
    course_service.delete_course(course_id, db)
    return success(message="删除成功")
