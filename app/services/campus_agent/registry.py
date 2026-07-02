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


ActionType = Literal["query", "create", "update", "delete", "send"]
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
    "query_my_profile": AgentTool(
        code="query_my_profile",
        name="查询我的身份信息",
        module="personal_academic",
        action="query",
        permission="dashboard",
        risk="low",
        description="查询当前登录用户的账号、角色以及关联的学生/教职工档案。",
    ),
    "query_my_teachers": AgentTool(
        code="query_my_teachers",
        name="查询我的老师",
        module="personal_academic",
        action="query",
        permission="schedule:my:list",
        risk="low",
        description="查询当前学生的班主任/辅导员和任课教师。",
    ),
    "query_my_courses": AgentTool(
        code="query_my_courses",
        name="查询我的课程",
        module="personal_academic",
        action="query",
        permission="schedule:my:list",
        risk="low",
        description="查询当前学生或教师相关课程。",
    ),
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
    "query_weather": AgentTool(
        code="query_weather",
        name="查询天气",
        module="common",
        action="query",
        permission="dashboard",
        risk="low",
        description="查询指定城市或默认城市的实时天气和近几日预报。",
    ),
    "send_email": AgentTool(
        code="send_email",
        name="发送邮件",
        module="email",
        action="send",
        permission="email:compose",
        risk="medium",
        description="向系统内用户或指定邮箱发送站内邮件。",
        confirm_required=True,
    ),
    "send_bulk_email": AgentTool(
        code="send_bulk_email",
        name="群发邮件",
        module="email",
        action="send",
        permission="email:compose",
        risk="high",
        description="按学生、教师或全体用户范围群发站内邮件。",
        confirm_required=True,
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
    "create_student": AgentTool(
        code="create_student",
        name="新增学生",
        module="people",
        action="create",
        permission="people:student:create",
        risk="medium",
        description="根据用户提供的信息新增学生及其登录账号。",
        confirm_required=True,
    ),
    "update_student": AgentTool(
        code="update_student",
        name="修改学生",
        module="people",
        action="update",
        permission="people:student:update",
        risk="medium",
        description="按学生 ID、姓名或学号定位学生，并修改允许变更的学生信息。",
        confirm_required=True,
    ),
    "delete_student": AgentTool(
        code="delete_student",
        name="停用学生",
        module="people",
        action="delete",
        permission="people:student:delete",
        risk="high",
        description="按学生 ID、姓名或学号定位学生，并软删除/停用学生档案。",
        confirm_required=True,
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
    "create_teacher": AgentTool(
        code="create_teacher",
        name="新增教师",
        module="people",
        action="create",
        permission="people:teacher:create",
        risk="medium",
        description="根据用户提供的信息新增教师及其登录账号。",
        confirm_required=True,
    ),
    "update_teacher": AgentTool(
        code="update_teacher",
        name="修改教师",
        module="people",
        action="update",
        permission="people:teacher:update",
        risk="medium",
        description="按教师 ID、姓名或工号定位教师，并修改允许变更的教师信息。",
        confirm_required=True,
    ),
    "delete_teacher": AgentTool(
        code="delete_teacher",
        name="停用教师",
        module="people",
        action="delete",
        permission="people:teacher:delete",
        risk="high",
        description="按教师 ID、姓名或工号定位教师，并软删除/停用教师档案。",
        confirm_required=True,
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
    "query_score": AgentTool(
        code="query_score",
        name="查询成绩",
        module="teaching",
        action="query",
        permission="teaching:score:list",
        risk="low",
        description="按学生、课程或考试查询权限范围内的成绩记录。",
    ),
    "create_course": AgentTool(
        code="create_course",
        name="新增课程",
        module="teaching",
        action="create",
        permission="teaching:course:create",
        risk="medium",
        description="根据用户提供的信息新增课程。",
        confirm_required=True,
    ),
    "update_course": AgentTool(
        code="update_course",
        name="修改课程",
        module="teaching",
        action="update",
        permission="teaching:course:update",
        risk="medium",
        description="按课程 ID、名称或编号定位课程，并修改课程信息。",
        confirm_required=True,
    ),
    "delete_course": AgentTool(
        code="delete_course",
        name="停用课程",
        module="teaching",
        action="delete",
        permission="teaching:course:delete",
        risk="high",
        description="按课程 ID、名称或编号定位课程，并软删除/停用课程。",
        confirm_required=True,
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
    "create_class": AgentTool(
        code="create_class",
        name="新增班级",
        module="org",
        action="create",
        permission="org:clazz:create",
        risk="medium",
        description="根据用户提供的信息新增班级。",
        confirm_required=True,
    ),
    "update_class": AgentTool(
        code="update_class",
        name="修改班级",
        module="org",
        action="update",
        permission="org:clazz:update",
        risk="medium",
        description="按班级 ID、名称或编号定位班级，并修改班级信息。",
        confirm_required=True,
    ),
    "delete_class": AgentTool(
        code="delete_class",
        name="停用班级",
        module="org",
        action="delete",
        permission="org:clazz:delete",
        risk="high",
        description="按班级 ID、名称或编号定位班级，并软删除/停用班级。",
        confirm_required=True,
    ),
    "query_department": AgentTool(
        code="query_department",
        name="查询院系",
        module="org",
        action="query",
        permission="org:department:list",
        risk="low",
        description="按院系名称或代码查询院系。",
    ),
    "create_department": AgentTool(
        code="create_department",
        name="新增院系",
        module="org",
        action="create",
        permission="org:department:create",
        risk="medium",
        description="根据用户提供的信息新增院系。",
        confirm_required=True,
    ),
    "update_department": AgentTool(
        code="update_department",
        name="修改院系",
        module="org",
        action="update",
        permission="org:department:update",
        risk="medium",
        description="按院系 ID、名称或代码定位院系，并修改院系信息。",
        confirm_required=True,
    ),
    "delete_department": AgentTool(
        code="delete_department",
        name="停用院系",
        module="org",
        action="delete",
        permission="org:department:delete",
        risk="high",
        description="按院系 ID、名称或代码定位院系，并软删除/停用院系。",
        confirm_required=True,
    ),
    "query_classroom": AgentTool(
        code="query_classroom",
        name="查询教室",
        module="schedule",
        action="query",
        permission="schedule:classroom:list",
        risk="low",
        description="按教室名称、楼栋、房间号查询教室。",
    ),
    "create_classroom": AgentTool(
        code="create_classroom",
        name="新增教室",
        module="schedule",
        action="create",
        permission="schedule:classroom:create",
        risk="medium",
        description="根据用户提供的信息新增教室。",
        confirm_required=True,
    ),
    "update_classroom": AgentTool(
        code="update_classroom",
        name="修改教室",
        module="schedule",
        action="update",
        permission="schedule:classroom:update",
        risk="medium",
        description="按教室 ID 或名称定位教室，并修改教室信息。",
        confirm_required=True,
    ),
    "delete_classroom": AgentTool(
        code="delete_classroom",
        name="停用教室",
        module="schedule",
        action="delete",
        permission="schedule:classroom:delete",
        risk="high",
        description="按教室 ID 或名称定位教室，并软删除/停用教室。",
        confirm_required=True,
    ),
    "query_term": AgentTool(
        code="query_term",
        name="查询学期",
        module="schedule",
        action="query",
        permission="schedule:term:list",
        risk="low",
        description="按学期名称或学年查询学期。",
    ),
    "create_term": AgentTool(
        code="create_term",
        name="新增学期",
        module="schedule",
        action="create",
        permission="schedule:term:create",
        risk="medium",
        description="根据用户提供的信息新增学期。",
        confirm_required=True,
    ),
    "update_term": AgentTool(
        code="update_term",
        name="修改学期",
        module="schedule",
        action="update",
        permission="schedule:term:update",
        risk="medium",
        description="按学期 ID、名称或学年定位学期，并修改学期信息。",
        confirm_required=True,
    ),
    "delete_term": AgentTool(
        code="delete_term",
        name="停用学期",
        module="schedule",
        action="delete",
        permission="schedule:term:delete",
        risk="high",
        description="按学期 ID、名称或学年定位学期，并软删除/停用学期。",
        confirm_required=True,
    ),
    "create_announcement": AgentTool(
        code="create_announcement",
        name="发布公告",
        module="announcement",
        action="create",
        permission="announcement:publish",
        risk="medium",
        description="根据用户提供的信息发布或保存公告。",
        confirm_required=True,
    ),
    "update_announcement": AgentTool(
        code="update_announcement",
        name="修改公告",
        module="announcement",
        action="update",
        permission="announcement:update",
        risk="medium",
        description="按公告 ID 或标题定位公告，并修改公告内容。",
        confirm_required=True,
    ),
    "delete_announcement": AgentTool(
        code="delete_announcement",
        name="删除公告",
        module="announcement",
        action="delete",
        permission="announcement:delete",
        risk="high",
        description="按公告 ID 或标题定位公告，并软删除公告。",
        confirm_required=True,
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
