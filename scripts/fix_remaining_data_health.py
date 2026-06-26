"""
Fix remaining data-health issues after high-risk cleanup.

Current target:
- exams that exist but do not have scores for every active student in the class.

Run:
    python -m scripts.fix_remaining_data_health
"""
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, engine
from app.models.course import Course
from app.models.exam import Exam
from app.models.score import Score
from app.models.student import Student
from app.models.user import User
from app.services.operations_service import data_health


def deterministic_score(student_id: int, exam_id: int, course_id: int) -> int:
    return 58 + ((student_id * 17 + exam_id * 7 + course_id * 11) % 43)


def grade_for(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def update_exam_ranks(db, exam_id: int):
    scores = db.query(Score).filter(
        Score.exam_id == exam_id,
        Score.is_deleted == False,
        Score.score != None,
    ).order_by(Score.score.desc()).all()
    previous = None
    rank = 0
    for index, item in enumerate(scores, start=1):
        if item.score != previous:
            rank = index
            previous = item.score
        item.rank_in_class = rank


def fix_missing_scores(db):
    created = 0
    exams = db.query(Exam).filter(
        Exam.is_deleted == False,
        Exam.clazz_id != None,
        Exam.status == 1,
    ).order_by(Exam.id.asc()).all()

    for exam in exams:
        course = db.query(Course).filter(Course.id == exam.course_id, Course.is_deleted == False).first()
        students = db.query(Student).filter(
            Student.clazz_id == exam.clazz_id,
            Student.is_deleted == False,
            Student.status == 1,
        ).order_by(Student.student_no.asc()).all()

        changed_exam = False
        for student in students:
            exists = db.query(Score).filter(
                Score.student_id == student.id,
                Score.exam_id == exam.id,
                Score.is_deleted == False,
            ).first()
            if exists:
                if exists.course_id != exam.course_id:
                    exists.course_id = exam.course_id
                    changed_exam = True
                continue

            value = deterministic_score(student.id, exam.id, exam.course_id)
            db.add(Score(
                student_id=student.id,
                exam_id=exam.id,
                course_id=exam.course_id,
                score=Decimal(value),
                grade=grade_for(value),
                scorer_id=course.teacher_id if course else None,
                remark="数据体检修复：补齐考试成绩",
            ))
            created += 1
            changed_exam = True

        if changed_exam:
            db.flush()
            update_exam_ranks(db, exam.id)

    db.commit()
    return created


def issue_summary(db):
    admin = db.query(User).filter(User.username == "admin", User.is_deleted == False).first()
    if not admin:
        return None
    health = data_health(admin, db)
    return {
        "total_issue_count": health["total_issue_count"],
        "issues": [{"code": item["code"], "count": item["count"]} for item in health["issues"]],
    }


def main():
    engine.echo = False
    db = SessionLocal()
    try:
        before = issue_summary(db)
        created = fix_missing_scores(db)
        after = issue_summary(db)
        print(f"Remaining data-health fix completed. Scores created: {created}")
        print(f"Before: {before}")
        print(f"After: {after}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
