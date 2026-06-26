"""
Seed linked attendance demo data.

The script is idempotent: it only creates a record when the same person/date/period
record does not already exist.
"""
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.attendance import AttendanceRecord
from app.models.clazz import Clazz
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User


def get_admin_id(db):
    admin = db.query(User).filter(User.username == "admin", User.is_deleted == False).first()
    return admin.id if admin else None


def add_student_record(db, student_no, attendance_date, status, remark, creator_id):
    student = (
        db.query(Student)
        .filter(Student.student_no == student_no, Student.is_deleted == False)
        .first()
    )
    if not student:
        return False
    clazz = db.query(Clazz).filter(Clazz.id == student.clazz_id).first()
    exists = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.is_deleted == False,
            AttendanceRecord.user_id == student.user_id,
            AttendanceRecord.attendance_date == attendance_date,
            AttendanceRecord.period_type == "day",
            AttendanceRecord.course_schedule_id == None,
        )
        .first()
    )
    if exists:
        return False
    db.add(AttendanceRecord(
        person_type="student",
        user_id=student.user_id,
        student_id=student.id,
        clazz_id=student.clazz_id,
        department_id=clazz.department_id if clazz else None,
        attendance_date=attendance_date,
        period_type="day",
        status=status,
        source="manual",
        remark=remark,
        created_by=creator_id,
        updated_by=creator_id,
    ))
    return True


def add_teacher_record(db, employee_no, attendance_date, status, remark, creator_id):
    teacher = (
        db.query(Teacher)
        .filter(Teacher.employee_no == employee_no, Teacher.is_deleted == False)
        .first()
    )
    if not teacher:
        return False
    exists = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.is_deleted == False,
            AttendanceRecord.user_id == teacher.user_id,
            AttendanceRecord.attendance_date == attendance_date,
            AttendanceRecord.period_type == "day",
            AttendanceRecord.course_schedule_id == None,
        )
        .first()
    )
    if exists:
        return False
    db.add(AttendanceRecord(
        person_type="teacher",
        user_id=teacher.user_id,
        teacher_id=teacher.id,
        department_id=teacher.department_id,
        attendance_date=attendance_date,
        period_type="day",
        checkin_time=datetime.combine(attendance_date, datetime.strptime("08:25", "%H:%M").time()),
        checkout_time=datetime.combine(attendance_date, datetime.strptime("17:35", "%H:%M").time()),
        status=status,
        source="manual",
        remark=remark,
        created_by=creator_id,
        updated_by=creator_id,
    ))
    return True


def main():
    with SessionLocal() as db:
        creator_id = get_admin_id(db)
        created = 0
        created += add_student_record(db, "S20230001", date(2026, 6, 24), "normal", "课堂出勤正常", creator_id)
        created += add_student_record(db, "S20230002", date(2026, 6, 24), "late", "早八迟到 8 分钟", creator_id)
        created += add_student_record(db, "S20230003", date(2026, 6, 25), "leave", "病假，已同步请假流程", creator_id)
        created += add_student_record(db, "S20230004", date(2026, 6, 25), "absent", "未参加上午课程点名", creator_id)
        created += add_teacher_record(db, "T2022001", date(2026, 6, 24), "normal", "教职工日考勤正常", creator_id)
        created += add_teacher_record(db, "T2022002", date(2026, 6, 24), "official", "院系会议公出", creator_id)
        db.commit()
        print(f"attendance seed complete, created={created}")


if __name__ == "__main__":
    main()
