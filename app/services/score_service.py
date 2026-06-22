"""
成绩服务
"""
from typing import List
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sa_func

from app.models.score import Score
from app.models.student import Student
from app.exceptions import BusinessException, NotFoundError
from app.schemas.score import ScoreCreate, ScoreUpdate
from app.schemas.common import PageParams


def _calculate_grade(score: Decimal) -> str:
    """根据分数计算等级"""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def create_score(data: ScoreCreate, db: Session) -> Score:
    # 检查是否已录入
    existing = db.query(Score).filter(
        Score.student_id == data.student_id,
        Score.exam_id == data.exam_id,
        Score.is_deleted == False,
    ).first()
    if existing:
        raise BusinessException(message="该学生此考试成绩已录入")

    grade = _calculate_grade(data.score) if data.score is not None else None

    score = Score(
        student_id=data.student_id,
        exam_id=data.exam_id,
        course_id=data.course_id,
        score=data.score,
        grade=grade,
        remark=data.remark,
        scorer_id=data.scorer_id,
    )
    db.add(score)
    db.flush()

    # 计算班级排名
    _update_class_ranks(db, data.exam_id, data.course_id)

    db.commit()
    db.refresh(score)
    return score


def update_score(score_id: int, data: ScoreUpdate, db: Session) -> Score:
    score = db.query(Score).filter(Score.id == score_id, Score.is_deleted == False).first()
    if not score:
        raise NotFoundError("成绩记录不存在")

    if data.score is not None:
        score.score = data.score
        score.grade = _calculate_grade(data.score)

    if data.remark is not None:
        score.remark = data.remark

    _update_class_ranks(db, score.exam_id, score.course_id)
    db.commit()
    db.refresh(score)
    return score


def delete_score(score_id: int, db: Session):
    score = db.query(Score).filter(Score.id == score_id, Score.is_deleted == False).first()
    if not score:
        raise NotFoundError("成绩记录不存在")
    score.soft_delete()
    _update_class_ranks(db, score.exam_id, score.course_id)
    db.commit()


def list_scores(params: PageParams, db: Session, exam_id: int = None, student_id: int = None, course_id: int = None):
    q = db.query(Score).options(
        joinedload(Score.student),
        joinedload(Score.course),
        joinedload(Score.exam),
    ).filter(Score.is_deleted == False)
    if exam_id:
        q = q.filter(Score.exam_id == exam_id)
    if student_id:
        q = q.filter(Score.student_id == student_id)
    if course_id:
        q = q.filter(Score.course_id == course_id)
    return q


def _update_class_ranks(db: Session, exam_id: int, course_id: int):
    """重新计算某考试某课程的班级排名"""
    scores = db.query(Score).filter(
        Score.exam_id == exam_id,
        Score.course_id == course_id,
        Score.is_deleted == False,
        Score.score.isnot(None),
    ).order_by(Score.score.desc()).all()

    rank = 0
    prev_score = None
    for i, s in enumerate(scores):
        if s.score != prev_score:
            rank = i + 1
            prev_score = s.score
        s.rank_in_class = rank
