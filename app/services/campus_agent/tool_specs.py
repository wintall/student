"""Schema metadata for campus assistant natural-language planning.

This file is the bridge between open-ended language and the guarded backend
tool registry.  Future modules should be added here first, then implemented in
tool_handlers.py and protected in registry.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.campus_agent.registry import AGENT_TOOLS


@dataclass(frozen=True)
class ToolFieldSpec:
    name: str
    description: str
    required_for_create: bool = False
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSpec:
    code: str
    object_name: str
    action: str
    description: str
    examples: tuple[str, ...] = ()
    fields: tuple[ToolFieldSpec, ...] = ()
    target_required: bool = False
    aliases: tuple[str, ...] = ()
    notes: str = ""

    def to_prompt_dict(self) -> dict:
        tool = AGENT_TOOLS.get(self.code)
        return {
            "tool_code": self.code,
            "name": tool.name if tool else self.code,
            "action": self.action,
            "object_name": self.object_name,
            "description": self.description,
            "target_required": self.target_required,
            "aliases": list(self.aliases),
            "fields": [
                {
                    "name": field.name,
                    "description": field.description,
                    "required_for_create": field.required_for_create,
                    "aliases": list(field.aliases),
                }
                for field in self.fields
            ],
            "examples": list(self.examples),
            "notes": self.notes,
        }


COMMON_PERSON_FIELDS = (
    ToolFieldSpec("name", "姓名", True, ("姓名", "名字")),
    ToolFieldSpec("gender", "性别，男=1，女=2", True, ("性别",)),
    ToolFieldSpec("id_card", "身份证号", True, ("身份证", "身份证号")),
    ToolFieldSpec("phone", "手机号或联系电话", False, ("手机", "手机号", "电话")),
    ToolFieldSpec("email", "邮箱", False, ("邮箱", "邮件地址")),
)


TOOL_SPECS: dict[str, ToolSpec] = {
    "query_my_profile": ToolSpec(
        "query_my_profile",
        "我的身份",
        "query",
        "查询当前登录用户的账号、角色、学生档案或教职工档案。",
        aliases=("我是谁", "我的信息", "我的身份", "我的个人资料", "我在哪个班", "我属于哪个学院"),
        fields=(ToolFieldSpec("profile_field", "可选：class/department/role/basic"),),
        examples=("我是谁", "我的信息", "我在哪个班", "我属于哪个学院"),
    ),
    "query_my_teachers": ToolSpec(
        "query_my_teachers",
        "我的老师",
        "query",
        "查询当前学生的班主任、辅导员、任课教师，也支持按课程关键词筛选。",
        aliases=("我的老师", "我的班主任", "我的辅导员", "任课老师", "谁教我"),
        fields=(ToolFieldSpec("teacher_scope", "all/counselor/course"), ToolFieldSpec("course_keyword", "课程关键词")),
        examples=("我的老师是谁", "我的班主任是谁", "谁教我数据库"),
    ),
    "query_my_courses": ToolSpec(
        "query_my_courses",
        "我的课程",
        "query",
        "查询当前学生或教师相关课程。",
        aliases=("我的课程", "我有哪些课", "我这学期学什么", "我教哪些课"),
        fields=(ToolFieldSpec("keyword", "课程关键词"),),
        examples=("我有哪些课", "我的课程有哪些", "我教哪些课"),
    ),
    "query_student": ToolSpec(
        code="query_student",
        object_name="学生",
        action="query",
        description="查询学生列表、单个学生资料，或追问学生字段。",
        aliases=("学生", "同学", "学号"),
        fields=(ToolFieldSpec("keyword", "姓名、学号、班级等搜索关键词"), ToolFieldSpec("requested_field", "只问某个字段时使用，如 gender/email/clazz_name/department_name/status/student_no/name")),
        examples=("查询所有学生", "杨杰的性别是啥", "学号 S20230006 是谁", "张芳在哪个班"),
    ),
    "create_student": ToolSpec(
        code="create_student",
        object_name="学生",
        action="create",
        description="新增学生并创建/关联学生档案。",
        aliases=("新增学生", "添加学生", "录入学生"),
        fields=COMMON_PERSON_FIELDS + (
            ToolFieldSpec("student_no", "学号", True, ("学号",)),
            ToolFieldSpec("clazz_keyword", "班级名称或班级编号", True, ("班级",)),
            ToolFieldSpec("enrollment_date", "入学日期，YYYY-MM-DD", False, ("入学日期",)),
        ),
        examples=("新增学生李雷 学号S20260001 性别男 身份证号... 班级计算机2401",),
    ),
    "update_student": ToolSpec(
        code="update_student",
        object_name="学生",
        action="update",
        description="修改学生资料。target_keyword 定位学生，changes 放要修改的字段。",
        target_required=True,
        aliases=("修改学生", "更新学生", "学生改为"),
        fields=COMMON_PERSON_FIELDS + (
            ToolFieldSpec("student_no", "学号", False, ("学号",)),
            ToolFieldSpec("clazz_keyword", "班级名称或班级编号", False, ("班级",)),
            ToolFieldSpec("status", "状态：在读=1，休学=2，毕业=3，退学=0", False, ("状态",)),
        ),
        examples=("林华的性别改为男", "把张芳邮箱改为 a@b.com", "学生S20230006转到数学2302班"),
    ),
    "delete_student": ToolSpec(
        code="delete_student",
        object_name="学生",
        action="delete",
        description="停用或删除学生档案，需要确认。",
        target_required=True,
        aliases=("删除学生", "停用学生", "注销学生"),
        fields=(ToolFieldSpec("target_keyword", "姓名、学号或ID"),),
        examples=("删除学生张三", "停用学号S20230006"),
    ),
    "query_teacher": ToolSpec(
        code="query_teacher",
        object_name="教师",
        action="query",
        description="查询教师资料。",
        aliases=("教师", "老师", "教职工", "工号"),
        fields=(ToolFieldSpec("keyword", "姓名、工号、院系等搜索关键词"),),
        examples=("查询所有教师", "查询老师张伟"),
    ),
    "create_teacher": ToolSpec(
        code="create_teacher",
        object_name="教师",
        action="create",
        description="新增教师档案。",
        aliases=("新增教师", "添加老师", "录入教职工"),
        fields=COMMON_PERSON_FIELDS + (
            ToolFieldSpec("employee_no", "工号", True, ("工号",)),
            ToolFieldSpec("position", "岗位/职位", True, ("岗位", "职位")),
            ToolFieldSpec("title", "职称", False, ("职称",)),
            ToolFieldSpec("department_keyword", "院系名称或代码", False, ("院系", "学院")),
            ToolFieldSpec("entry_date", "入职日期，YYYY-MM-DD", False, ("入职日期",)),
        ),
        examples=("新增教师王明 工号T2026001 性别男 身份证号... 岗位教师 院系计算机学院",),
    ),
    "update_teacher": ToolSpec(
        code="update_teacher",
        object_name="教师",
        action="update",
        description="修改教师资料。",
        target_required=True,
        aliases=("修改教师", "老师改为", "更新教职工"),
        fields=COMMON_PERSON_FIELDS + (
            ToolFieldSpec("employee_no", "工号", False, ("工号",)),
            ToolFieldSpec("position", "岗位/职位", False, ("岗位", "职位")),
            ToolFieldSpec("title", "职称", False, ("职称",)),
            ToolFieldSpec("department_keyword", "院系名称或代码", False, ("院系", "学院")),
            ToolFieldSpec("status", "状态：在职=1，离职=0", False, ("状态",)),
        ),
        examples=("张伟职称改为教授", "把老师李强停用"),
    ),
    "delete_teacher": ToolSpec(
        code="delete_teacher",
        object_name="教师",
        action="delete",
        description="停用或删除教师档案，需要确认。",
        target_required=True,
        aliases=("删除教师", "停用老师", "注销教职工"),
        fields=(ToolFieldSpec("target_keyword", "姓名、工号或ID"),),
        examples=("删除教师张伟",),
    ),
    "query_course": ToolSpec("query_course", "课程", "query", "查询课程。", aliases=("课程", "科目"), fields=(ToolFieldSpec("keyword", "课程名、编号、院系关键词"),), examples=("查询所有课程", "查询高等数学")),
    "create_course": ToolSpec("create_course", "课程", "create", "新增课程。", aliases=("新增课程", "添加课程"), fields=(ToolFieldSpec("name", "课程名", True), ToolFieldSpec("code", "课程编号", True), ToolFieldSpec("credit", "学分", True), ToolFieldSpec("hours", "学时", True), ToolFieldSpec("department_keyword", "院系", False), ToolFieldSpec("teacher_keyword", "任课教师", False), ToolFieldSpec("course_type", "课程类型：必修=1，选修=2，公共课=3", False)), examples=("新增课程人工智能导论 编号AI101 学分3 学时48")),
    "update_course": ToolSpec("update_course", "课程", "update", "修改课程。", target_required=True, aliases=("修改课程", "课程改为"), fields=(ToolFieldSpec("credit", "学分"), ToolFieldSpec("hours", "学时"), ToolFieldSpec("teacher_keyword", "任课教师"), ToolFieldSpec("department_keyword", "院系"), ToolFieldSpec("status", "状态")), examples=("高等数学学分改成4",)),
    "delete_course": ToolSpec("delete_course", "课程", "delete", "停用课程。", target_required=True, aliases=("删除课程", "停用课程"), fields=(ToolFieldSpec("target_keyword", "课程名、编号或ID"),)),
    "query_class": ToolSpec("query_class", "班级", "query", "查询班级。", aliases=("班级", "班号"), fields=(ToolFieldSpec("keyword", "班级名、编号或院系关键词"),), examples=("查询计算机2301班",)),
    "create_class": ToolSpec("create_class", "班级", "create", "新增班级。", aliases=("新增班级", "创建班级"), fields=(ToolFieldSpec("name", "班级名称", True), ToolFieldSpec("code", "班级编号", True), ToolFieldSpec("grade", "年级", False), ToolFieldSpec("department_keyword", "院系", False), ToolFieldSpec("counselor_keyword", "班主任/辅导员", False))),
    "update_class": ToolSpec("update_class", "班级", "update", "修改班级。", target_required=True, aliases=("修改班级", "班级改为"), fields=(ToolFieldSpec("name", "班级名称"), ToolFieldSpec("grade", "年级"), ToolFieldSpec("department_keyword", "院系"), ToolFieldSpec("counselor_keyword", "班主任/辅导员"), ToolFieldSpec("status", "状态"))),
    "delete_class": ToolSpec("delete_class", "班级", "delete", "停用班级。", target_required=True, aliases=("删除班级", "停用班级")),
    "query_department": ToolSpec("query_department", "院系", "query", "查询院系。", aliases=("院系", "学院", "系部"), fields=(ToolFieldSpec("keyword", "院系名或代码"),)),
    "create_department": ToolSpec("create_department", "院系", "create", "新增院系。", aliases=("新增院系", "新增学院"), fields=(ToolFieldSpec("name", "院系名称", True), ToolFieldSpec("code", "院系代码", True), ToolFieldSpec("description", "描述", False))),
    "update_department": ToolSpec("update_department", "院系", "update", "修改院系。", target_required=True, aliases=("修改院系", "学院改为"), fields=(ToolFieldSpec("name", "院系名称"), ToolFieldSpec("code", "院系代码"), ToolFieldSpec("description", "描述"), ToolFieldSpec("status", "状态"))),
    "delete_department": ToolSpec("delete_department", "院系", "delete", "停用院系。", target_required=True, aliases=("删除院系", "停用学院")),
    "query_classroom": ToolSpec("query_classroom", "教室", "query", "查询教室。", aliases=("教室", "楼栋", "房间"), fields=(ToolFieldSpec("keyword", "教室名、楼栋或房间号"),)),
    "create_classroom": ToolSpec("create_classroom", "教室", "create", "新增教室。", aliases=("新增教室", "添加教室"), fields=(ToolFieldSpec("name", "教室名称", True), ToolFieldSpec("building", "楼栋", True), ToolFieldSpec("room_no", "房间号", True), ToolFieldSpec("capacity", "容量", True), ToolFieldSpec("campus", "校区", False), ToolFieldSpec("room_type", "类型", False))),
    "update_classroom": ToolSpec("update_classroom", "教室", "update", "修改教室。", target_required=True, aliases=("修改教室", "教室改为"), fields=(ToolFieldSpec("capacity", "容量"), ToolFieldSpec("building", "楼栋"), ToolFieldSpec("room_no", "房间号"), ToolFieldSpec("campus", "校区"), ToolFieldSpec("room_type", "类型"), ToolFieldSpec("status", "状态"))),
    "delete_classroom": ToolSpec("delete_classroom", "教室", "delete", "停用教室。", target_required=True, aliases=("删除教室", "停用教室")),
    "query_term": ToolSpec("query_term", "学期", "query", "查询学期。", aliases=("学期", "学年"), fields=(ToolFieldSpec("keyword", "学期名或学年"),)),
    "create_term": ToolSpec("create_term", "学期", "create", "新增学期。", aliases=("新增学期", "创建学期"), fields=(ToolFieldSpec("name", "学期名称", True), ToolFieldSpec("academic_year", "学年", True), ToolFieldSpec("semester", "第几学期", True), ToolFieldSpec("start_date", "开始日期", True), ToolFieldSpec("end_date", "结束日期", True), ToolFieldSpec("week_count", "教学周数", True), ToolFieldSpec("is_current", "是否当前学期", False))),
    "update_term": ToolSpec("update_term", "学期", "update", "修改学期。", target_required=True, aliases=("修改学期", "学期改为"), fields=(ToolFieldSpec("name", "学期名称"), ToolFieldSpec("academic_year", "学年"), ToolFieldSpec("semester", "第几学期"), ToolFieldSpec("start_date", "开始日期"), ToolFieldSpec("end_date", "结束日期"), ToolFieldSpec("week_count", "教学周数"), ToolFieldSpec("is_current", "是否当前学期"), ToolFieldSpec("status", "状态"))),
    "delete_term": ToolSpec("delete_term", "学期", "delete", "停用学期。", target_required=True, aliases=("删除学期", "停用学期")),
    "query_announcements": ToolSpec("query_announcements", "公告", "query", "查询公告。", aliases=("公告", "通知"), fields=(ToolFieldSpec("keyword", "标题或内容关键词"),)),
    "create_announcement": ToolSpec("create_announcement", "公告", "create", "发布公告。", aliases=("发布公告", "新增通知"), fields=(ToolFieldSpec("title", "标题", True), ToolFieldSpec("content", "正文内容", True), ToolFieldSpec("type", "类型：通知=1，活动=2，紧急=3", False), ToolFieldSpec("is_top", "是否置顶", False))),
    "update_announcement": ToolSpec("update_announcement", "公告", "update", "修改公告。", target_required=True, aliases=("修改公告", "通知改为"), fields=(ToolFieldSpec("title", "标题"), ToolFieldSpec("content", "内容"), ToolFieldSpec("type", "类型"), ToolFieldSpec("is_top", "是否置顶"), ToolFieldSpec("status", "状态"))),
    "delete_announcement": ToolSpec("delete_announcement", "公告", "delete", "删除公告。", target_required=True, aliases=("删除公告", "撤下通知")),
    "query_score": ToolSpec("query_score", "成绩", "query", "查询成绩。", aliases=("成绩", "分数", "考试成绩"), fields=(ToolFieldSpec("keyword", "学生、课程或考试关键词"),), examples=("查询杨杰的成绩", "查询高等数学成绩")),
    "query_my_schedule": ToolSpec("query_my_schedule", "我的课表", "query", "查询当前用户课表。", aliases=("我的课表", "今天有什么课", "在哪上课")),
    "query_my_attendance": ToolSpec("query_my_attendance", "我的考勤", "query", "查询当前用户考勤。", aliases=("我的考勤", "出勤", "迟到", "缺勤")),
    "query_my_leave": ToolSpec("query_my_leave", "我的请假", "query", "查询当前用户请假申请。", aliases=("我的请假", "请假进度", "请假状态")),
    "query_weather": ToolSpec("query_weather", "天气", "query", "查询天气。", aliases=("天气", "气温", "下雨"), fields=(ToolFieldSpec("city", "城市名，不明确时可为空"),), examples=("查询北京天气", "今天上海天气怎么样")),
    "send_email": ToolSpec("send_email", "邮件", "send", "给系统内用户或指定邮箱发送站内邮件。", aliases=("发邮件", "写信", "发信"), fields=(ToolFieldSpec("recipient_keyword", "收件人姓名、用户名、学号、工号或邮箱"), ToolFieldSpec("recipient_email", "收件邮箱"), ToolFieldSpec("subject", "邮件主题", True), ToolFieldSpec("body", "邮件正文", True)), examples=("给学生吴浩发邮件", "给teacher01发邮件 主题是测试 内容是hello")),
    "send_bulk_email": ToolSpec("send_bulk_email", "群发邮件", "send", "按学生、教师或全体用户范围群发邮件。", aliases=("群发邮件", "给所有学生发邮件", "给全体教师发信"), fields=(ToolFieldSpec("recipient_scope", "students/teachers/all_users"), ToolFieldSpec("subject", "邮件主题", True), ToolFieldSpec("body", "邮件正文", True)), examples=("给所有学生发一份邮件 主题是通知 内容是明天开会",)),
}


def specs_for_prompt(tool_codes: set[str] | None = None) -> list[dict]:
    codes = tool_codes or set(TOOL_SPECS)
    return [spec.to_prompt_dict() for code, spec in TOOL_SPECS.items() if code in codes]
