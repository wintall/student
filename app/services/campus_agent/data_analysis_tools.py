"""Data analysis tools for the football assistant."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.attendance import AttendanceRecord
from app.models.clazz import Clazz
from app.models.course import Course
from app.models.exam import Exam
from app.models.leave import LeaveRequest
from app.models.score import Score
from app.models.student import Student
from app.models.user import User
from app.services import operations_service
from app.services.campus_agent.llm_client import call_deepseek


DATA_ANALYSIS_WORDS = [
    "数据分析",
    "数据体检",
    "异常",
    "高危",
    "统计",
    "趋势",
    "挂科",
    "及格率",
    "平均分",
    "成绩分析",
    "考勤分析",
    "请假分析",
    "管理建议",
    "体检总结",
]


def should_use_data_analysis(message: str) -> bool:
    text = message or ""
    return any(word in text for word in DATA_ANALYSIS_WORDS)


def handle_data_analysis_message(*, user: User, db: Session, message: str) -> tuple[str, dict[str, Any]]:
    text = (message or "").strip()
    if _is_health_task(text):
        data = _health_summary(user, db)
        reply = _llm_or_fallback(text, data, _format_health_reply(data))
        return reply, data
    if _is_attendance_task(text):
        data = _attendance_summary(db)
        reply = _llm_or_fallback(text, data, _format_attendance_reply(data))
        return reply, data
    if _is_leave_task(text):
        data = _leave_summary(db)
        reply = _llm_or_fallback(text, data, _format_leave_reply(data))
        return reply, data
    if _is_score_task(text):
        data = _score_summary(db)
        reply = _llm_or_fallback(text, data, _format_score_reply(data))
        return reply, data
    data = _overview(user, db)
    reply = _llm_or_fallback(text, data, _format_overview_reply(data))
    return reply, data


def _is_health_task(text: str) -> bool:
    return any(word in text for word in ["体检", "异常", "高危", "风险", "整改"])


def _is_score_task(text: str) -> bool:
    return any(word in text for word in ["成绩", "分数", "挂科", "及格率", "平均分", "趋势"])


def _is_attendance_task(text: str) -> bool:
    return any(word in text for word in ["考勤", "迟到", "缺勤", "早退", "出勤"])


def _is_leave_task(text: str) -> bool:
    return "请假" in text


def _health_summary(user: User, db: Session) -> dict[str, Any]:
    health = operations_service.data_health(user, db)
    high = [item for item in health.get("issues", []) if item.get("severity") == "high"]
    medium = [item for item in health.get("issues", []) if item.get("severity") == "medium"]
    return {
        "task": "health",
        "scope": health.get("scope"),
        "checked_at": health.get("checked_at"),
        "total_issue_count": health.get("total_issue_count", 0),
        "issue_type_count": health.get("issue_type_count", 0),
        "high_issue_count": sum(item.get("count", 0) for item in high),
        "medium_issue_count": sum(item.get("count", 0) for item in medium),
        "top_issues": health.get("issues", [])[:8],
    }


def _score_summary(db: Session) -> dict[str, Any]:
    rows = db.query(Score).options(
        joinedload(Score.student).joinedload(Student.clazz),
        joinedload(Score.course),
        joinedload(Score.exam),
    ).filter(Score.is_deleted == False).all()
    scored = [float(item.score) for item in rows if item.score is not None]
    fail_rows = [item for item in rows if item.score is not None and float(item.score) < 60]
    course_stats: dict[str, list[float]] = defaultdict(list)
    clazz_stats: dict[str, list[float]] = defaultdict(list)
    for item in rows:
        if item.score is None:
            continue
        value = float(item.score)
        course_stats[item.course.name if item.course else "未知课程"].append(value)
        clazz = item.student.clazz.name if item.student and item.student.clazz else "未知班级"
        clazz_stats[clazz].append(value)
    weak_courses = _rank_score_groups(course_stats, low_first=True)
    strong_courses = _rank_score_groups(course_stats, low_first=False)
    weak_clazzes = _rank_score_groups(clazz_stats, low_first=True)
    return {
        "task": "score",
        "total_records": len(rows),
        "scored_records": len(scored),
        "missing_score_count": len(rows) - len(scored),
        "average_score": round(mean(scored), 2) if scored else None,
        "pass_rate": round((len(scored) - len(fail_rows)) * 100 / len(scored), 2) if scored else None,
        "fail_count": len(fail_rows),
        "weak_courses": weak_courses[:5],
        "strong_courses": strong_courses[:5],
        "weak_clazzes": weak_clazzes[:5],
    }


def _rank_score_groups(groups: dict[str, list[float]], *, low_first: bool) -> list[dict[str, Any]]:
    items = []
    for name, values in groups.items():
        if not values:
            continue
        fail_count = sum(1 for value in values if value < 60)
        items.append({
            "name": name,
            "count": len(values),
            "average": round(mean(values), 2),
            "fail_count": fail_count,
            "pass_rate": round((len(values) - fail_count) * 100 / len(values), 2),
        })
    return sorted(items, key=lambda item: (item["average"], -item["fail_count"]), reverse=not low_first)


def _attendance_summary(db: Session) -> dict[str, Any]:
    rows = db.query(AttendanceRecord).filter(AttendanceRecord.is_deleted == False).all()
    status_counter = Counter(item.status for item in rows)
    person_counter = Counter(item.person_type for item in rows)
    abnormal_statuses = {"late", "early_leave", "absent", "leave"}
    abnormal = [item for item in rows if item.status in abnormal_statuses]
    by_clazz = Counter(item.clazz.name if item.clazz else "未关联班级" for item in abnormal if item.person_type == "student")
    return {
        "task": "attendance",
        "total_records": len(rows),
        "student_records": person_counter.get("student", 0),
        "teacher_records": person_counter.get("teacher", 0),
        "status_counts": dict(status_counter),
        "abnormal_count": len(abnormal),
        "abnormal_rate": round(len(abnormal) * 100 / len(rows), 2) if rows else 0,
        "top_abnormal_classes": [{"name": name, "count": count} for name, count in by_clazz.most_common(5)],
    }


def _leave_summary(db: Session) -> dict[str, Any]:
    rows = db.query(LeaveRequest).filter(LeaveRequest.is_deleted == False).all()
    status_counter = Counter(item.status for item in rows)
    type_counter = Counter(item.leave_type for item in rows)
    applicant_counter = Counter(item.applicant_type for item in rows)
    pending = [item for item in rows if item.status == "pending"]
    return {
        "task": "leave",
        "total_requests": len(rows),
        "status_counts": dict(status_counter),
        "leave_type_counts": dict(type_counter),
        "applicant_type_counts": dict(applicant_counter),
        "pending_count": len(pending),
        "top_pending": [
            {
                "id": item.id,
                "applicant": item.student.name if item.student else (item.teacher.name if item.teacher else ""),
                "leave_type": item.leave_type,
                "reason": item.reason[:60],
            }
            for item in pending[:5]
        ],
    }


def _overview(user: User, db: Session) -> dict[str, Any]:
    health = _health_summary(user, db)
    score = _score_summary(db)
    attendance = _attendance_summary(db)
    leave = _leave_summary(db)
    totals = {
        "students": db.query(Student).filter(Student.is_deleted == False).count(),
        "courses": db.query(Course).filter(Course.is_deleted == False).count(),
        "exams": db.query(Exam).filter(Exam.is_deleted == False).count(),
        "scores": score["total_records"],
    }
    return {"task": "overview", "totals": totals, "health": health, "score": score, "attendance": attendance, "leave": leave}


def _llm_or_fallback(message: str, data: dict[str, Any], fallback: str) -> str:
    prompt = (
        "你是校园管理系统的数据分析助手。请基于给定 JSON 数据，用中文给出管理层可读的分析。\n"
        "要求：先给结论，再列关键指标，最后给 3 条可执行建议。不要编造 JSON 之外的数据。"
    )
    reply = call_deepseek(
        system_prompt=prompt,
        user_message=f"用户问题：{message}\n\n数据：{data}",
        temperature=0.25,
        max_tokens=1000,
    )
    return reply or fallback


def _format_health_reply(data: dict[str, Any]) -> str:
    lines = [
        f"数据体检共发现 {data['total_issue_count']} 个异常，涉及 {data['issue_type_count']} 类问题。",
        f"其中高危异常 {data['high_issue_count']} 个，中危异常 {data['medium_issue_count']} 个。",
    ]
    if data["top_issues"]:
        lines.append("优先处理这些问题：")
        for item in data["top_issues"][:5]:
            lines.append(f"- {item['title']}：{item['count']} 个，等级：{item['severity']}")
    lines.append("建议先修高危数据完整性问题，再处理成绩未录全、课表冲突等业务一致性问题。")
    return "\n".join(lines)


def _format_score_reply(data: dict[str, Any]) -> str:
    lines = [
        f"成绩记录共 {data['total_records']} 条，已录入分数 {data['scored_records']} 条，未录入 {data['missing_score_count']} 条。",
        f"平均分：{data['average_score'] if data['average_score'] is not None else '暂无'}，及格率：{data['pass_rate'] if data['pass_rate'] is not None else '暂无'}%。",
        f"不及格记录：{data['fail_count']} 条。",
    ]
    if data["weak_courses"]:
        lines.append("需要关注的课程：")
        for item in data["weak_courses"][:5]:
            lines.append(f"- {item['name']}：平均分 {item['average']}，及格率 {item['pass_rate']}%，样本 {item['count']} 条")
    return "\n".join(lines)


def _format_attendance_reply(data: dict[str, Any]) -> str:
    lines = [
        f"考勤记录共 {data['total_records']} 条，异常记录 {data['abnormal_count']} 条，异常率 {data['abnormal_rate']}%。",
        f"状态分布：{data['status_counts']}",
    ]
    if data["top_abnormal_classes"]:
        lines.append("学生异常较集中的班级：")
        for item in data["top_abnormal_classes"]:
            lines.append(f"- {item['name']}：{item['count']} 条")
    return "\n".join(lines)


def _format_leave_reply(data: dict[str, Any]) -> str:
    lines = [
        f"请假申请共 {data['total_requests']} 条，待审批 {data['pending_count']} 条。",
        f"状态分布：{data['status_counts']}",
        f"类型分布：{data['leave_type_counts']}",
    ]
    return "\n".join(lines)


def _format_overview_reply(data: dict[str, Any]) -> str:
    totals = data["totals"]
    lines = [
        "当前系统数据概览：",
        f"- 学生 {totals['students']} 人，课程 {totals['courses']} 门，考试 {totals['exams']} 场，成绩记录 {totals['scores']} 条。",
        f"- 数据体检异常 {data['health']['total_issue_count']} 个。",
        f"- 成绩平均分 {data['score']['average_score']}，及格率 {data['score']['pass_rate']}%。",
        f"- 考勤异常率 {data['attendance']['abnormal_rate']}%，待审批请假 {data['leave']['pending_count']} 条。",
        "建议：先处理高危数据异常，再按课程和班级复盘成绩、考勤和请假集中问题。",
    ]
    return "\n".join(lines)
