"""
Seed demo data for term, classroom and course schedules.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.clazz import Clazz
from app.models.course import Course
from app.models.schedule import Classroom, CourseSchedule, Term
from app.models.teacher import Teacher


def get_or_create_term(db):
    term = db.query(Term).filter(
        Term.academic_year == "2025-2026",
        Term.semester == 1,
        Term.is_deleted == False,
    ).first()
    if term:
        return term
    db.query(Term).filter(Term.is_deleted == False).update({"is_current": False})
    term = Term(
        name="2025-2026 学年第一学期",
        academic_year="2025-2026",
        semester=1,
        start_date=date(2025, 9, 1),
        end_date=date(2026, 1, 18),
        week_count=20,
        is_current=True,
        status=1,
        remark="演示学期",
    )
    db.add(term)
    db.flush()
    return term


def get_or_create_classrooms(db):
    items = [
        {"name": "逸夫楼 A101", "building": "逸夫楼", "room_no": "A101", "campus": "主校区", "capacity": 80, "room_type": "multimedia"},
        {"name": "逸夫楼 A102", "building": "逸夫楼", "room_no": "A102", "campus": "主校区", "capacity": 80, "room_type": "normal"},
        {"name": "实验楼 B201", "building": "实验楼", "room_no": "B201", "campus": "主校区", "capacity": 60, "room_type": "computer"},
        {"name": "综合楼 C301", "building": "综合楼", "room_no": "C301", "campus": "主校区", "capacity": 120, "room_type": "normal"},
    ]
    result = []
    for item in items:
        classroom = db.query(Classroom).filter(Classroom.name == item["name"], Classroom.is_deleted == False).first()
        if not classroom:
            classroom = Classroom(status=1, remark="演示教室", **item)
            db.add(classroom)
            db.flush()
        result.append(classroom)
    return result


def pick_course(db, index):
    courses = db.query(Course).filter(Course.is_deleted == False, Course.status == 1).order_by(Course.id).all()
    return courses[index] if len(courses) > index else None


def pick_clazz(db, index):
    clazzes = db.query(Clazz).filter(Clazz.is_deleted == False, Clazz.status == 1).order_by(Clazz.id).all()
    return clazzes[index] if len(clazzes) > index else None


def pick_teacher(db, course, index):
    if course and course.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == course.teacher_id, Teacher.is_deleted == False).first()
        if teacher:
            return teacher
    teachers = db.query(Teacher).filter(Teacher.is_deleted == False, Teacher.status == 1).order_by(Teacher.id).all()
    return teachers[index] if len(teachers) > index else None


def create_schedule_if_missing(db, **data):
    exists = db.query(CourseSchedule).filter(
        CourseSchedule.term_id == data["term_id"],
        CourseSchedule.course_id == data["course_id"],
        CourseSchedule.clazz_id == data["clazz_id"],
        CourseSchedule.weekday == data["weekday"],
        CourseSchedule.start_section == data["start_section"],
        CourseSchedule.is_deleted == False,
    ).first()
    if exists:
        return exists, False
    schedule = CourseSchedule(status=1, week_type="all", schedule_type="normal", remark="演示课表", **data)
    db.add(schedule)
    return schedule, True


def main():
    db = SessionLocal()
    try:
        term = get_or_create_term(db)
        rooms = get_or_create_classrooms(db)
        plans = [
            (0, 0, 0, 1, 1, 2, 1, 16),
            (1, 0, 1, 2, 3, 4, 1, 16),
            (2, 1, 2, 3, 1, 2, 1, 16),
            (3, 1, 3, 4, 5, 6, 1, 16),
            (4, 2, 0, 5, 3, 4, 1, 16),
            (5, 2, 1, 1, 5, 6, 1, 16),
        ]
        created = 0
        for course_idx, clazz_idx, room_idx, weekday, start_section, end_section, start_week, end_week in plans:
            course = pick_course(db, course_idx)
            clazz = pick_clazz(db, clazz_idx)
            teacher = pick_teacher(db, course, course_idx)
            if not (course and clazz and teacher):
                continue
            _, was_created = create_schedule_if_missing(
                db,
                term_id=term.id,
                course_id=course.id,
                clazz_id=clazz.id,
                teacher_id=teacher.id,
                classroom_id=rooms[room_idx % len(rooms)].id,
                weekday=weekday,
                start_section=start_section,
                end_section=end_section,
                start_week=start_week,
                end_week=end_week,
            )
            if was_created:
                created += 1
        db.commit()
        print(f"课表示例数据同步完成，新增 {created} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
