"""
Seed integrated demo data across organization, teaching, schedule, score and leave modules.

This script is intentionally idempotent: it updates missing business links and creates
records only when a matching record does not already exist.

Run:
    python -m scripts.seed_integrated_demo_data
"""
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password
from app.config import settings
from app.database import SessionLocal, engine
from app.models.clazz import Clazz
from app.models.course import Course
from app.models.department import Department
from app.models.exam import Exam
from app.models.leave import LeaveRequest
from app.models.schedule import Classroom, CourseSchedule, Term
from app.models.score import Score
from app.models.student import Student, StudentCourse
from app.models.teacher import Teacher, TeacherClazz
from app.models.user import Role, User, UserRole


DEFAULT_PASSWORD = settings.DEFAULT_USER_PASSWORD

DEPARTMENT_ADMINS = {
    "CS": "teacher02",
    "MATH": "teacher05",
    "LANG": "teacher07",
    "ECON": "teacher09",
    "ART": "teacher11",
}

COUNSELORS = {
    "CS": "teacher04",
    "MATH": "teacher06",
    "LANG": "teacher08",
    "ECON": "teacher10",
    "ART": "teacher12",
}

CURRICULUM_BY_DEPT = {
    "CS": ["CS101", "CS201", "CS301", "CS302", "MATH101", "LANG101"],
    "MATH": ["MATH201", "MATH202", "MATH101", "LANG101", "CS101"],
    "LANG": ["LANG101", "LANG201", "MATH101", "CS101"],
    "ECON": ["ECON101", "MATH101", "LANG101", "CS101"],
    "ART": ["ART101", "ART201", "LANG101", "CS101"],
}

ROOMS = [
    {
        "name": "A101 多媒体教室",
        "building": "第一教学楼",
        "room_no": "A101",
        "campus": "主校区",
        "capacity": 80,
        "room_type": "multimedia",
    },
    {
        "name": "A102 普通教室",
        "building": "第一教学楼",
        "room_no": "A102",
        "campus": "主校区",
        "capacity": 70,
        "room_type": "normal",
    },
    {
        "name": "B201 计算机实验室",
        "building": "实验楼",
        "room_no": "B201",
        "campus": "主校区",
        "capacity": 60,
        "room_type": "computer",
    },
    {
        "name": "C301 阶梯教室",
        "building": "综合楼",
        "room_no": "C301",
        "campus": "主校区",
        "capacity": 120,
        "room_type": "lecture",
    },
]


def get_role(db, code: str):
    return db.query(Role).filter(Role.code == code).first()


def add_role(db, user: User, role_code: str) -> bool:
    role = get_role(db, role_code)
    if not role:
        return False
    exists = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    ).first()
    if exists:
        return False
    db.add(UserRole(user_id=user.id, role_id=role.id))
    return True


def get_teacher_by_username(db, username: str):
    user = db.query(User).filter(User.username == username, User.is_deleted == False).first()
    if not user:
        return None
    return db.query(Teacher).filter(Teacher.user_id == user.id, Teacher.is_deleted == False).first()


