"""
Services for terms, classrooms and course schedules.
"""
from datetime import date
from typing import Optional

from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session, joinedload

from app.exceptions import BusinessException, NotFoundError
from app.models.clazz import Clazz
from app.models.course import Course
from app.models.schedule import Classroom, CourseSchedule, Term
from app.models.student import Student
from app.models.teacher import Teacher
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

VALID_WEEK_TYPES = {"all", "odd", "even"}
VALID_SCHEDULE_TYPES = {"normal", "makeup", "temporary"}


def _validate_term_dates(start_date: date, end_date: date):
    if end_date < start_date:
        raise BusinessException(message="结束日期不能早于开始日期")


def _set_current_term(term: Term, db: Session):
    if term.is_current:
        db.query(Term).filter(Term.id != term.id, Term.is_deleted == False).update({"is_current": False})


def create_term(data: TermCreate, db: Session) -> Term:
    _validate_term_dates(data.start_date, data.end_date)
    exists = db.query(Term).filter(
        Term.academic_year == data.academic_year,
        Term.semester == data.semester,
        Term.is_deleted == False,
    ).first()
    if exists:
        raise BusinessException(message="该学年学期已存在")
    term = Term(**data.model_dump())
    db.add(term)
    db.flush()
    _set_current_term(term, db)
    db.commit()
    db.refresh(term)
    return term


def get_term(term_id: int, db: Session) -> Term:
    term = db.query(Term).filter(Term.id == term_id, Term.is_deleted == False).first()
    if not term:
        raise NotFoundError("学期不存在")
    return term


def update_term(term_id: int, data: TermUpdate, db: Session) -> Term:
    term = get_term(term_id, db)
    payload = data.model_dump(exclude_unset=True)
    academic_year = payload.get("academic_year", term.academic_year)
    semester = payload.get("semester", term.semester)
    exists = db.query(Term).filter(
        Term.id != term.id,
        Term.academic_year == academic_year,
        Term.semester == semester,
        Term.is_deleted == False,
    ).first()
    if exists:
        raise BusinessException(message="该学年学期已存在")
    start_date = payload.get("start_date", term.start_date)
    end_date = payload.get("end_date", term.end_date)
    _validate_term_dates(start_date, end_date)
    for key, value in payload.items():
        setattr(term, key, value)
    _set_current_term(term, db)
    db.commit()
    db.refresh(term)
    return term


def delete_term(term_id: int, db: Session):
    term = get_term(term_id, db)
    if db.query(CourseSchedule).filter(CourseSchedule.term_id == term.id, CourseSchedule.is_deleted == False).first():
        raise BusinessException(message="该学期已有课表，不能删除")
    term.soft_delete()
    db.commit()


def list_terms(params: PageParams, db: Session, status: Optional[int] = None):
    q = db.query(Term).filter(Term.is_deleted == False)
    if status is not None:
        q = q.filter(Term.status == status)
    if params.keyword:
        q = q.filter(or_(Term.name.contains(params.keyword), Term.academic_year.contains(params.keyword)))
    return q.order_by(Term.start_date.desc(), Term.semester.desc())


def create_classroom(data: ClassroomCreate, db: Session) -> Classroom:
    if db.query(Classroom).filter(Classroom.name == data.name, Classroom.is_deleted == False).first():
        raise BusinessException(message="教室名称已存在")
    classroom = Classroom(**data.model_dump())
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


def get_classroom(classroom_id: int, db: Session) -> Classroom:
    classroom = db.query(Classroom).filter(
        Classroom.id == classroom_id,
        Classroom.is_deleted == False,
    ).first()
    if not classroom:
        raise NotFoundError("教室不存在")
    return classroom


def update_classroom(classroom_id: int, data: ClassroomUpdate, db: Session) -> Classroom:
    classroom = get_classroom(classroom_id, db)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("name") and payload["name"] != classroom.name:
        exists = db.query(Classroom).filter(
            Classroom.name == payload["name"],
            Classroom.id != classroom.id,
            Classroom.is_deleted == False,
        ).first()
        if exists:
            raise BusinessException(message="教室名称已存在")
    for key, value in payload.items():
        setattr(classroom, key, value)
    db.commit()
    db.refresh(classroom)
    return classroom


