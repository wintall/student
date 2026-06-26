"""
Attendance module routes.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.schemas.attendance import AttendanceRecordCreate, AttendanceRecordUpdate
from app.schemas.common import PageParams
from app.services import attendance_service
from app.utils.entity_mappers import attendance_record_to_dict, map_entities
from app.utils.pagination import paginate
from app.utils.response import page_success, success

router = APIRouter(prefix="/attendance", tags=["请假考勤"])


@router.get("/my")
def list_my(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attendance:my:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = attendance_service.list_my_attendance(user, params, db, status, start_date, end_date)
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), attendance_record_to_dict)
    return page_success(result)


@router.get("/students")
def list_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    department_id: int = Query(None),
    clazz_id: int = Query(None),
    student_id: int = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attendance:student:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = attendance_service.list_student_attendance(
        user, params, db, status, start_date, end_date, department_id, clazz_id, student_id
    )
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), attendance_record_to_dict)
    return page_success(result)


@router.get("/teachers")
def list_teachers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    start_date: date = Query(None),
    end_date: date = Query(None),
    department_id: int = Query(None),
    teacher_id: int = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attendance:teacher:list")),
):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    q = attendance_service.list_teacher_attendance(
        user, params, db, status, start_date, end_date, department_id, teacher_id
    )
    result = paginate(q, params)
    result["items"] = map_entities(result.get("items", []), attendance_record_to_dict)
    return page_success(result)


@router.get("/candidates/students")
def student_candidates(
    keyword: str = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attendance:student:create")),
):
    students = attendance_service.list_student_candidates(user, db, keyword, limit)
    items = []
    for student in students:
        clazz = getattr(student, "clazz", None)
        department = getattr(clazz, "department", None) if clazz else None
        items.append({
            "id": student.id,
            "name": student.name,
            "student_no": student.student_no,
            "user_id": student.user_id,
            "clazz_id": student.clazz_id,
            "clazz_name": getattr(clazz, "name", "") if clazz else "",
            "department_id": getattr(department, "id", None) if department else None,
            "department_name": getattr(department, "name", "") if department else "",
        })
    return success(data=items)


@router.get("/candidates/teachers")
def teacher_candidates(
    keyword: str = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attendance:teacher:create")),
):
    teachers = attendance_service.list_teacher_candidates(user, db, keyword, limit)
    items = []
    for teacher in teachers:
        department = getattr(teacher, "department", None)
        items.append({
            "id": teacher.id,
            "name": teacher.name,
            "employee_no": teacher.employee_no,
            "user_id": teacher.user_id,
            "department_id": teacher.department_id,
            "department_name": getattr(department, "name", "") if department else "",
        })
    return success(data=items)


@router.post("")
def create(
    body: AttendanceRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(["attendance:student:create", "attendance:teacher:create"])),
):
    record = attendance_service.create_attendance_record(user, body, db)
    return success(data=attendance_record_to_dict(record), message="创建成功")


@router.get("/{record_id}")
def get(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("attendance:my:list")),
):
    record = attendance_service.get_attendance_record_for_manager(user, record_id, db)
    return success(data=attendance_record_to_dict(record))


@router.put("/{record_id}")
def update(
    record_id: int,
    body: AttendanceRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(["attendance:student:update", "attendance:teacher:update"])),
):
    record = attendance_service.update_attendance_record(user, record_id, body, db)
    return success(data=attendance_record_to_dict(record), message="更新成功")


@router.delete("/{record_id}")
def delete(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(["attendance:student:delete", "attendance:teacher:delete"])),
):
    attendance_service.delete_attendance_record(user, record_id, db)
    return success(message="删除成功")
