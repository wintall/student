"""Tool registry for the campus assistant.

The assistant may only call tools declared in this file.  The language model is
allowed to propose a tool name, but permission checks and execution are owned by
the backend.
"""
from dataclasses import dataclass, asdict
from typing import Literal

from sqlalchemy.orm import Session

from app.core.permissions import has_permission
from app.models.user import User


ActionType = Literal["query", "create", "update", "delete"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class AgentTool:
    code: str
    name: str
    module: str
    action: ActionType
    permission: str
    risk: RiskLevel
    description: str
    confirm_required: bool = False
    enabled: bool = True

    def to_dict(self, user: User | None = None, db: Session | None = None) -> dict:
        data = asdict(self)
        if user is not None and db is not None:
            data["available"] = has_permission(user, db, self.permission)
        return data


AGENT_TOOLS: dict[str, AgentTool] = {
    "query_my_schedule": AgentTool(
        code="query_my_schedule",
        name="查询我的课表",
        module="schedule",
        action="query",
        permission="schedule:my:list",
        risk="low",
        description="查询当前登录用户自己的课程表。",
    ),
    "query_my_attendance": AgentTool(
        code="query_my_attendance",
        name="查询我的考勤",
        module="attendance",
        action="query",
        permission="attendance:my:list",
        risk="low",
        description="查询当前登录用户自己的考勤记录。",
    ),
    "query_my_leave": AgentTool(
        code="query_my_leave",
        name="查询我的请假",
        module="leave",
        action="query",
        permission="leave:request:list",
        risk="low",
        description="查询当前登录用户自己的请假申请和审批状态。",
    ),
    "create_leave_request": AgentTool(
        code="create_leave_request",
        name="提交请假申请",
        module="leave",
        action="create",
        permission="leave:request:create",
        risk="medium",
        description="为当前登录用户提交请假申请。",
        confirm_required=True,
    ),
    "query_announcements": AgentTool(
        code="query_announcements",
        name="查询公告",
        module="announcement",
        action="query",
        permission="announcement:list:view",
        risk="low",
        description="查询校园公告列表。",
    ),
    "query_student": AgentTool(
        code="query_student",
        name="查询学生",
        module="people",
        action="query",
        permission="people:student:list",
        risk="low",
        description="按姓名、学号、班级等条件查询学生。",
    ),
    "query_teacher": AgentTool(
        code="query_teacher",
        name="查询教师",
        module="people",
        action="query",
        permission="people:teacher:list",
        risk="low",
        description="按姓名、工号、院系等条件查询教师。",
    ),
    "query_course": AgentTool(
        code="query_course",
        name="查询课程",
        module="teaching",
        action="query",
        permission="teaching:course:list",
        risk="low",
        description="按课程名、课程编号、院系等条件查询课程。",
    ),
    "query_class": AgentTool(
        code="query_class",
        name="查询班级",
        module="org",
        action="query",
        permission="org:clazz:list",
        risk="low",
        description="按班级名、班级编号、院系等条件查询班级。",
    ),
}


def get_tool(tool_code: str) -> AgentTool | None:
    tool = AGENT_TOOLS.get(tool_code)
    if not tool or not tool.enabled:
        return None
    return tool


def get_available_tools(user: User, db: Session) -> list[dict]:
    return [
        tool.to_dict(user, db)
        for tool in AGENT_TOOLS.values()
        if tool.enabled and has_permission(user, db, tool.permission)
    ]


def get_all_tools(user: User, db: Session) -> list[dict]:
    return [
        tool.to_dict(user, db)
        for tool in AGENT_TOOLS.values()
        if tool.enabled
    ]