def ensure_user_for_teacher(db, teacher: Teacher) -> User:
    if teacher.user:
        return teacher.user
    username = f"teacher_{teacher.employee_no}".lower()
    user = User(
        username=username,
        password_hash=hash_password(DEFAULT_PASSWORD),
        real_name=teacher.name,
        status=1,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    teacher.user_id = user.id
    return user


def ensure_teacher_clazz(db, teacher_id: int, clazz_id: int) -> bool:
    exists = db.query(TeacherClazz).filter(
        TeacherClazz.teacher_id == teacher_id,
        TeacherClazz.clazz_id == clazz_id,
    ).first()
    if exists:
        return False
    db.add(TeacherClazz(teacher_id=teacher_id, clazz_id=clazz_id))
    return True


def ensure_class_advisers(db):
    changed = {"clazz": 0, "teacher_clazz": 0, "roles": 0}

    departments = {d.id: d for d in db.query(Department).filter(Department.is_deleted == False).all()}
    for dept in departments.values():
        admin = get_teacher_by_username(db, DEPARTMENT_ADMINS.get(dept.code, ""))
        counselor = get_teacher_by_username(db, COUNSELORS.get(dept.code, ""))

        if admin:
            admin_user = ensure_user_for_teacher(db, admin)
            if add_role(db, admin_user, "department_admin"):
                changed["roles"] += 1
            if "主任" not in (admin.position or ""):
                admin.position = "院系主任"

        if counselor:
            counselor_user = ensure_user_for_teacher(db, counselor)
            if add_role(db, counselor_user, "counselor"):
                changed["roles"] += 1
            if "辅导员" not in (counselor.position or ""):
                counselor.position = "辅导员"

        if not counselor:
            continue

        clazzes = db.query(Clazz).filter(
            Clazz.department_id == dept.id,
            Clazz.is_deleted == False,
        ).all()
        for clazz in clazzes:
            if clazz.counselor_id != counselor.id:
                clazz.counselor_id = counselor.id
                changed["clazz"] += 1
            if ensure_teacher_clazz(db, counselor.id, clazz.id):
                changed["teacher_clazz"] += 1

    return changed


def ensure_current_term(db) -> Term:
    db.query(Term).filter(Term.is_deleted == False).update({"is_current": False})
    term = db.query(Term).filter(
        Term.academic_year == "2025-2026",
        Term.semester == 1,
        Term.is_deleted == False,
    ).first()
    if not term:
        term = Term(
            name="2025-2026 学年第一学期",
            academic_year="2025-2026",
            semester=1,
            start_date=date(2025, 9, 1),
            end_date=date(2026, 1, 18),
            week_count=20,
            is_current=True,
            status=1,
            remark="联动演示学期",
        )
        db.add(term)
        db.flush()
    else:
        term.name = "2025-2026 学年第一学期"
        term.start_date = date(2025, 9, 1)
        term.end_date = date(2026, 1, 18)
        term.week_count = 20
        term.is_current = True
        term.status = 1
    return term


def ensure_classrooms(db):
    rooms = []
    for item in ROOMS:
        room = db.query(Classroom).filter(
            Classroom.name == item["name"],
            Classroom.is_deleted == False,
        ).first()
        if not room:
            room = Classroom(**item, status=1, remark="联动演示教室")
            db.add(room)
            db.flush()
        else:
            for key, value in item.items():
                setattr(room, key, value)
            room.status = 1
        rooms.append(room)
    return rooms


def active_courses_for_clazz(db, clazz: Clazz):
    dept = clazz.department
    if not dept:
        return []
    codes = CURRICULUM_BY_DEPT.get(dept.code, ["LANG101"])
    courses = []
    for code in codes:
        course = db.query(Course).filter(
            Course.code == code,
            Course.is_deleted == False,
            Course.status == 1,
        ).first()
        if course:
            courses.append(course)
    return courses


def ensure_student_courses(db):
    created = 0
    students = db.query(Student).filter(Student.is_deleted == False, Student.status == 1).all()
    for student in students:
        courses = active_courses_for_clazz(db, student.clazz)
        for course in courses:
            exists = db.query(StudentCourse).filter(
                StudentCourse.student_id == student.id,
                StudentCourse.course_id == course.id,
            ).first()
            if exists:
                if exists.status != 1:
                    exists.status = 1
                continue
            db.add(StudentCourse(
                student_id=student.id,
                course_id=course.id,
                select_time=datetime(2025, 9, 2, 9, 0, 0),
                status=1,
            ))
            created += 1
    return created


def schedule_conflicts(db, *, term_id, teacher_id, clazz_id, classroom_id, weekday, start_section, end_section):
    q = db.query(CourseSchedule).filter(
        CourseSchedule.term_id == term_id,
        CourseSchedule.is_deleted == False,
        CourseSchedule.status == 1,
        CourseSchedule.weekday == weekday,
        CourseSchedule.start_section <= end_section,
        CourseSchedule.end_section >= start_section,
    )
    return q.filter(
        (CourseSchedule.teacher_id == teacher_id)
        | (CourseSchedule.clazz_id == clazz_id)
        | (CourseSchedule.classroom_id == classroom_id)
    ).first()


def ensure_course_schedules(db, term: Term, rooms: list[Classroom]):
    created = 0
    clazzes = db.query(Clazz).filter(Clazz.is_deleted == False, Clazz.status == 1).order_by(Clazz.code).all()
    slots = [
        (1, 1, 2),
        (2, 3, 4),
        (3, 1, 2),
        (4, 3, 4),
        (5, 1, 2),
        (1, 5, 6),
    ]

    for class_index, clazz in enumerate(clazzes):
        for course_index, course in enumerate(active_courses_for_clazz(db, clazz)[:6]):
            teacher_id = course.teacher_id or clazz.counselor_id
            if not teacher_id:
                continue

            weekday, start_section, end_section = slots[course_index % len(slots)]
            room = rooms[(class_index + course_index) % len(rooms)]
            exists = db.query(CourseSchedule).filter(
                CourseSchedule.term_id == term.id,
                CourseSchedule.course_id == course.id,
                CourseSchedule.clazz_id == clazz.id,
                CourseSchedule.is_deleted == False,
            ).first()
            if exists:
                exists.teacher_id = teacher_id
                exists.classroom_id = room.id
                exists.start_week = 1
                exists.end_week = min(16, term.week_count)
                exists.week_type = "all"
                exists.schedule_type = "normal"
                exists.status = 1
                continue

            if schedule_conflicts(
                db,
                term_id=term.id,
                teacher_id=teacher_id,
                clazz_id=clazz.id,
                classroom_id=room.id,
                weekday=weekday,
                start_section=start_section,
                end_section=end_section,
            ):
                continue

            schedule = CourseSchedule(
                term_id=term.id,
                course_id=course.id,
                clazz_id=clazz.id,
                teacher_id=teacher_id,
                classroom_id=room.id,
                weekday=weekday,
                start_section=start_section,
                end_section=end_section,
                start_week=1,
                end_week=min(16, term.week_count),
                week_type="all",
                schedule_type="normal",
                status=1,
                remark="联动演示课表",
            )
            db.add(schedule)
            created += 1
    return created


def score_grade(value: int) -> str:
    if value >= 90:
        return "A"
    if value >= 80:
        return "B"
    if value >= 70:
        return "C"
    if value >= 60:
        return "D"
    return "F"


def deterministic_score(student_id: int, course_id: int, clazz_id: int) -> int:
    return 58 + ((student_id * 7 + course_id * 11 + clazz_id * 13) % 43)


def ensure_exam_and_scores(db):
    created_exams = 0
    created_scores = 0
    clazzes = db.query(Clazz).filter(Clazz.is_deleted == False, Clazz.status == 1).order_by(Clazz.code).all()
    exam_base_date = date(2026, 1, 5)

    for clazz_index, clazz in enumerate(clazzes):
        students = db.query(Student).filter(
            Student.clazz_id == clazz.id,
            Student.is_deleted == False,
            Student.status == 1,
        ).order_by(Student.student_no).all()
        if not students:
            continue

        for course_index, course in enumerate(active_courses_for_clazz(db, clazz)[:5]):
            exam = db.query(Exam).filter(
                Exam.course_id == course.id,
                Exam.clazz_id == clazz.id,
                Exam.exam_type == 2,
                Exam.is_deleted == False,
            ).first()
            if not exam:
                exam = Exam(
                    name=f"{clazz.name} - {course.name} - 期末考试",
                    course_id=course.id,
                    exam_type=2,
                    exam_date=exam_base_date + timedelta(days=(clazz_index + course_index) % 10),
                    exam_time="09:00-11:00",
                    location="按课表教室",
                    clazz_id=clazz.id,
                    description="联动演示期末考试",
                    status=1,
                )
                db.add(exam)
                db.flush()
                created_exams += 1
            else:
                exam.course_id = course.id
                exam.clazz_id = clazz.id
                exam.exam_type = 2
                exam.status = 1

            scorer_id = course.teacher_id or clazz.counselor_id
            class_scores = []
            for student in students:
                score = db.query(Score).filter(
                    Score.student_id == student.id,
                    Score.exam_id == exam.id,
                    Score.is_deleted == False,
                ).first()
                if not score:
                    value = deterministic_score(student.id, course.id, clazz.id)
                    score = Score(
                        student_id=student.id,
                        exam_id=exam.id,
                        course_id=course.id,
                        score=Decimal(value),
                        grade=score_grade(value),
                        scorer_id=scorer_id,
                        remark="联动演示成绩",
                    )
                    db.add(score)
                    db.flush()
                    created_scores += 1
                else:
                    score.course_id = course.id
                    score.scorer_id = scorer_id
                    if score.score is None:
                        value = deterministic_score(student.id, course.id, clazz.id)
                        score.score = Decimal(value)
                        score.grade = score_grade(value)
                class_scores.append(score)

            ranked = sorted(
                [s for s in class_scores if s.score is not None],
                key=lambda item: item.score,
                reverse=True,
            )
            for rank, score in enumerate(ranked, start=1):
                score.rank_in_class = rank

    return {"exams": created_exams, "scores": created_scores}


def find_first_student(db, clazz_code: str):
    return db.query(Student).join(Clazz).filter(
        Clazz.code == clazz_code,
        Student.is_deleted == False,
        Student.status == 1,
    ).order_by(Student.student_no).first()


def find_review_user(db, role_code: str, dept_code: str | None = None):
    q = db.query(User).join(UserRole).join(Role).join(Teacher, Teacher.user_id == User.id).filter(
        Role.code == role_code,
        User.is_deleted == False,
        Teacher.is_deleted == False,
    )
    if dept_code:
        q = q.join(Department, Department.id == Teacher.department_id).filter(Department.code == dept_code)
    return q.first()


def ensure_leave_request(db, *, applicant: User, applicant_type: str, leave_type: str,
                         start_time: datetime, end_time: datetime, reason: str,
                         status: str = "pending", reviewer: User | None = None,
                         reviewer_role: str | None = None, review_comment: str | None = None):
    exists = db.query(LeaveRequest).filter(
        LeaveRequest.applicant_user_id == applicant.id,
        LeaveRequest.start_time == start_time,
        LeaveRequest.end_time == end_time,
        LeaveRequest.is_deleted == False,
    ).first()
    if exists:
        return exists, False

    student = db.query(Student).filter(Student.user_id == applicant.id, Student.is_deleted == False).first()
    teacher = db.query(Teacher).filter(Teacher.user_id == applicant.id, Teacher.is_deleted == False).first()
    clazz = student.clazz if student else None
    department_id = None
    if student and clazz:
        department_id = clazz.department_id
    elif teacher:
        department_id = teacher.department_id

    reviewed_at = datetime(2025, 9, 4, 10, 0, 0) if reviewer else None
    req = LeaveRequest(
        applicant_user_id=applicant.id,
        applicant_type=applicant_type,
        student_id=student.id if applicant_type == "student" and student else None,
        teacher_id=teacher.id if applicant_type == "teacher" and teacher else None,
        clazz_id=clazz.id if clazz else None,
        department_id=department_id,
        leave_type=leave_type,
        start_time=start_time,
        end_time=end_time,
        duration_hours=Decimal(str((end_time - start_time).total_seconds() / 3600)).quantize(Decimal("0.01")),
        reason=reason,
        destination="校外" if applicant_type == "student" else None,
        contact_phone=applicant.phone,
        emergency_contact="家长 13800009999" if applicant_type == "student" else "办公室 010-88888888",
        remark="联动演示请假",
        status=status,
        reviewer_id=reviewer.id if reviewer else None,
        reviewer_role=reviewer_role,
        review_comment=review_comment,
        reviewed_at=reviewed_at,
    )
    db.add(req)
    return req, True


def ensure_leave_requests(db):
    created = 0
    cs_student = find_first_student(db, "CS2201")
    math_student = find_first_student(db, "MATH2301") or find_first_student(db, "MATH2201")
    teacher = get_teacher_by_username(db, "teacher03")

    cs_counselor = find_review_user(db, "counselor", "CS")
    math_dept_admin = find_review_user(db, "department_admin", "MATH")
    cs_dept_admin = find_review_user(db, "department_admin", "CS")

    if cs_student and cs_student.user:
        _, was_created = ensure_leave_request(
            db,
            applicant=cs_student.user,
            applicant_type="student",
            leave_type="sick",
            start_time=datetime(2025, 9, 10, 8, 0, 0),
            end_time=datetime(2025, 9, 10, 18, 0, 0),
            reason="因发热到校医院复诊，请假一天。",
            status="pending",
        )
        created += int(was_created)

        _, was_created = ensure_leave_request(
            db,
            applicant=cs_student.user,
            applicant_type="student",
            leave_type="personal",
            start_time=datetime(2025, 9, 18, 13, 0, 0),
            end_time=datetime(2025, 9, 18, 18, 0, 0),
            reason="参加家庭重要事务，下午请假。",
            status="approved",
            reviewer=cs_counselor,
            reviewer_role="counselor",
            review_comment="情况属实，同意请假，按时返校。",
        )
        created += int(was_created)

    if math_student and math_student.user:
        _, was_created = ensure_leave_request(
            db,
            applicant=math_student.user,
            applicant_type="student",
            leave_type="other",
            start_time=datetime(2025, 9, 22, 8, 0, 0),
            end_time=datetime(2025, 9, 22, 12, 0, 0),
            reason="材料不完整，暂不符合请假要求。",
            status="rejected",
            reviewer=math_dept_admin,
            reviewer_role="department_admin",
            review_comment="请补充证明材料后重新提交。",
        )
        created += int(was_created)

    if teacher and teacher.user:
        _, was_created = ensure_leave_request(
            db,
            applicant=teacher.user,
            applicant_type="teacher",
            leave_type="official",
            start_time=datetime(2025, 10, 9, 8, 0, 0),
            end_time=datetime(2025, 10, 10, 18, 0, 0),
            reason="参加省级教学研讨会。",
            status="approved",
            reviewer=cs_dept_admin,
            reviewer_role="department_admin",
            review_comment="同意参加，返校后提交会议材料。",
        )
        created += int(was_created)

    return created


def integrity_summary(db):
    students_without_courses = db.query(Student).outerjoin(StudentCourse).filter(
        Student.is_deleted == False,
        StudentCourse.id == None,
    ).count()
    classes_without_counselor = db.query(Clazz).filter(
        Clazz.is_deleted == False,
        Clazz.counselor_id == None,
    ).count()
    schedules = db.query(CourseSchedule).filter(CourseSchedule.is_deleted == False).count()
    leave_requests = db.query(LeaveRequest).filter(LeaveRequest.is_deleted == False).count()
    return {
        "students_without_courses": students_without_courses,
        "classes_without_counselor": classes_without_counselor,
        "course_schedules": schedules,
        "leave_requests": leave_requests,
    }


def main():
    engine.echo = False
    db = SessionLocal()
    try:
        adviser_changes = ensure_class_advisers(db)
        term = ensure_current_term(db)
        rooms = ensure_classrooms(db)
        created_student_courses = ensure_student_courses(db)
        created_schedules = ensure_course_schedules(db, term, rooms)
        score_changes = ensure_exam_and_scores(db)
        created_leave_requests = ensure_leave_requests(db)
        db.commit()

        summary = integrity_summary(db)
        print("Integrated demo data synchronized.")
        print(f"- class counselor updates: {adviser_changes['clazz']}")
        print(f"- teacher-class links created: {adviser_changes['teacher_clazz']}")
        print(f"- reviewer roles added: {adviser_changes['roles']}")
        print(f"- student-course rows created: {created_student_courses}")
        print(f"- course schedules created: {created_schedules}")
        print(f"- exams created: {score_changes['exams']}")
        print(f"- scores created: {score_changes['scores']}")
        print(f"- leave requests created: {created_leave_requests}")
        print("- integrity summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
