"""
Fix high-risk data health issues.

Current high-risk target:
- course schedule conflicts by teacher, class or classroom.

Run:
    python -m scripts.fix_high_risk_data
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, engine
from app.models.schedule import Classroom, CourseSchedule, Term
from app.services.operations_service import data_health
from app.models.user import User


SECTION_PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]
SLOTS = [(weekday, start, end) for weekday in range(1, 6) for start, end in SECTION_PAIRS]


def _slot_key(term_id: int, weekday: int, start_section: int, end_section: int):
    return term_id, weekday, start_section, end_section


def fix_schedule_conflicts(db):
    rooms = db.query(Classroom).filter(
        Classroom.is_deleted == False,
        Classroom.status == 1,
    ).order_by(Classroom.capacity.desc(), Classroom.id.asc()).all()
    if not rooms:
        raise RuntimeError("No available classrooms found.")

    terms = db.query(Term).filter(Term.is_deleted == False).order_by(Term.id.asc()).all()
    updated = 0

    for term in terms:
        schedules = db.query(CourseSchedule).filter(
            CourseSchedule.term_id == term.id,
            CourseSchedule.is_deleted == False,
            CourseSchedule.status == 1,
        ).order_by(
            CourseSchedule.clazz_id.asc(),
            CourseSchedule.teacher_id.asc(),
            CourseSchedule.course_id.asc(),
            CourseSchedule.id.asc(),
        ).all()

        used_teachers = set()
        used_clazzes = set()
        used_rooms = set()
        class_slot_cursor = defaultdict(int)

        for index, schedule in enumerate(schedules):
            assigned = False
            start_offset = class_slot_cursor[schedule.clazz_id] % len(SLOTS)

            for offset in range(len(SLOTS)):
                weekday, start_section, end_section = SLOTS[(start_offset + offset) % len(SLOTS)]
                slot = _slot_key(term.id, weekday, start_section, end_section)
                if (schedule.teacher_id, slot) in used_teachers:
                    continue
                if (schedule.clazz_id, slot) in used_clazzes:
                    continue

                for room_offset in range(len(rooms)):
                    room = rooms[(index + room_offset) % len(rooms)]
                    if (room.id, slot) in used_rooms:
                        continue

                    schedule.weekday = weekday
                    schedule.start_section = start_section
                    schedule.end_section = end_section
                    schedule.classroom_id = room.id
                    schedule.start_week = 1
                    schedule.end_week = min(term.week_count or schedule.end_week or 16, 16)
                    schedule.week_type = "all"
                    schedule.schedule_type = "normal"
                    schedule.remark = "高危体检修复：重新排布避免教师/班级/教室冲突"

                    used_teachers.add((schedule.teacher_id, slot))
                    used_clazzes.add((schedule.clazz_id, slot))
                    used_rooms.add((room.id, slot))
                    class_slot_cursor[schedule.clazz_id] = (start_offset + offset + 1) % len(SLOTS)
                    updated += 1
                    assigned = True
                    break

                if assigned:
                    break

            if not assigned:
                raise RuntimeError(f"Unable to assign conflict-free slot for schedule {schedule.id}.")

    db.commit()
    return updated


def high_issue_count(db):
    admin = db.query(User).filter(User.username == "admin", User.is_deleted == False).first()
    if not admin:
        return None
    health = data_health(admin, db)
    return [
        {"code": item["code"], "count": item["count"]}
        for item in health["issues"]
        if item["severity"] == "high"
    ]


def main():
    engine.echo = False
    db = SessionLocal()
    try:
        before = high_issue_count(db)
        updated = fix_schedule_conflicts(db)
        after = high_issue_count(db)
        print(f"High-risk data fix completed. Schedules updated: {updated}")
        print(f"Before: {before}")
        print(f"After: {after}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
