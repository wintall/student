"""
课程服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.course import Course
from app.exceptions import BusinessException, NotFoundError
from app.schemas.course import CourseCreate, CourseUpdate
from app.schemas.common import PageParams


def create_course(data: CourseCreate, db: Session) -> Course:
    if db.query(Course).filter(Course.code == data.code).first():
        raise BusinessException(message="课程代码已存在")
    course = Course(**data.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def get_course(course_id: int, db: Session) -> Course:
    course = db.query(Course).options(
        joinedload(Course.department),
        joinedload(Course.teacher),
    ).filter(Course.id == course_id, Course.is_deleted == False).first()
    if not course:
        raise NotFoundError("课程不存在")
    return course


def update_course(course_id: int, data: CourseUpdate, db: Session) -> Course:
    course = get_course(course_id, db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


def delete_course(course_id: int, db: Session):
    course = get_course(course_id, db)
    course.soft_delete()
    db.commit()


def list_courses(params: PageParams, db: Session, department_id: int = None):
    q = db.query(Course).options(
        joinedload(Course.department),
        joinedload(Course.teacher),
    ).filter(Course.is_deleted == False)
    if department_id:
        q = q.filter(Course.department_id == department_id)
    if params.keyword:
        q = q.filter(Course.name.contains(params.keyword) | Course.code.contains(params.keyword))
    return q
