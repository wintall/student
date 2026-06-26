"""
Routes for terms, classrooms and course schedules.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.schemas.common import PageParams
from app.schemas.schedule import (
    ClassroomCreate,
    ClassroomUpdate,
    CourseScheduleCreate,
    CourseScheduleUpdate,
    TermCreate,
    TermUpdate,
)
from app.services import schedule_service
from app.utils.entity_mappers import (
    classroom_to_dict,
    course_schedule_to_dict,
    map_entities,
    term_to_dict,
)
from app.utils.pagination import paginate
from app.utils.response import page_success, success

router = APIRouter(tags=["排课管理"])


@router.post("/terms")
def create_term(
    body: TermCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("academic-calendar:term:create")),
):
    term = schedule_service.create_term(body, db)
    return success(data=term_to_dict(term), message="创建成功")


@router.get("/terms")
def list_terms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("academic-calendar:term:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = schedule_service.list_terms(params, db, status)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), term_to_dict)
    return page_success(result)


@router.get("/terms/{term_id}")
def get_term(
    term_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("academic-calendar:term:list")),
):
    term = schedule_service.get_term(term_id, db)
    return success(data=term_to_dict(term))


@router.put("/terms/{term_id}")
def update_term(
    term_id: int,
    body: TermUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("academic-calendar:term:update")),
):
    term = schedule_service.update_term(term_id, body, db)
    return success(data=term_to_dict(term), message="更新成功")


@router.delete("/terms/{term_id}")
def delete_term(
    term_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("academic-calendar:term:delete")),
):
    schedule_service.delete_term(term_id, db)
    return success(message="删除成功")


@router.post("/classrooms")
def create_classroom(
    body: ClassroomCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:classroom:create")),
):
    classroom = schedule_service.create_classroom(body, db)
    return success(data=classroom_to_dict(classroom), message="创建成功")


@router.get("/classrooms")
def list_classrooms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: int = Query(None),
    room_type: str = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:classroom:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = schedule_service.list_classrooms(params, db, status, room_type)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), classroom_to_dict)
    return page_success(result)


@router.get("/classrooms/{classroom_id}")
def get_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:classroom:list")),
):
    classroom = schedule_service.get_classroom(classroom_id, db)
    return success(data=classroom_to_dict(classroom))


@router.put("/classrooms/{classroom_id}")
def update_classroom(
    classroom_id: int,
    body: ClassroomUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:classroom:update")),
):
    classroom = schedule_service.update_classroom(classroom_id, body, db)
    return success(data=classroom_to_dict(classroom), message="更新成功")


@router.delete("/classrooms/{classroom_id}")
def delete_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:classroom:delete")),
):
    schedule_service.delete_classroom(classroom_id, db)
    return success(message="删除成功")


@router.post("/course-schedules")
def create_course_schedule(
    body: CourseScheduleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:timetable:create")),
):
    schedule = schedule_service.create_course_schedule(body, db)
    return success(data=course_schedule_to_dict(schedule), message="创建成功")


@router.get("/course-schedules")
def list_course_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    term_id: int = Query(None),
    course_id: int = Query(None),
    clazz_id: int = Query(None),
    teacher_id: int = Query(None),
    classroom_id: int = Query(None),
    weekday: int = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:timetable:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = schedule_service.list_course_schedules(
        params, db, term_id, course_id, clazz_id, teacher_id, classroom_id, weekday
    )
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), course_schedule_to_dict)
    return page_success(result)


@router.get("/course-schedules/my")
def list_my_course_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    keyword: str = Query(None),
    term_id: int = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("schedule:my:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = schedule_service.list_my_course_schedules(user, params, db, term_id)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), course_schedule_to_dict)
    return page_success(result)


@router.get("/course-schedules/{schedule_id}")
def get_course_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:timetable:list")),
):
    schedule = schedule_service.get_course_schedule(schedule_id, db)
    return success(data=course_schedule_to_dict(schedule))


@router.put("/course-schedules/{schedule_id}")
def update_course_schedule(
    schedule_id: int,
    body: CourseScheduleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:timetable:update")),
):
    schedule = schedule_service.update_course_schedule(schedule_id, body, db)
    return success(data=course_schedule_to_dict(schedule), message="更新成功")


@router.delete("/course-schedules/{schedule_id}")
def delete_course_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("schedule:timetable:delete")),
):
    schedule_service.delete_course_schedule(schedule_id, db)
    return success(message="删除成功")