def delete_classroom(classroom_id: int, db: Session):
    classroom = get_classroom(classroom_id, db)
    if db.query(CourseSchedule).filter(
        CourseSchedule.classroom_id == classroom.id,
        CourseSchedule.is_deleted == False,
    ).first():
        raise BusinessException(message="该教室已有课表，不能删除")
    classroom.soft_delete()
    db.commit()


def list_classrooms(params: PageParams, db: Session, status: Optional[int] = None, room_type: Optional[str] = None):
    q = db.query(Classroom).filter(Classroom.is_deleted == False)
    if status is not None:
        q = q.filter(Classroom.status == status)
    if room_type:
        q = q.filter(Classroom.room_type == room_type)
    if params.keyword:
        q = q.filter(or_(
            Classroom.name.contains(params.keyword),
            Classroom.building.contains(params.keyword),
            Classroom.room_no.contains(params.keyword),
        ))
    return q.order_by(Classroom.name.asc())


def _schedule_query(db: Session):
    return db.query(CourseSchedule).options(
        joinedload(CourseSchedule.term),
        joinedload(CourseSchedule.course),
        joinedload(CourseSchedule.clazz),
        joinedload(CourseSchedule.teacher),
        joinedload(CourseSchedule.classroom),
    ).filter(CourseSchedule.is_deleted == False)


def _week_type_conflicts(left: str, right: str) -> bool:
    return left == "all" or right == "all" or left == right


def _validate_schedule_payload(data: dict, db: Session):
    if data["start_section"] > data["end_section"]:
        raise BusinessException(message="开始节次不能大于结束节次")
    if data["start_week"] > data["end_week"]:
        raise BusinessException(message="开始周不能大于结束周")
    if data["week_type"] not in VALID_WEEK_TYPES:
        raise BusinessException(message="周次类型不正确")
    if data["schedule_type"] not in VALID_SCHEDULE_TYPES:
        raise BusinessException(message="课表类型不正确")
    term = get_term(data["term_id"], db)
    if data["end_week"] > term.week_count:
        raise BusinessException(message="结束周不能超过学期教学周数")
    if not db.query(Course).filter(Course.id == data["course_id"], Course.is_deleted == False).first():
        raise BusinessException(message="课程不存在")
    if not db.query(Clazz).filter(Clazz.id == data["clazz_id"], Clazz.is_deleted == False).first():
        raise BusinessException(message="班级不存在")
    if not db.query(Teacher).filter(Teacher.id == data["teacher_id"], Teacher.is_deleted == False).first():
        raise BusinessException(message="教师不存在")
    classroom_id = data.get("classroom_id")
    if classroom_id and not db.query(Classroom).filter(
        Classroom.id == classroom_id,
        Classroom.is_deleted == False,
        Classroom.status != 0,
    ).first():
        raise BusinessException(message="教室不存在或已停用")


def _assert_no_schedule_conflict(data: dict, db: Session, exclude_id: Optional[int] = None):
    q = db.query(CourseSchedule).filter(
        CourseSchedule.is_deleted == False,
        CourseSchedule.status == 1,
        CourseSchedule.term_id == data["term_id"],
        CourseSchedule.weekday == data["weekday"],
        CourseSchedule.start_section <= data["end_section"],
        CourseSchedule.end_section >= data["start_section"],
        CourseSchedule.start_week <= data["end_week"],
        CourseSchedule.end_week >= data["start_week"],
    )
    if exclude_id:
        q = q.filter(CourseSchedule.id != exclude_id)

    conflict_conditions = [
        CourseSchedule.teacher_id == data["teacher_id"],
        CourseSchedule.clazz_id == data["clazz_id"],
    ]
    if data.get("classroom_id"):
        conflict_conditions.append(CourseSchedule.classroom_id == data["classroom_id"])

    candidates = q.filter(or_(*conflict_conditions)).all()

    for item in candidates:
        if not _week_type_conflicts(item.week_type, data["week_type"]):
            continue
        if item.teacher_id == data["teacher_id"]:
            raise BusinessException(message=f"教师时间冲突：{item.course.name if item.course else '已有课程'}")
        if item.clazz_id == data["clazz_id"]:
            raise BusinessException(message=f"班级时间冲突：{item.course.name if item.course else '已有课程'}")
        if data.get("classroom_id") and item.classroom_id == data.get("classroom_id"):
            raise BusinessException(message=f"教室时间冲突：{item.course.name if item.course else '已有课程'}")


