"""
考试服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.exam import Exam
from app.exceptions import NotFoundError
from app.schemas.exam import ExamCreate, ExamUpdate
from app.schemas.common import PageParams


def create_exam(data: ExamCreate, db: Session) -> Exam:
    exam = Exam(**data.model_dump())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


def get_exam(exam_id: int, db: Session) -> Exam:
    exam = db.query(Exam).options(
        joinedload(Exam.course),
        joinedload(Exam.clazz),
    ).filter(Exam.id == exam_id, Exam.is_deleted == False).first()
    if not exam:
        raise NotFoundError("考试不存在")
    return exam


def update_exam(exam_id: int, data: ExamUpdate, db: Session) -> Exam:
    exam = get_exam(exam_id, db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(exam, k, v)
    db.commit()
    db.refresh(exam)
    return exam


def delete_exam(exam_id: int, db: Session):
    exam = get_exam(exam_id, db)
    exam.soft_delete()
    db.commit()


def list_exams(params: PageParams, db: Session, course_id: int = None, clazz_id: int = None):
    q = db.query(Exam).options(
        joinedload(Exam.course),
        joinedload(Exam.clazz),
    ).filter(Exam.is_deleted == False)
    if course_id:
        q = q.filter(Exam.course_id == course_id)
    if clazz_id:
        q = q.filter(Exam.clazz_id == clazz_id)
    if params.keyword:
        q = q.filter(Exam.name.contains(params.keyword))
    return q
