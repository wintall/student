"""
Cross-module operations services: dashboard, data health checks and CSV exports.
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import get_user_role_codes
from app.models.announcement import Announcement
from app.models.clazz import Clazz
from app.models.course import Course
from app.models.department import Department
from app.models.email import EmailMessage
from app.models.exam import Exam
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.schedule import CourseSchedule
from app.models.score import Score
from app.models.student import Student, StudentCourse
from app.models.teacher import Teacher
from app.models.user import User


ADMIN_ROLES = {"admin", "academic_admin"}
DEPARTMENT_ROLES = {"department_admin", "staff_dean"}
COUNSELOR_ROLES = {"counselor", "staff_counselor"}
TEACHER_ROLES = {"teacher", "staff_teacher", "staff_affairs"}


def _role_codes(user: User, db: Session) -> set[str]:
    return get_user_role_codes(user, db)


def _teacher(user: User, db: Session) -> Teacher | None:
    return db.query(Teacher).filter(Teacher.user_id == user.id, Teacher.is_deleted == False).first()


def _student(user: User, db: Session) -> Student | None:
    return db.query(Student).filter(Student.user_id == user.id, Student.is_deleted == False).first()


def _scope(user: User, db: Session) -> dict[str, Any]:
    roles = _role_codes(user, db)
    teacher = _teacher(user, db)
    student = _student(user, db)
    if roles & ADMIN_ROLES:
        return {"kind": "all", "roles": roles, "teacher": teacher, "student": student}
    if roles & DEPARTMENT_ROLES and teacher and teacher.department_id:
        return {"kind": "department", "department_id": teacher.department_id, "roles": roles, "teacher": teacher, "student": student}
    if roles & COUNSELOR_ROLES and teacher:
        clazz_ids = [row[0] for row in db.query(Clazz.id).filter(
            Clazz.counselor_id == teacher.id,
            Clazz.is_deleted == False,
        ).all()]
        return {"kind": "clazzes", "clazz_ids": clazz_ids, "roles": roles, "teacher": teacher, "student": student}
    if student:
        return {"kind": "student", "student_id": student.id, "clazz_id": student.clazz_id, "roles": roles, "teacher": teacher, "student": student}
    if teacher:
        return {"kind": "teacher", "teacher_id": teacher.id, "department_id": teacher.department_id, "roles": roles, "teacher": teacher, "student": student}
    return {"kind": "self", "roles": roles, "teacher": teacher, "student": student}


def _student_query(db: Session, scope: dict[str, Any]):
    q = db.query(Student).filter(Student.is_deleted == False)
    if scope["kind"] == "department":
        q = q.join(Clazz, Clazz.id == Student.clazz_id).filter(Clazz.department_id == scope["department_id"])
    elif scope["kind"] == "clazzes":
        q = q.filter(Student.clazz_id.in_(scope.get("clazz_ids") or [-1]))
    elif scope["kind"] == "student":
        q = q.filter(Student.id == scope["student_id"])
    elif scope["kind"] == "teacher":
        q = q.filter(False)
    return q


def _clazz_query(db: Session, scope: dict[str, Any]):
    q = db.query(Clazz).filter(Clazz.is_deleted == False)
    if scope["kind"] == "department":
        q = q.filter(Clazz.department_id == scope["department_id"])
    elif scope["kind"] == "clazzes":
        q = q.filter(Clazz.id.in_(scope.get("clazz_ids") or [-1]))
    elif scope["kind"] == "student":
        q = q.filter(Clazz.id == scope["clazz_id"])
    elif scope["kind"] == "teacher":
        q = q.filter(False)
    return q


def _course_query(db: Session, scope: dict[str, Any]):
    q = db.query(Course).filter(Course.is_deleted == False)
    if scope["kind"] == "department":
        q = q.filter(Course.department_id == scope["department_id"])
    elif scope["kind"] == "teacher":
        q = q.filter(Course.teacher_id == scope["teacher_id"])
    elif scope["kind"] in {"clazzes", "student"}:
        clazz_ids = scope.get("clazz_ids") or [scope.get("clazz_id")]
        q = q.join(CourseSchedule, CourseSchedule.course_id == Course.id).filter(
            CourseSchedule.clazz_id.in_([cid for cid in clazz_ids if cid]),
            CourseSchedule.is_deleted == False,
        )
    return q.distinct()


def _schedule_query(db: Session, scope: dict[str, Any]):
    q = db.query(CourseSchedule).filter(CourseSchedule.is_deleted == False)
    if scope["kind"] == "department":
        q = q.join(Clazz, Clazz.id == CourseSchedule.clazz_id).filter(Clazz.department_id == scope["department_id"])
    elif scope["kind"] == "clazzes":
        q = q.filter(CourseSchedule.clazz_id.in_(scope.get("clazz_ids") or [-1]))
    elif scope["kind"] == "student":
        q = q.filter(CourseSchedule.clazz_id == scope["clazz_id"])
    elif scope["kind"] == "teacher":
        q = q.filter(CourseSchedule.teacher_id == scope["teacher_id"])
    return q


def _score_query(db: Session, scope: dict[str, Any]):
    q = db.query(Score).filter(Score.is_deleted == False)
    if scope["kind"] == "department":
        q = q.join(Student, Student.id == Score.student_id).join(Clazz, Clazz.id == Student.clazz_id).filter(
            Clazz.department_id == scope["department_id"]
        )
    elif scope["kind"] == "clazzes":
        q = q.join(Student, Student.id == Score.student_id).filter(Student.clazz_id.in_(scope.get("clazz_ids") or [-1]))
    elif scope["kind"] == "student":
        q = q.filter(Score.student_id == scope["student_id"])
    elif scope["kind"] == "teacher":
        q = q.filter(Score.scorer_id == scope["teacher_id"])
    return q


def _issue(code: str, title: str, severity: str, count: int, samples: Iterable[Any] = ()) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "severity": severity,
        "count": int(count or 0),
        "samples": list(samples),
    }


def data_health(user: User, db: Session) -> dict[str, Any]:
    scope = _scope(user, db)
    issues = []

    students_without_user = _student_query(db, scope).filter(Student.user_id == None).all()
    issues.append(_issue("student_without_user", "学生未关联登录账号", "high", len(students_without_user), [
        {"id": s.id, "name": s.name, "student_no": s.student_no} for s in students_without_user[:5]
    ]))

    clazzes_without_counselor = _clazz_query(db, scope).filter(Clazz.counselor_id == None).all()
    issues.append(_issue("clazz_without_counselor", "班级未配置班主任/辅导员", "medium", len(clazzes_without_counselor), [
        {"id": c.id, "name": c.name, "code": c.code} for c in clazzes_without_counselor[:5]
    ]))

    courses_without_teacher = _course_query(db, scope).filter(Course.teacher_id == None).all()
    issues.append(_issue("course_without_teacher", "课程未设置任课教师", "high", len(courses_without_teacher), [
        {"id": c.id, "name": c.name, "code": c.code} for c in courses_without_teacher[:5]
    ]))

    users_without_email = db.query(User).filter(User.is_deleted == False).filter(or_(User.email == None, User.email == "")).all()
    if scope["kind"] not in {"all", "department"}:
        users_without_email = []
    issues.append(_issue("user_without_email", "用户缺少邮箱", "medium", len(users_without_email), [
        {"id": u.id, "username": u.username, "real_name": u.real_name} for u in users_without_email[:5]
    ]))

    students_without_courses = _student_query(db, scope).outerjoin(StudentCourse).filter(StudentCourse.id == None).all()
    issues.append(_issue("student_without_course", "学生没有选课记录", "high", len(students_without_courses), [
        {"id": s.id, "name": s.name, "student_no": s.student_no} for s in students_without_courses[:5]
    ]))

    schedules_without_room = _schedule_query(db, scope).filter(CourseSchedule.classroom_id == None).all()
    issues.append(_issue("schedule_without_classroom", "课表缺少教室", "medium", len(schedules_without_room), [
        {"id": s.id, "course_id": s.course_id, "clazz_id": s.clazz_id} for s in schedules_without_room[:5]
    ]))

    mismatch_scores = _score_query(db, scope).join(Exam, Exam.id == Score.exam_id).filter(
        Score.course_id != Exam.course_id
    ).all()
    issues.append(_issue("score_course_mismatch", "成绩课程与考试课程不一致", "high", len(mismatch_scores), [
        {"id": s.id, "student_id": s.student_id, "exam_id": s.exam_id, "course_id": s.course_id} for s in mismatch_scores[:5]
    ]))

    missing_score_rows = []
    exams = db.query(Exam).filter(Exam.is_deleted == False, Exam.clazz_id != None).all()
    for exam in exams:
        if scope["kind"] == "department":
            clazz = db.query(Clazz).filter(Clazz.id == exam.clazz_id).first()
            if not clazz or clazz.department_id != scope["department_id"]:
                continue
        elif scope["kind"] == "clazzes" and exam.clazz_id not in (scope.get("clazz_ids") or []):
            continue
        elif scope["kind"] == "student":
            if exam.clazz_id != scope.get("clazz_id"):
                continue
        elif scope["kind"] == "teacher":
            course = db.query(Course).filter(Course.id == exam.course_id).first()
            if not course or course.teacher_id != scope["teacher_id"]:
                continue
        student_count = db.query(Student).filter(
            Student.clazz_id == exam.clazz_id,
            Student.is_deleted == False,
            Student.status == 1,
        ).count()
        score_count = db.query(Score).filter(
            Score.exam_id == exam.id,
            Score.is_deleted == False,
        ).count()
        if student_count > score_count:
            missing_score_rows.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "missing_count": student_count - score_count,
            })
    issues.append(_issue("exam_missing_scores", "已有考试但学生成绩未录全", "medium", len(missing_score_rows), missing_score_rows[:5]))

    conflict_count, conflict_samples = schedule_conflicts(db, scope)
    issues.append(_issue("schedule_conflict", "课表存在时间冲突", "high", conflict_count, conflict_samples[:5]))

    active = [item for item in issues if item["count"] > 0]
    severity_weight = {"high": 3, "medium": 2, "low": 1}
    active.sort(key=lambda item: (severity_weight.get(item["severity"], 0), item["count"]), reverse=True)
    return {
        "scope": scope["kind"],
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_issue_count": sum(item["count"] for item in active),
        "issue_type_count": len(active),
        "issues": active,
    }


def schedule_conflicts(db: Session, scope: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    items = _schedule_query(db, scope).order_by(
        CourseSchedule.term_id,
        CourseSchedule.weekday,
        CourseSchedule.start_section,
    ).all()
    conflicts = []
    for index, left in enumerate(items):
        for right in items[index + 1:]:
            if left.term_id != right.term_id or left.weekday != right.weekday:
                continue
            if left.start_section > right.end_section or left.end_section < right.start_section:
                continue
            if left.start_week > right.end_week or left.end_week < right.start_week:
                continue
            reason = None
            if left.teacher_id == right.teacher_id:
                reason = "teacher"
            elif left.clazz_id == right.clazz_id:
                reason = "clazz"
            elif left.classroom_id and left.classroom_id == right.classroom_id:
                reason = "classroom"
            if reason:
                conflicts.append({
                    "reason": reason,
                    "left_id": left.id,
                    "right_id": right.id,
                    "weekday": left.weekday,
                    "section": f"{left.start_section}-{left.end_section}",
                })
    return len(conflicts), conflicts


def dashboard_summary(user: User, db: Session) -> dict[str, Any]:
    scope = _scope(user, db)
    health = data_health(user, db)
    unread_mail = db.query(EmailMessage).filter(
        EmailMessage.is_deleted_by_recipient == False,
        EmailMessage.is_read == False,
        or_(EmailMessage.recipient_user_id == user.id, EmailMessage.recipient_email == (user.email or "").lower()),
    ).count()
    unread_notifications = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False).count()

    pending_leave_q = db.query(LeaveRequest).filter(LeaveRequest.is_deleted == False, LeaveRequest.status == "pending")
    if scope["kind"] == "department":
        pending_leave_q = pending_leave_q.filter(LeaveRequest.department_id == scope["department_id"])
    elif scope["kind"] == "clazzes":
        pending_leave_q = pending_leave_q.filter(LeaveRequest.clazz_id.in_(scope.get("clazz_ids") or [-1]))
    elif scope["kind"] in {"student", "teacher", "self"}:
        pending_leave_q = pending_leave_q.filter(False)

    today = date.today().isoweekday()
    today_schedule_q = _schedule_query(db, scope).filter(CourseSchedule.weekday == today)

    stats = {
        "students": _student_query(db, scope).count(),
        "teachers": db.query(Teacher).filter(Teacher.is_deleted == False).count() if scope["kind"] == "all" else 0,
        "courses": _course_query(db, scope).count(),
        "schedules": _schedule_query(db, scope).count(),
        "unread_mails": unread_mail,
        "unread_notifications": unread_notifications,
        "pending_leaves": pending_leave_q.count(),
        "health_issues": health["total_issue_count"],
    }
    todos = []
    if stats["pending_leaves"]:
        todos.append({"title": "待审核请假", "count": stats["pending_leaves"], "path": "/leave/review", "type": "leave"})
    if stats["health_issues"]:
        todos.append({"title": "数据体检异常", "count": stats["health_issues"], "path": "/operations/health", "type": "health"})
    if unread_mail:
        todos.append({"title": "未读邮件", "count": unread_mail, "path": "/email/inbox", "type": "email"})
    if unread_notifications:
        todos.append({"title": "未读通知", "count": unread_notifications, "path": "/notifications", "type": "notification"})

    recent_notifications = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(5).all()
    recent_announcements = db.query(Announcement).filter(Announcement.is_deleted == False, Announcement.status == 1).order_by(Announcement.created_at.desc()).limit(5).all()

    return {
        "scope": scope["kind"],
        "stats": stats,
        "todos": todos,
        "today_schedules": [
            {
                "id": s.id,
                "course_name": s.course.name if s.course else "",
                "clazz_name": s.clazz.name if s.clazz else "",
                "classroom_name": s.classroom.name if s.classroom else "",
                "section": f"{s.start_section}-{s.end_section}",
            }
            for s in today_schedule_q.options(
                joinedload(CourseSchedule.course),
                joinedload(CourseSchedule.clazz),
                joinedload(CourseSchedule.classroom),
            ).limit(8).all()
        ],
        "notifications": [_notification_dict(n) for n in recent_notifications],
        "announcements": [
            {"id": a.id, "title": a.title, "created_at": _format_value(a.created_at)}
            for a in recent_announcements
        ],
        "health": {
            "total_issue_count": health["total_issue_count"],
            "issue_type_count": health["issue_type_count"],
            "top_issues": health["issues"][:5],
        },
    }


def _notification_dict(item: Notification) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "category": item.category,
        "related_type": item.related_type,
        "related_id": item.related_id,
        "is_read": item.is_read,
        "created_at": _format_value(item.created_at),
    }


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _csv_response(rows: list[dict[str, Any]], headers: list[tuple[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in headers])
    for row in rows:
        writer.writerow([_format_value(row.get(key)) for key, _ in headers])
    return buffer.getvalue()


def export_csv(export_type: str, user: User, db: Session, student_id: int | None = None) -> tuple[str, str]:
    scope = _scope(user, db)
    if export_type == "students":
        rows = [
            {
                "student_no": s.student_no,
                "name": s.name,
                "clazz": s.clazz.name if s.clazz else "",
                "department": s.clazz.department.name if s.clazz and s.clazz.department else "",
                "status": s.status,
            }
            for s in _student_query(db, scope).options(joinedload(Student.clazz).joinedload(Clazz.department)).all()
        ]
        return "students.csv", _csv_response(rows, [("student_no", "学号"), ("name", "姓名"), ("clazz", "班级"), ("department", "院系"), ("status", "状态")])

    if export_type == "teachers":
        q = db.query(Teacher).options(joinedload(Teacher.department)).filter(Teacher.is_deleted == False)
        if scope["kind"] == "department":
            q = q.filter(Teacher.department_id == scope["department_id"])
        elif scope["kind"] == "teacher":
            q = q.filter(Teacher.id == scope["teacher_id"])
        rows = [{"employee_no": t.employee_no, "name": t.name, "department": t.department.name if t.department else "", "position": t.position, "title": t.title} for t in q.all()]
        return "teachers.csv", _csv_response(rows, [("employee_no", "工号"), ("name", "姓名"), ("department", "院系"), ("position", "岗位"), ("title", "职称")])

    if export_type == "courses":
        rows = [{"code": c.code, "name": c.name, "teacher": c.teacher.name if c.teacher else "", "credit": c.credit, "hours": c.hours} for c in _course_query(db, scope).options(joinedload(Course.teacher)).all()]
        return "courses.csv", _csv_response(rows, [("code", "课程代码"), ("name", "课程名称"), ("teacher", "任课教师"), ("credit", "学分"), ("hours", "学时")])

    if export_type == "schedules":
        rows = [
            {
                "course": s.course.name if s.course else "",
                "clazz": s.clazz.name if s.clazz else "",
                "teacher": s.teacher.name if s.teacher else "",
                "classroom": s.classroom.name if s.classroom else "",
                "weekday": s.weekday,
                "section": f"{s.start_section}-{s.end_section}",
                "week": f"{s.start_week}-{s.end_week}",
            }
            for s in _schedule_query(db, scope).options(
                joinedload(CourseSchedule.course),
                joinedload(CourseSchedule.clazz),
                joinedload(CourseSchedule.teacher),
                joinedload(CourseSchedule.classroom),
            ).all()
        ]
        return "schedules.csv", _csv_response(rows, [("course", "课程"), ("clazz", "班级"), ("teacher", "教师"), ("classroom", "教室"), ("weekday", "星期"), ("section", "节次"), ("week", "周次")])

    if export_type in {"scores", "transcript"}:
        q = _score_query(db, scope).options(joinedload(Score.student), joinedload(Score.course), joinedload(Score.exam))
        if export_type == "transcript":
            if student_id:
                q = q.filter(Score.student_id == student_id)
            elif scope["kind"] == "student":
                q = q.filter(Score.student_id == scope["student_id"])
        rows = [
            {
                "student_no": s.student.student_no if s.student else "",
                "student": s.student.name if s.student else "",
                "course": s.course.name if s.course else "",
                "exam": s.exam.name if s.exam else "",
                "score": s.score,
                "grade": s.grade,
                "rank": s.rank_in_class,
            }
            for s in q.all()
        ]
        filename = "transcript.csv" if export_type == "transcript" else "scores.csv"
        return filename, _csv_response(rows, [("student_no", "学号"), ("student", "姓名"), ("course", "课程"), ("exam", "考试"), ("score", "分数"), ("grade", "等级"), ("rank", "班级排名")])

    raise ValueError("unsupported export type")
