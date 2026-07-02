"""Master/sub-agent facade for the football assistant.

This module intentionally wraps the existing handlers instead of replacing
them.  The master agent selects a domain sub-agent; each sub-agent owns only
its domain semantics and delegates real execution back to the orchestrator,
executor, and existing business services.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Callable, Protocol

from sqlalchemy.orm import Session, joinedload

from app.core.permissions import get_user_role_codes
from app.models.clazz import Clazz
from app.models.conversation import Conversation
from app.models.schedule import CourseSchedule
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.services.campus_agent.schemas import AgentResponse


@dataclass
class SubAgentContext:
    user: User
    conversation: Conversation
    session_id: str
    message: str
    mode: str
    memory_context: object | None = None
    file_ids: list[str] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class SubAgent(Protocol):
    code: str
    name: str

    def can_handle(self, ctx: SubAgentContext) -> bool:
        ...

    def handle(self, ctx: SubAgentContext) -> AgentResponse:
        ...


def _current_student(user: User, db: Session) -> Student | None:
    return db.query(Student).options(
        joinedload(Student.user),
        joinedload(Student.clazz).joinedload(Clazz.department),
        joinedload(Student.clazz).joinedload(Clazz.counselor).joinedload(Teacher.department),
    ).filter(Student.user_id == user.id, Student.is_deleted == False).first()


def _current_teacher(user: User, db: Session) -> Teacher | None:
    return db.query(Teacher).options(
        joinedload(Teacher.user),
        joinedload(Teacher.department),
    ).filter(Teacher.user_id == user.id, Teacher.is_deleted == False).first()


def _teacher_summary(teacher: Teacher) -> str:
    dept = getattr(getattr(teacher, "department", None), "name", "") or "未设置院系"
    title = f"，职称：{teacher.title}" if getattr(teacher, "title", None) else ""
    return f"{teacher.name}（工号：{teacher.employee_no}，岗位：{teacher.position or '未设置'}{title}，院系：{dept}）"


def _age_from_id_card(id_card: str | None) -> int | None:
    text = (id_card or "").strip()
    if not re.fullmatch(r"\d{17}[\dXx]", text):
        return None
    try:
        birth_year = int(text[6:10])
        birth_month = int(text[10:12])
        birth_day = int(text[12:14])
        today = date.today()
        return today.year - birth_year - ((today.month, today.day) < (birth_month, birth_day))
    except Exception:
        return None


def _role_can_view_teacher_private(user: User, db: Session, teacher: Teacher | None) -> bool:
    roles = get_user_role_codes(user, db)
    if "admin" in roles:
        return True
    return bool(teacher and teacher.user_id == user.id)


def _text_has_personal_relation_signal(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    patterns = [
        "我是谁",
        "我的信息",
        "我的身份",
        "我的档案",
        "我的老师",
        "我的班主任",
        "我的辅导员",
        "任课老师",
        "谁教我",
        "教我",
        "我的课程",
        "我有哪些课",
        "我有什么课",
        "我教哪些课",
    ]
    if any(item in compact for item in patterns):
        return True
    return bool(re.search(r"我的.*老师.*(?:年龄|多大|电话|邮箱|工号|岗位|职称)", compact))


class AcademicRelationAgent:
    code = "academic_relation"
    name = "教务关系子Agent"

    def __init__(self, db: Session, execute_academic: Callable[[str, dict, SubAgentContext], AgentResponse]):
        self.db = db
        self.execute_academic = execute_academic

    def can_handle(self, ctx: SubAgentContext) -> bool:
        return ctx.mode in {"auto", "academic_ops", "academic_tools"} and _text_has_personal_relation_signal(ctx.message)

    def handle(self, ctx: SubAgentContext) -> AgentResponse:
        text = ctx.message.strip()
        compact = re.sub(r"\s+", "", text)
        if "我的老师" in compact and any(word in compact for word in ["年龄", "多大", "岁数"]):
            return self._handle_my_teacher_age(ctx)
        if "我的老师" in compact and any(word in compact for word in ["电话", "手机号", "邮箱", "邮件"]):
            return self._handle_my_teacher_contact(ctx)
        return self._delegate_personal_tool(ctx)

    def _delegate_personal_tool(self, ctx: SubAgentContext) -> AgentResponse:
        compact = re.sub(r"\s+", "", ctx.message)
        if any(word in compact for word in ["我是谁", "我的信息", "我的身份", "我的档案"]):
            return self.execute_academic("query_my_profile", {}, ctx)
        if any(word in compact for word in ["我的课程", "我有哪些课", "我有什么课", "我教哪些课"]):
            return self.execute_academic("query_my_courses", {}, ctx)
        args: dict = {"teacher_scope": "all"}
        if "班主任" in compact or "辅导员" in compact:
            args["teacher_scope"] = "counselor"
        course_match = re.search(r"(?:谁教我|教我)([\u4e00-\u9fa5A-Za-z0-9·_-]{1,30})", compact)
        if course_match:
            args["teacher_scope"] = "course"
            args["course_keyword"] = course_match.group(1).strip("的课课程")
        return self.execute_academic("query_my_teachers", args, ctx)

    def _resolve_my_teachers(self, ctx: SubAgentContext) -> tuple[Student | None, list[tuple[str, Teacher]]]:
        student = _current_student(ctx.user, self.db)
        if not student:
            return None, []
        teachers: list[tuple[str, Teacher]] = []
        counselor = getattr(getattr(student, "clazz", None), "counselor", None)
        if counselor:
            teachers.append(("班主任/辅导员", counselor))
        rows = self.db.query(CourseSchedule).options(
            joinedload(CourseSchedule.course),
            joinedload(CourseSchedule.teacher).joinedload(Teacher.department),
        ).filter(
            CourseSchedule.clazz_id == student.clazz_id,
            CourseSchedule.status == 1,
            CourseSchedule.is_deleted == False,
        ).all()
        seen = {counselor.id} if counselor else set()
        for row in rows:
            teacher = getattr(row, "teacher", None)
            course = getattr(row, "course", None)
            if not teacher or teacher.id in seen:
                continue
            seen.add(teacher.id)
            teachers.append((getattr(course, "name", "") or "任课教师", teacher))
        return student, teachers

    def _handle_my_teacher_age(self, ctx: SubAgentContext) -> AgentResponse:
        teacher_self = _current_teacher(ctx.user, self.db)
        student, teachers = self._resolve_my_teachers(ctx)
        if not student:
            reply = "当前账号没有学生档案，因此没有“我的老师”这一学生视角信息。"
            if teacher_self:
                reply = "你当前是教职工账号，没有“我的老师”的学生视角；如果要查自己的档案，可以问“我是谁”。"
            return AgentResponse(reply=reply, mode="academic_ops", intent="academic_relation_teacher_age")
        if len(teachers) > 1:
            names = "、".join(f"{relation}：{teacher.name}" for relation, teacher in teachers[:8])
            reply = f"我找到了多位老师：{names}。你想问哪一位的年龄？例如“班主任的年龄”或“数据库老师的年龄”。"
            return AgentResponse(reply=reply, mode="academic_ops", intent="academic_relation_need_clarification")
        if not teachers:
            return AgentResponse(reply="暂未查到你的老师信息。", mode="academic_ops", intent="academic_relation_teacher_age")
        relation, teacher = teachers[0]
        if not _role_can_view_teacher_private(ctx.user, self.db, teacher):
            reply = f"我能确认你的{relation}是：{_teacher_summary(teacher)}。年龄属于教师个人隐私信息，当前学生账号不展示。"
            return AgentResponse(reply=reply, mode="academic_ops", intent="academic_relation_privacy_limited")
        age = _age_from_id_card(getattr(teacher, "id_card", None))
        reply = f"{teacher.name}老师今年约 {age} 岁。" if age is not None else f"系统中没有可用于计算 {teacher.name} 老师年龄的公开字段。"
        return AgentResponse(reply=reply, mode="academic_ops", intent="academic_relation_teacher_age")

    def _handle_my_teacher_contact(self, ctx: SubAgentContext) -> AgentResponse:
        student, teachers = self._resolve_my_teachers(ctx)
        if not student:
            return AgentResponse(reply="当前账号没有学生档案，因此没有“我的老师”这一学生视角信息。", mode="academic_ops", intent="academic_relation_teacher_contact")
        if not teachers:
            return AgentResponse(reply="暂未查到你的老师信息。", mode="academic_ops", intent="academic_relation_teacher_contact")
        lines = ["你可以联系这些老师："]
        for relation, teacher in teachers[:8]:
            user = getattr(teacher, "user", None)
            email = getattr(user, "email", "") if user else ""
            phone = getattr(user, "phone", "") if user else ""
            contact = []
            if email:
                contact.append(f"邮箱：{email}")
            if phone:
                contact.append(f"电话：{phone}")
            lines.append(f"- {relation}：{teacher.name}（{'; '.join(contact) if contact else '系统未公开联系方式'}）")
        return AgentResponse(reply="\n".join(lines), mode="academic_ops", intent="academic_relation_teacher_contact")


class HandlerSubAgent:
    def __init__(self, code: str, name: str, modes: set[str], handler: Callable[[SubAgentContext], AgentResponse]):
        self.code = code
        self.name = name
        self.modes = modes
        self.handler = handler

    def can_handle(self, ctx: SubAgentContext) -> bool:
        return ctx.mode in self.modes

    def handle(self, ctx: SubAgentContext) -> AgentResponse:
        return self.handler(ctx)


class MasterAgentRouter:
    """Dispatch to sub-agents after mode detection."""

    def __init__(self, agents: list[SubAgent]):
        self.agents = agents

    def dispatch(self, ctx: SubAgentContext) -> AgentResponse | None:
        for agent in self.agents:
            if agent.can_handle(ctx):
                return agent.handle(ctx)
        return None