def create_course_schedule(data: CourseScheduleCreate, db: Session) -> CourseSchedule:
    payload = data.model_dump()
    _validate_schedule_payload(payload, db)
    _assert_no_schedule_conflict(payload, db)
    schedule = CourseSchedule(**payload)
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return get_course_schedule(schedule.id, db)


def get_course_schedule(schedule_id: int, db: Session) -> CourseSchedule:
    schedule = _schedule_query(db).filter(CourseSchedule.id == schedule_id).first()
    if not schedule:
        raise NotFoundError("课表不存在")
    return schedule


def update_course_schedule(schedule_id: int, data: CourseScheduleUpdate, db: Session) -> CourseSchedule:
    schedule = get_course_schedule(schedule_id, db)
    payload = {
        "term_id": schedule.term_id,
        "course_id": schedule.course_id,
        "clazz_id": schedule.clazz_id,
        "teacher_id": schedule.teacher_id,
        "classroom_id": schedule.classroom_id,
        "weekday": schedule.weekday,
        "start_section": schedule.start_section,
        "end_section": schedule.end_section,
        "start_week": schedule.start_week,
        "end_week": schedule.end_week,
        "week_type": schedule.week_type,
        "schedule_type": schedule.schedule_type,
        "status": schedule.status,
        "remark": schedule.remark,
    }
    payload.update(data.model_dump(exclude_unset=True))
    _validate_schedule_payload(payload, db)
    _assert_no_schedule_conflict(payload, db, exclude_id=schedule.id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)
    db.commit()
    db.refresh(schedule)
    return get_course_schedule(schedule.id, db)


def delete_course_schedule(schedule_id: int, db: Session):
    schedule = get_course_schedule(schedule_id, db)
    schedule.soft_delete()
    db.commit()


def list_course_schedules(
    params: PageParams,
    db: Session,
    term_id: Optional[int] = None,
    course_id: Optional[int] = None,
    clazz_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    classroom_id: Optional[int] = None,
    weekday: Optional[int] = None,
):
    q = _schedule_query(db)
    if term_id:
        q = q.filter(CourseSchedule.term_id == term_id)
    if course_id:
        q = q.filter(CourseSchedule.course_id == course_id)
    if clazz_id:
        q = q.filter(CourseSchedule.clazz_id == clazz_id)
    if teacher_id:
        q = q.filter(CourseSchedule.teacher_id == teacher_id)
    if classroom_id:
        q = q.filter(CourseSchedule.classroom_id == classroom_id)
    if weekday:
        q = q.filter(CourseSchedule.weekday == weekday)
    if params.keyword:
        q = q.join(Course, Course.id == CourseSchedule.course_id).filter(Course.name.contains(params.keyword))
    return q.order_by(
        CourseSchedule.weekday.asc(),
        CourseSchedule.start_section.asc(),
        CourseSchedule.start_week.asc(),
    )


def list_my_course_schedules(user: User, params: PageParams, db: Session, term_id: Optional[int] = None):
    q = _schedule_query(db)
    student = db.query(Student).filter(Student.user_id == user.id, Student.is_deleted == False).first()
    teacher = db.query(Teacher).filter(Teacher.user_id == user.id, Teacher.is_deleted == False).first()
    conditions = []
    if student:
        conditions.append(CourseSchedule.clazz_id == student.clazz_id)
    if teacher:
        conditions.append(CourseSchedule.teacher_id == teacher.id)
    if not conditions:
        return q.filter(false())
    q = q.filter(or_(*conditions))
    if term_id:
        q = q.filter(CourseSchedule.term_id == term_id)
    if params.keyword:
        q = q.join(Course, Course.id == CourseSchedule.course_id).filter(Course.name.contains(params.keyword))
    return q.order_by(
        CourseSchedule.weekday.asc(),
        CourseSchedule.start_section.asc(),
        CourseSchedule.start_week.asc(),
    )
