"""
Attendance module service.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import get_user_role_codes
from app.exceptions import BusinessException, NotFoundError, PermissionDenied
from app.models.attendance import AttendanceRecord
from app.models.clazz import Clazz
from app.models.leave import LeaveRequest
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.attendance import AttendanceRecordCreate, AttendanceRecordUpdate
from app.schemas.common import PageParams

DEPARTMENT_MANAGE_ROLES = {"department_admin", "staff_dean"}
COUNSELOR_MANAGE_ROLES = {"counselor", "staff_counselor"}


def _query_base(db: Session):
    return db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.user),
        joinedload(AttendanceRecord.student),
        joinedload(AttendanceRecord.teacher),
        joinedload(AttendanceRecord.clazz),
        joinedload(AttendanceRecord.department),
        joinedload(AttendanceRecord.course_schedule),
        joinedload(AttendanceRecord.leave_request),
        joinedload(AttendanceRecord.creator),
        joinedload(AttendanceRecord.updater),
    ).filter(AttendanceRecord.is_deleted == False)


def _current_student(user: User, db: Session) -> Optional[Student]:
    return db.query(Student).options(joinedload(Student.clazz).joinedload(Clazz.department)).filter(
        Student.user_id == user.id,
        Student.is_deleted == False,
    ).first()


def _current_teacher(user: User, db: Session) -> Optional[Teacher]:
    return db.query(Teacher).filter(
        Teacher.user_id == user.id,
        Teacher.is_deleted == False,
    ).first()


def _managed_student_filters(user: User, db: Session):
    role_codes = get_user_role_codes(user, db)
    if "admin" in role_codes:
        return [], "admin"

    teacher = _current_teacher(user, db)
    conditions = []
    scope = None

    if teacher and role_codes & DEPARTMENT_MANAGE_ROLES and teacher.department_id:
        conditions.append(AttendanceRecord.department_id == teacher.department_id)
        scope = "department"

    if teacher and role_codes & COUNSELOR_MANAGE_ROLES:
        clazz_ids = [
            row[0]
            for row in db.query(Clazz.id).filter(
                Clazz.counselor_id == teacher.id,
                Clazz.is_deleted == False,
            ).all()
        ]
        if clazz_ids:
            conditions.append(AttendanceRecord.clazz_id.in_(clazz_ids))
            scope = scope or "clazz"

    if not conditions:
        raise PermissionDenied("无可管理的学生考勤范围")

    return conditions, scope or "student_manager"


def _managed_teacher_filters(user: User, db: Session):
    role_codes = get_user_role_codes(user, db)
    if "admin" in role_codes:
        return [], "admin"

    teacher = _current_teacher(user, db)
    if teacher and role_codes & DEPARTMENT_MANAGE_ROLES and teacher.department_id:
        return [AttendanceRecord.department_id == teacher.department_id], "department"

    raise PermissionDenied("无可管理的教职工考勤范围")


def _resolve_person(data: AttendanceRecordCreate, db: Session) -> dict:
    if data.person_type == "student":
        student = None
        if data.student_id:
            student = db.query(Student).options(joinedload(Student.clazz)).filter(
                Student.id == data.student_id,
                Student.is_deleted == False,
            ).first()
        elif data.user_id:
            student = db.query(Student).options(joinedload(Student.clazz)).filter(
                Student.user_id == data.user_id,
                Student.is_deleted == False,
            ).first()
        if not student:
            raise BusinessException(message="未找到学生信息")
        clazz = student.clazz
        return {
            "person_type": "student",
            "user_id": student.user_id,
            "student_id": student.id,
            "teacher_id": None,
            "clazz_id": student.clazz_id,
            "department_id": clazz.department_id if clazz else None,
        }

    if data.person_type == "teacher":
        teacher = None
        if data.teacher_id:
            teacher = db.query(Teacher).filter(
                Teacher.id == data.teacher_id,
                Teacher.is_deleted == False,
            ).first()
        elif data.user_id:
            teacher = db.query(Teacher).filter(
                Teacher.user_id == data.user_id,
                Teacher.is_deleted == False,
            ).first()
        if not teacher:
            raise BusinessException(message="未找到教职工信息")
        return {
            "person_type": "teacher",
            "user_id": teacher.user_id,
            "student_id": None,
            "teacher_id": teacher.id,
            "clazz_id": None,
            "department_id": teacher.department_id,
        }

    raise BusinessException(message="考勤人员类型不正确")


def _ensure_can_manage_record(user: User, person_type: str, target: dict, db: Session):
    role_codes = get_user_role_codes(user, db)
    if "admin" in role_codes:
        return

    teacher = _current_teacher(user, db)
    if not teacher:
        raise PermissionDenied("无权管理考勤")

    if person_type == "student":
        if role_codes & DEPARTMENT_MANAGE_ROLES and teacher.department_id and target.get("department_id") == teacher.department_id:
            return
        if role_codes & COUNSELOR_MANAGE_ROLES and target.get("clazz_id"):
            exists = db.query(Clazz.id).filter(
                Clazz.id == target["clazz_id"],
                Clazz.counselor_id == teacher.id,
                Clazz.is_deleted == False,
            ).first()
            if exists:
                return
        raise PermissionDenied("无权管理该学生考勤")

    if person_type == "teacher":
        if role_codes & DEPARTMENT_MANAGE_ROLES and teacher.department_id and target.get("department_id") == teacher.department_id:
            return
        raise PermissionDenied("无权管理该教职工考勤")


def _apply_filters(
    q,
    *,
    params: PageParams,
    person_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    department_id: Optional[int] = None,
    clazz_id: Optional[int] = None,
    student_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
):
    if person_type:
        q = q.filter(AttendanceRecord.person_type == person_type)
    if status:
        q = q.filter(AttendanceRecord.status == status)
    if start_date:
        q = q.filter(AttendanceRecord.attendance_date >= start_date)
    if end_date:
        q = q.filter(AttendanceRecord.attendance_date <= end_date)
    if department_id:
        q = q.filter(AttendanceRecord.department_id == department_id)
    if clazz_id:
        q = q.filter(AttendanceRecord.clazz_id == clazz_id)
    if student_id:
        q = q.filter(AttendanceRecord.student_id == student_id)
    if teacher_id:
        q = q.filter(AttendanceRecord.teacher_id == teacher_id)
    if params.keyword:
        keyword = params.keyword
        q = q.outerjoin(Student, Student.id == AttendanceRecord.student_id).outerjoin(
            Teacher, Teacher.id == AttendanceRecord.teacher_id
        ).outerjoin(User, User.id == AttendanceRecord.user_id).filter(
            or_(
                Student.name.contains(keyword),
                Student.student_no.contains(keyword),
                Teacher.name.contains(keyword),
                Teacher.employee_no.contains(keyword),
                User.real_name.contains(keyword),
                User.username.contains(keyword),
                AttendanceRecord.remark.contains(keyword),
            )
        )
    return q


def list_my_attendance(
    user: User,
    params: PageParams,
    db: Session,
    status: str = None,
    start_date: date = None,
    end_date: date = None,
):
    q = _query_base(db).filter(AttendanceRecord.user_id == user.id)
    q = _apply_filters(q, params=params, status=status, start_date=start_date, end_date=end_date)
    return q.order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())


def list_student_attendance(
    user: User,
    params: PageParams,
    db: Session,
    status: str = None,
    start_date: date = None,
    end_date: date = None,
    department_id: int = None,
    clazz_id: int = None,
    student_id: int = None,
):
    conditions, _ = _managed_student_filters(user, db)
    q = _query_base(db).filter(AttendanceRecord.person_type == "student")
    if conditions:
        q = q.filter(or_(*conditions))
    q = _apply_filters(
        q,
        params=params,
        status=status,
        start_date=start_date,
        end_date=end_date,
        department_id=department_id,
        clazz_id=clazz_id,
        student_id=student_id,
    )
    return q.order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())


def list_teacher_attendance(
    user: User,
    params: PageParams,
    db: Session,
    status: str = None,
    start_date: date = None,
    end_date: date = None,
    department_id: int = None,
    teacher_id: int = None,
):
    conditions, _ = _managed_teacher_filters(user, db)
    q = _query_base(db).filter(AttendanceRecord.person_type == "teacher")
    if conditions:
        q = q.filter(or_(*conditions))
    q = _apply_filters(
        q,
        params=params,
        status=status,
        start_date=start_date,
        end_date=end_date,
        department_id=department_id,
        teacher_id=teacher_id,
    )
    return q.order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())


def list_student_candidates(user: User, db: Session, keyword: str = None, limit: int = 20):
    role_codes = get_user_role_codes(user, db)
    q = db.query(Student).options(
        joinedload(Student.clazz).joinedload(Clazz.department),
        joinedload(Student.user),
    ).filter(Student.is_deleted == False)

    if "admin" not in role_codes:
        teacher = _current_teacher(user, db)
        conditions = []
        if teacher and role_codes & DEPARTMENT_MANAGE_ROLES and teacher.department_id:
            q = q.join(Clazz, Clazz.id == Student.clazz_id)
            conditions.append(Clazz.department_id == teacher.department_id)
        if teacher and role_codes & COUNSELOR_MANAGE_ROLES:
            clazz_ids = [
                row[0]
                for row in db.query(Clazz.id).filter(
                    Clazz.counselor_id == teacher.id,
                    Clazz.is_deleted == False,
                ).all()
            ]
            if clazz_ids:
                conditions.append(Student.clazz_id.in_(clazz_ids))
        if not conditions:
            raise PermissionDenied("无可管理的学生考勤范围")
        q = q.filter(or_(*conditions))

    if keyword:
        q = q.filter(or_(Student.name.contains(keyword), Student.student_no.contains(keyword)))
    return q.order_by(Student.student_no.asc()).limit(max(1, min(limit, 50))).all()


def list_teacher_candidates(user: User, db: Session, keyword: str = None, limit: int = 20):
    role_codes = get_user_role_codes(user, db)
    q = db.query(Teacher).options(
        joinedload(Teacher.department),
        joinedload(Teacher.user),
    ).filter(Teacher.is_deleted == False)

    if "admin" not in role_codes:
        teacher = _current_teacher(user, db)
        if not (teacher and role_codes & DEPARTMENT_MANAGE_ROLES and teacher.department_id):
            raise PermissionDenied("无可管理的教职工考勤范围")
        q = q.filter(Teacher.department_id == teacher.department_id)

    if keyword:
        q = q.filter(or_(Teacher.name.contains(keyword), Teacher.employee_no.contains(keyword)))
    return q.order_by(Teacher.employee_no.asc()).limit(max(1, min(limit, 50))).all()


def _find_duplicate(data: dict, attendance_date: date, period_type: str, course_schedule_id: Optional[int], db: Session):
    q = db.query(AttendanceRecord).filter(
        AttendanceRecord.is_deleted == False,
        AttendanceRecord.user_id == data["user_id"],
        AttendanceRecord.attendance_date == attendance_date,
        AttendanceRecord.period_type == period_type,
    )
    if course_schedule_id is None:
        q = q.filter(AttendanceRecord.course_schedule_id == None)
    else:
        q = q.filter(AttendanceRecord.course_schedule_id == course_schedule_id)
    return q.first()


def create_attendance_record(user: User, data: AttendanceRecordCreate, db: Session) -> AttendanceRecord:
    target = _resolve_person(data, db)
    _ensure_can_manage_record(user, data.person_type, target, db)
    duplicate = _find_duplicate(target, data.attendance_date, data.period_type, data.course_schedule_id, db)
    if duplicate:
        raise BusinessException(message="该人员当天同一时段已有考勤记录")

    record = AttendanceRecord(
        **target,
        attendance_date=data.attendance_date,
        period_type=data.period_type,
        course_schedule_id=data.course_schedule_id,
        checkin_time=data.checkin_time,
        checkout_time=data.checkout_time,
        status=data.status,
        source="manual",
        remark=data.remark,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return get_attendance_record_for_manager(user, record.id, db)


def get_attendance_record(record_id: int, db: Session) -> AttendanceRecord:
    record = _query_base(db).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise NotFoundError("考勤记录不存在")
    return record


def get_attendance_record_for_manager(user: User, record_id: int, db: Session) -> AttendanceRecord:
    record = get_attendance_record(record_id, db)
    if record.user_id == user.id:
        return record
    _ensure_can_manage_record(user, record.person_type, {
        "department_id": record.department_id,
        "clazz_id": record.clazz_id,
    }, db)
    return record


def update_attendance_record(user: User, record_id: int, data: AttendanceRecordUpdate, db: Session) -> AttendanceRecord:
    record = get_attendance_record(record_id, db)
    _ensure_can_manage_record(user, record.person_type, {
        "department_id": record.department_id,
        "clazz_id": record.clazz_id,
    }, db)

    update_data = data.model_dump(exclude_unset=True)
    next_date = update_data.get("attendance_date", record.attendance_date)
    next_period = update_data.get("period_type", record.period_type)
    next_schedule = update_data.get("course_schedule_id", record.course_schedule_id)
    duplicate = _find_duplicate(
        {"user_id": record.user_id},
        next_date,
        next_period,
        next_schedule,
        db,
    )
    if duplicate and duplicate.id != record.id:
        raise BusinessException(message="该人员当天同一时段已有考勤记录")

    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_by = user.id
    db.commit()
    db.refresh(record)
    return get_attendance_record(record.id, db)


def delete_attendance_record(user: User, record_id: int, db: Session):
    record = get_attendance_record(record_id, db)
    _ensure_can_manage_record(user, record.person_type, {
        "department_id": record.department_id,
        "clazz_id": record.clazz_id,
    }, db)
    record.soft_delete()
    record.updated_by = user.id
    db.commit()


def sync_leave_to_attendance(leave_request: LeaveRequest, reviewer: User, db: Session):
    """Create leave attendance records after leave approval."""
    if leave_request.status != "approved":
        return
    if not leave_request.start_time or not leave_request.end_time:
        return

    current = leave_request.start_time.date()
    end = leave_request.end_time.date()
    while current <= end:
        target = {
            "person_type": leave_request.applicant_type,
            "user_id": leave_request.applicant_user_id,
            "student_id": leave_request.student_id,
            "teacher_id": leave_request.teacher_id,
            "clazz_id": leave_request.clazz_id,
            "department_id": leave_request.department_id,
        }
        duplicate = _find_duplicate(target, current, "day", None, db)
        if duplicate:
            if duplicate.source == "leave_sync" or duplicate.status in {"absent", "manual"}:
                duplicate.status = "leave"
                duplicate.source = "leave_sync"
                duplicate.leave_request_id = leave_request.id
                duplicate.remark = f"请假自动同步：{leave_request.reason[:120]}"
                duplicate.updated_by = reviewer.id
        else:
            db.add(AttendanceRecord(
                **target,
                attendance_date=current,
                period_type="day",
                status="leave",
                source="leave_sync",
                leave_request_id=leave_request.id,
                remark=f"请假自动同步：{leave_request.reason[:120]}",
                created_by=reviewer.id,
                updated_by=reviewer.id,
            ))
        current = current + timedelta(days=1)
