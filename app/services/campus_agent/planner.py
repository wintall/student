"""Rule-based planning layer for the campus assistant.

The planner converts natural language into a registered tool plus raw
arguments.  It is intentionally deterministic: CRUD tools must remain
auditable and all real execution still goes through CampusAgentExecutor.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.campus_agent.schemas import AgentPlan


CREATE_TOOL_CODES = {
    "create_student",
    "create_teacher",
    "create_course",
    "create_class",
    "create_department",
    "create_classroom",
    "create_term",
    "create_announcement",
    "create_leave_request",
    "send_email",
    "send_bulk_email",
}

QUERY_TOOL_CODES = {
    "query_my_schedule",
    "query_my_attendance",
    "query_my_leave",
    "query_announcements",
    "query_student",
    "query_teacher",
    "query_course",
    "query_score",
    "query_class",
    "query_department",
    "query_classroom",
    "query_term",
    "query_weather",
}

TOOL_OBJECTS = {
    "update_student": "student",
    "delete_student": "student",
    "update_teacher": "teacher",
    "delete_teacher": "teacher",
    "update_course": "course",
    "delete_course": "course",
    "update_class": "class",
    "delete_class": "class",
    "update_department": "department",
    "delete_department": "department",
    "update_classroom": "classroom",
    "delete_classroom": "classroom",
    "update_term": "term",
    "delete_term": "term",
    "update_announcement": "announcement",
    "delete_announcement": "announcement",
}

TARGET_ALIASES = {
    "student": ["学生", "同学"],
    "teacher": ["教师", "老师", "教职工"],
    "course": ["课程"],
    "class": ["班级"],
    "department": ["院系", "学院", "系部"],
    "classroom": ["教室"],
    "term": ["学期"],
    "announcement": ["公告", "通知"],
}

OBJECT_TOOL_MAP = {
    "student": {
        "query": "query_student",
        "create": "create_student",
        "update": "update_student",
        "delete": "delete_student",
        "words": ["学生", "学号", "同学"],
    },
    "teacher": {
        "query": "query_teacher",
        "create": "create_teacher",
        "update": "update_teacher",
        "delete": "delete_teacher",
        "words": ["教师", "老师", "教职工", "工号"],
    },
    "course": {
        "query": "query_course",
        "create": "create_course",
        "update": "update_course",
        "delete": "delete_course",
        "words": ["课程", "课程编号", "课程代码"],
    },
    "class": {
        "query": "query_class",
        "create": "create_class",
        "update": "update_class",
        "delete": "delete_class",
        "words": ["班级", "班号"],
    },
    "department": {
        "query": "query_department",
        "create": "create_department",
        "update": "update_department",
        "delete": "delete_department",
        "words": ["院系", "学院", "系部"],
    },
    "classroom": {
        "query": "query_classroom",
        "create": "create_classroom",
        "update": "update_classroom",
        "delete": "delete_classroom",
        "words": ["教室", "楼栋", "房间"],
    },
    "term": {
        "query": "query_term",
        "create": "create_term",
        "update": "update_term",
        "delete": "delete_term",
        "words": ["学期", "学年"],
    },
    "announcement": {
        "query": "query_announcements",
        "create": "create_announcement",
        "update": "update_announcement",
        "delete": "delete_announcement",
        "words": ["公告", "通知"],
    },
}

CREATE_WORDS = ["新增", "添加", "创建", "录入", "新建", "发布"]
UPDATE_WORDS = ["修改", "更新", "调整", "改一下", "更改", "设置", "改成", "改为", "转到", "变成", "补充", "填写", "填入", "录入"]
DELETE_WORDS = ["删除", "停用", "禁用", "移除", "注销"]
QUERY_WORDS = ["查", "查询", "搜索", "找", "看一下", "看看", "列出", "显示", "全部", "所有"]
CONTINUATION_WORDS = ["继续", "下一页", "下页", "显示更多", "更多", "全部显示", "显示全部", "显示所有", "显示全部的", "能显示全部", "可以显示全部", "都显示", "完整显示"]
PRONOUN_WORDS = ["这个", "这个人", "这个学生", "这名学生", "该学生", "他", "她", "TA", "ta"]

FIELD_UPDATE_TOOL_HINTS = [
    ("update_student", ["性别", "手机号", "电话", "邮箱", "班级", "状态", "学号", "姓名", "名字"]),
    ("update_teacher", ["工号", "岗位", "职位", "职称", "入职日期"]),
    ("update_course", ["学分", "学时", "课程类型", "任课教师", "教师", "老师"]),
    ("update_classroom", ["容量", "楼栋", "房间号", "校区", "教室类型"]),
    ("update_term", ["学年", "学期序号", "开始日期", "结束日期", "周数", "教学周数", "当前学期"]),
    ("update_announcement", ["标题", "内容", "置顶", "取消置顶"]),
    ("update_department", ["院系代码", "学院代码", "描述"]),
]

QUERY_FIELD_HINTS = {
    "student": ["性别", "手机号", "电话", "邮箱", "班级", "院系", "学院", "状态", "学号", "姓名", "名字"],
    "teacher": ["工号", "岗位", "职位", "职称", "院系", "学院", "手机号", "电话", "邮箱", "状态", "姓名", "名字"],
}


def compact_message(message: str) -> str:
    return re.sub(r"[\s,，。.?？!！:：;；、]+", "", message or "")


def is_capability_question(message: str) -> bool:
    text = compact_message(message)
    keywords = [
        "你能做什么",
        "能做什么",
        "可以做什么",
        "会做什么",
        "你会做什么",
        "能干什么",
        "可以干什么",
        "能操作什么",
        "能操作哪些",
        "有哪些工具",
        "有什么工具",
        "有什么功能",
        "功能清单",
        "工具清单",
        "权限内",
        "我的权限",
        "能查什么",
        "能查哪些",
    ]
    return any(keyword in text for keyword in keywords)


def parse_confirmation(message: str) -> tuple[str, int] | None:
    text = (message or "").strip()
    if re.fullmatch(r"#?\d+", text):
        return "确认", int(text.lstrip("#"))
    match = re.search(r"(确认|执行|同意|取消|放弃)\s*(?:动作|操作|ID|id)?\s*#?(\d+)", text)
    if not match:
        if text in {"确认", "执行", "同意", "取消", "放弃"}:
            return text, 0
        return None
    return match.group(1), int(match.group(2))


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _detect_object(text: str) -> str | None:
    if re.search(r"[Tt]\d{6,}", text) or _contains_any(text, ["岗位", "职位", "职称", "入职日期"]):
        return "teacher"
    if re.search(r"[Ss]\d{6,}", text):
        return "student"
    if _contains_any(text, ["邮箱", "邮件地址", "手机号", "电话"]) and _contains_any(text, ["补充", "添加", "设置", "修改", "更新", "填写", "填入", "录入"]):
        if _contains_any(text, ["教师", "老师", "教职工", "工号"]):
            return "teacher"
        return "student"
    for object_key, config in OBJECT_TOOL_MAP.items():
        if _contains_any(text, config["words"]):
            return object_key
    return None


def _detect_action(text: str) -> str | None:
    if _contains_any(text, DELETE_WORDS):
        return "delete"
    if _contains_any(text, UPDATE_WORDS):
        return "update"
    if _contains_any(text, CREATE_WORDS):
        return "create"
    if _contains_any(text, QUERY_WORDS):
        return "query"
    return None


def _detect_academic_tool(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None

    if "天气" in text:
        return "query_weather"

    if any(word in text for word in ["邮箱", "邮件地址"]) and any(word in text for word in ["补充", "添加", "设置", "修改", "更新", "填写", "填入", "录入", "改为", "改成"]):
        inferred_update_tool = _detect_field_update_tool(text)
        if inferred_update_tool:
            return inferred_update_tool

    if any(word in text for word in ["发邮件", "发个邮件", "发一封邮件", "发一份邮件", "写邮件", "发送邮件", "发信", "写信", "站内信"]):
        if any(word in text for word in ["所有", "全体", "全部", "系统所有", "群发", "每个"]):
            return "send_bulk_email"
        return "send_email"

    action = _detect_action(text)
    if action == "update":
        inferred_update_tool = _detect_field_update_tool(text)
        if inferred_update_tool:
            return inferred_update_tool

    object_key = _detect_object(text)
    if action in {"create", "update", "delete"} and object_key:
        return OBJECT_TOOL_MAP[object_key][action]

    if re.search(r"[Tt]\d{6,}", text):
        if _contains_any(text, ["成绩", "分数"]):
            return "query_score"
        return "query_teacher"
    if re.search(r"[Ss]\d{6,}", text):
        if _contains_any(text, ["成绩", "分数"]):
            return "query_score"
        return "query_student"

    student_field_words = ["性别", "手机号", "电话", "邮箱", "班级", "院系", "学院", "状态", "学号", "姓名", "名字"]
    if re.search(r"[Ss]\d{6,}", text) and _contains_any(text, student_field_words):
        return "query_student"
    if re.search(r"[Tt]\d{6,}", text) and _contains_any(text, QUERY_FIELD_HINTS["teacher"]):
        return "query_teacher"
    if _contains_any(text, PRONOUN_WORDS) and _contains_any(text, student_field_words):
        return "query_student"
    if _contains_any(text, ["我的成绩", "我的分数", "我自己的成绩", "本人成绩"]):
        return "query_score"
    if _contains_any(text, ["课表", "课程表", "今天有什么课", "明天有什么课", "在哪上课", "上什么课"]):
        return "query_my_schedule"
    if _contains_any(text, ["成绩", "分数", "考试成绩", "学生成绩"]):
        return "query_score"
    if _contains_any(text, ["考勤", "出勤", "缺勤", "迟到", "早退"]):
        return "query_my_attendance"
    if _contains_any(text, ["我的请假", "请假进度", "请假申请", "请假状态"]):
        return "query_my_leave"
    if _contains_any(text, ["公告", "通知", "校园通知", "最新消息"]):
        return "query_announcements"

    if action and object_key:
        return OBJECT_TOOL_MAP[object_key][action]
    return None


def infer_query_tool_from_context(message: str, memory_context: Any) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    if re.search(r"[Tt]\d{6,}", text):
        return "query_teacher"
    if re.search(r"[Ss]\d{6,}", text):
        return "query_student"
    if _contains_any(text, ["教师", "老师", "教职工", "工号"]):
        return "query_teacher"
    if _contains_any(text, ["学生", "同学", "学号"]):
        return "query_student"

    contexts = []
    if memory_context:
        contexts.extend([
            getattr(memory_context, "active_draft", None),
            getattr(memory_context, "last_tool", None),
            getattr(memory_context, "recent_query_tool", None),
        ])
    for context in contexts:
        tool_code = (context or {}).get("tool_code")
        if tool_code in {"query_teacher", "update_teacher", "delete_teacher", "create_teacher"}:
            return "query_teacher"
        if tool_code in {"query_student", "update_student", "delete_student", "create_student"}:
            return "query_student"
    return None


def _detect_field_update_tool(text: str) -> str | None:
    if _looks_like_person_field_update(text):
        return "update_student"
    for tool_code, words in FIELD_UPDATE_TOOL_HINTS:
        if _contains_any(text, words):
            if tool_code == "update_student" and not _looks_like_person_field_update(text):
                continue
            return tool_code
    return None


def _looks_like_person_field_update(text: str) -> bool:
    person_fields = ["性别", "手机号", "电话", "邮箱", "班级", "状态", "学号", "姓名", "名字"]
    update_words = ["改为", "改成", "设为", "设置为", "变成", "转到", "补充", "添加", "填写", "填入", "录入", "更新"]
    if not _contains_any(text, person_fields) or not _contains_any(text, update_words):
        return False
    return bool(
        re.search(r"^[\u4e00-\u9fa5A-Za-z·]{2,20}的", text)
        or re.search(r"(?:给|把|将)?(?:学生|同学|教师|老师)?[\u4e00-\u9fa5A-Za-z·]{2,20}(?:补充|添加|设置|修改|更新|填写|填入|录入)", text)
    )


def _parse_name_after_verbs(text: str, verbs: list[str], noun: str, max_len: int = 30) -> str | None:
    verb_pattern = "|".join(re.escape(v + noun) for v in verbs)
    match = re.search(fr"(?:{verb_pattern})([\u4e00-\u9fa5A-Za-z0-9·_-]{{1,{max_len}}})", text)
    if not match:
        return None
    value = match.group(1)
    for stopper in [
        "学号", "工号", "编号", "代码", "性别", "身份证", "手机号", "电话", "邮箱", "班级",
        "院系", "学院", "岗位", "职位", "职称", "年级", "容量", "楼栋", "房间号", "标题",
        "内容", "描述", "备注", "学分", "学时", "类型", "教师", "老师", "开始", "结束",
    ]:
        if stopper in value:
            value = value.split(stopper)[0]
    return value.strip(" ，,。") or None


def _set_match(args: dict, text: str, key: str, patterns: list[str], *, cast=None):
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip(" ，,。")
            args[key] = cast(value) if cast else value
            return


def _parse_gender_value(value: str) -> int:
    return 1 if value in {"男", "1"} else 2


def _parse_status_value(text: str, *, person: bool = False) -> int | None:
    if any(word in text for word in ["停用", "禁用", "离职", "退学", "撤回"]):
        return 0
    if any(word in text for word in ["正常", "启用", "恢复", "在职", "在读", "发布"]):
        return 1
    if person and "休学" in text:
        return 2
    if person and "毕业" in text:
        return 3
    if "草稿" in text:
        return 2
    return None


def _parse_course_type(text: str) -> int | None:
    if "必修" in text:
        return 1
    if "选修" in text:
        return 2
    if "公共课" in text or "公共" in text:
        return 3
    match = re.search(r"课程类型[:： ]*([123])", text)
    return int(match.group(1)) if match else None


def _parse_person_common_args(message: str, *, id_label: str, id_key: str, noun: str, create_words: list[str]) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    patterns = {
        id_key: [fr"{id_label}[:： ]*([A-Za-z0-9_-]+)", fr"{id_label}是([A-Za-z0-9_-]+)"],
        "id_card": [r"身份证(?:号)?[:： ]*([0-9Xx]{15,18})", r"身份证(?:号)?是([0-9Xx]{15,18})"],
        "phone": [r"手机号[:： ]*(1[3-9]\d{9})", r"电话[:： ]*(1[3-9]\d{9})", r"(1[3-9]\d{9})"],
        "email": [r"邮箱[:： ]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"],
        "department_keyword": [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
    }
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1)
                break

    gender_match = re.search(r"性别[:： ]*(男|女|1|2)", text)
    if gender_match:
        args["gender"] = _parse_gender_value(gender_match.group(1))
    elif "男" in text and "女" not in text:
        args["gender"] = 1
    elif "女" in text:
        args["gender"] = 2

    name = _parse_name_after_verbs(text, create_words, noun, 20)
    if not name:
        match = re.search(r"姓名[:： ]*([\u4e00-\u9fa5A-Za-z·]{2,20})", text)
        name = match.group(1) if match else None
    if name:
        args["name"] = name
    return args


def _parse_create_student_args(message: str) -> dict:
    args = _parse_person_common_args(
        message,
        id_label="学号",
        id_key="student_no",
        noun="学生",
        create_words=["新增", "添加", "创建", "录入", "新建"],
    )
    _set_match(args, message, "clazz_keyword", [r"班级[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"到([\u4e00-\u9fa5A-Za-z0-9_-]+班)"])
    _set_match(args, message, "enrollment_date", [r"入学日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    return args


def _parse_create_teacher_args(message: str) -> dict:
    args = _parse_person_common_args(
        message,
        id_label="工号",
        id_key="employee_no",
        noun="教师",
        create_words=["新增", "添加", "创建", "录入", "新建"],
    )
    _set_match(args, message, "position", [r"岗位[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"职位[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, message, "title", [r"职称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, message, "entry_date", [r"入职日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    return args


def _parse_create_course_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    name = _parse_name_after_verbs(text, ["新增", "添加", "创建", "录入", "新建"], "课程", 40)
    if not name:
        _set_match(args, text, "name", [r"课程名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})"])
    else:
        args["name"] = name
    _set_match(args, text, "code", [r"(?:课程)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"])
    _set_match(args, text, "credit", [r"学分[:： ]*(\d+(?:\.\d+)?)"])
    _set_match(args, text, "hours", [r"学时[:： ]*(\d+)"], cast=int)
    _set_match(args, text, "department_keyword", [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, text, "teacher_keyword", [r"(?:任课)?教师[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"老师[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, text, "description", [r"简介[:： ]*(.+)$"])
    course_type = _parse_course_type(text)
    if course_type:
        args["course_type"] = course_type
    return args


def _parse_create_class_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    name = _parse_name_after_verbs(text, ["新增", "添加", "创建", "录入", "新建"], "班级", 30)
    if name:
        args["name"] = name
    else:
        _set_match(args, text, "name", [r"班级名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,30})"])
    _set_match(args, text, "code", [r"(?:班级)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"])
    _set_match(args, text, "grade", [r"年级[:： ]*(\d{4}|\d{2})"])
    _set_match(args, text, "department_keyword", [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, text, "counselor_keyword", [r"班主任[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"辅导员[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    return args


def _parse_create_department_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    name = _parse_name_after_verbs(text, ["新增", "添加", "创建", "新建"], "院系", 50)
    if name:
        args["name"] = name
    else:
        _set_match(args, text, "name", [r"院系名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})"])
    _set_match(args, text, "code", [r"(?:代码|编号)[:： ]*([A-Za-z0-9_-]+)"])
    _set_match(args, text, "description", [r"描述[:： ]*(.+)$"])
    return args


def _parse_create_classroom_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    name = _parse_name_after_verbs(text, ["新增", "添加", "创建", "新建"], "教室", 40)
    if name:
        args["name"] = name
    else:
        _set_match(args, text, "name", [r"教室名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})"])
    _set_match(args, text, "building", [r"楼栋[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, text, "room_no", [r"房间号[:： ]*([A-Za-z0-9_-]+)"])
    _set_match(args, text, "campus", [r"校区[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
    _set_match(args, text, "capacity", [r"容量[:： ]*(\d+)"], cast=int)
    _set_match(args, text, "room_type", [r"类型[:： ]*([A-Za-z0-9_\-\u4e00-\u9fa5]+)"])
    _set_match(args, text, "remark", [r"备注[:： ]*(.+)$"])
    return args


def _parse_create_term_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    name = _parse_name_after_verbs(text, ["新增", "添加", "创建", "新建"], "学期", 50)
    if name:
        args["name"] = name
    else:
        _set_match(args, text, "name", [r"学期名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})"])
    _set_match(args, text, "academic_year", [r"学年[:： ]*([0-9]{4}-[0-9]{4}|[0-9]{4})"])
    _set_match(args, text, "semester", [r"第?([123])学期", r"学期[:： ]*([123])"], cast=int)
    _set_match(args, text, "start_date", [r"开始日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    _set_match(args, text, "end_date", [r"结束日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    _set_match(args, text, "week_count", [r"(?:周数|教学周数)[:： ]*(\d+)"], cast=int)
    _set_match(args, text, "remark", [r"备注[:： ]*(.+)$"])
    if "当前" in text:
        args["is_current"] = True
    return args


def _parse_create_announcement_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    _set_match(args, text, "title", [r"标题[:： ]*(.+?)(?:\s+内容|内容[:： ]?|$)"])
    if not args.get("title"):
        name = _parse_name_after_verbs(text, ["发布", "新增", "添加", "创建"], "公告", 80)
        if name:
            if "内容" in name:
                name = name.split("内容")[0].strip(" ，,。")
            args["title"] = name
    _set_match(args, text, "content", [r"内容[:： ]*(.+)$"])
    type_map = {"通知": 1, "活动": 2, "紧急": 3}
    for key, value in type_map.items():
        if key in text:
            args["type"] = value
            break
    if "置顶" in text:
        args["is_top"] = True
    if "草稿" in text:
        args["status"] = 2
    return args


def _parse_weather_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    match = re.search(r"(?:查询|查一下|查|看看|看一下)?([\u4e00-\u9fa5A-Za-z]{2,20})(?:今天|今日|现在|当前)?天气", text)
    if not match:
        match = re.search(r"(?:今天|今日|现在|当前)?([\u4e00-\u9fa5A-Za-z]{2,20})天气", text)
    if match:
        city = match.group(1)
        for word in ["查询", "查一下", "查看", "看看", "看一下", "今天", "今日", "现在", "当前", "的"]:
            city = city.replace(word, "")
        city = city.strip(" ，,。")
        if city and city not in {"天气", "今天天气"}:
            args["city"] = city
    return args


def _parse_email_common(message: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}

    subject_match = re.search(r"(?:主题|标题)(?:是|为|叫)?[:： ]*(.+?)(?:[，,。；;]?\s*(?:内容|正文)(?:是|为)?[:： ]*|$)", text)
    if subject_match:
        args["subject"] = subject_match.group(1).strip(" ，,。")
    body_match = re.search(r"(?:内容|正文)(?:是|为)?[:： ]*(.+)$", text)
    if body_match:
        args["body"] = body_match.group(1).strip()

    email_match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
    if email_match:
        args["recipient_email"] = email_match.group(1)

    recipient_match = re.search(r"(?:给|发给|发送给)(.+?)(?:发(?:一封|一份|一封邮件|一份邮件|个|一下|份|封)?(?:邮件|信)|写(?:一封|一份|个|一下|份|封)?(?:邮件|信)|发送(?:一封|一份|个|一下|份|封)?(?:邮件|信)|，|,|主题|标题|内容|正文|$)", text)
    if recipient_match:
        recipient = recipient_match.group(1).strip(" ，,。")
        recipient = re.sub(r"<[^>]+>", "", recipient).strip(" ，,。")
        recipient = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", recipient).strip(" ，,。")
        for prefix in ["学生", "同学", "教师", "老师", "教职工", "用户", "收件人"]:
            if recipient.startswith(prefix) and len(recipient) > len(prefix):
                recipient = recipient[len(prefix):].strip(" ，,。")
        for suffix in ["发个邮件", "发一下邮件", "发份邮件", "发封邮件", "发邮件", "写邮件", "发送邮件", "发个信", "发信"]:
            if recipient.endswith(suffix) and len(recipient) > len(suffix):
                recipient = recipient[: -len(suffix)].strip(" ，,。")
        if recipient and not any(word in recipient for word in ["所有", "全体", "全部", "每个"]):
            args["recipient_keyword"] = recipient

    if not args.get("recipient_keyword") and not args.get("subject") and not args.get("body") and not args.get("recipient_email"):
        fallback = text.strip(" ，,。")
        for prefix in ["学生", "同学", "教师", "老师", "教职工", "用户", "收件人"]:
            if fallback.startswith(prefix) and len(fallback) > len(prefix):
                fallback = fallback[len(prefix):].strip(" ，,。")
                break
        if 1 < len(fallback) <= 30 and not any(word in fallback for word in ["邮件", "主题", "内容", "正文"]):
            args["recipient_keyword"] = fallback

    return args


def _parse_bulk_email_args(message: str) -> dict:
    text = (message or "").strip()
    args = _parse_email_common(text)
    if any(word in text for word in ["学生", "同学"]):
        args["recipient_scope"] = "students"
    elif any(word in text for word in ["教师", "老师", "教职工"]):
        args["recipient_scope"] = "teachers"
    elif any(word in text for word in ["所有用户", "全体用户", "系统所有用户", "所有人", "全体人员", "全校"]):
        args["recipient_scope"] = "all_users"
    return args


def _extract_target(message: str, object_key: str) -> dict:
    text = (message or "").strip()
    args: dict[str, Any] = {}
    id_match = re.search(r"(?:ID|id)[:： ]*#?(\d+)", text)
    if id_match:
        args["target_id"] = int(id_match.group(1))
        return args

    if object_key in {"student", "teacher"} and _contains_any(text, ["邮箱", "邮件地址", "手机号", "电话"]):
        contact_target = _match_contact_maintenance_target(text)
        if contact_target:
            return {"target_keyword": contact_target}

    if object_key == "teacher":
        employee_no = re.search(r"[Tt]\d{6,}", text)
        if employee_no:
            return {"target_keyword": employee_no.group(0).upper()}
    if object_key == "student":
        student_no = re.search(r"[Ss]\d{6,}", text)
        if student_no:
            return {"target_keyword": student_no.group(0).upper()}

    field_target = _extract_field_update_target(text, object_key)
    if field_target:
        return field_target

    aliases = TARGET_ALIASES.get(object_key, [])
    verbs = r"(?:修改|更新|调整|更改|设置|改一下|删除|停用|禁用|移除|注销)"
    for alias in aliases:
        match = re.search(fr"{verbs}{alias}([\u4e00-\u9fa5A-Za-z0-9·_-]{{1,50}})", text)
        if not match:
            match = re.search(fr"{alias}[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{{1,50}})", text)
        if match:
            target = match.group(1)
            for stopper in [
                "的", "姓名", "名称", "标题", "学号", "工号", "编号", "代码", "状态", "性别", "电话",
                "手机号", "邮箱", "身份证", "班级", "院系", "学院", "岗位", "职位", "职称", "年级",
                "容量", "楼栋", "房间号", "内容", "描述", "备注", "改为", "改成", "设置为", "为",
                "学分", "学时", "类型", "教师", "老师", "开始", "结束", "周数", "教学周数",
            ]:
                if stopper in target:
                    target = target.split(stopper)[0]
            target = target.strip(" ，,。")
            if target:
                args["target_keyword"] = target
                return args

    code_match = re.search(r"(?:学号|工号|编号|代码)[:： ]*([A-Za-z0-9_-]+)", text)
    if code_match:
        args["target_keyword"] = code_match.group(1)
    return args


def _extract_field_update_target(text: str, object_key: str) -> dict:
    if object_key == "student":
        target = _match_prefix_before_fields(text, ["性别", "手机号", "电话", "邮箱", "班级", "状态", "学号", "姓名", "名字"])
        if not target:
            target = _match_contact_maintenance_target(text)
    elif object_key == "teacher":
        target = _match_prefix_before_fields(text, ["工号", "岗位", "职位", "职称", "院系", "学院", "入职日期"])
        if not target:
            target = _match_contact_maintenance_target(text)
    elif object_key == "course":
        target = _match_prefix_before_fields(text, ["学分", "学时", "课程类型", "类型", "任课教师", "教师", "老师", "院系", "学院", "名称"])
    elif object_key == "class":
        target = _match_prefix_before_fields(text, ["年级", "班主任", "辅导员", "院系", "学院", "名称", "代码", "编号"])
    elif object_key == "department":
        target = _match_prefix_before_fields(text, ["院系代码", "学院代码", "代码", "编号", "描述", "名称"])
    elif object_key == "classroom":
        target = _match_prefix_before_fields(text, ["容量", "楼栋", "房间号", "校区", "类型", "备注", "名称"])
    elif object_key == "term":
        target = _match_prefix_before_fields(text, ["学年", "学期序号", "开始日期", "结束日期", "周数", "教学周数", "当前", "名称"])
    elif object_key == "announcement":
        target = _match_prefix_before_fields(text, ["标题", "内容", "置顶", "状态"])
    else:
        target = None
    if not target:
        return {}
    for prefix in ["把", "将", "给", "帮我把", "请把"]:
        if target.startswith(prefix):
            target = target[len(prefix):]
    for noun in ["学生", "教师", "老师", "课程", "班级", "院系", "学院", "教室", "学期", "公告", "通知"]:
        if target.startswith(noun) and len(target) > len(noun):
            target = target[len(noun):]
        if target.endswith(noun) and len(target) > len(noun):
            target = target[: -len(noun)]
    target = target.strip(" 的，,。")
    return {"target_keyword": target} if target else {}


def _match_prefix_before_fields(text: str, fields: list[str]) -> str | None:
    field_pattern = "|".join(re.escape(field) for field in sorted(fields, key=len, reverse=True))
    update_pattern = r"(?:改为|改成|设为|设置为|变成|调整为|更新为|转到|改到)"
    match = re.search(fr"^(.+?)(?:的)?(?:{field_pattern}){update_pattern}", text)
    if not match:
        return None
    return match.group(1).strip()


def _match_contact_maintenance_target(text: str) -> str | None:
    patterns = [
        r"(?:能不能|能否|能|可以|可不可以|是否|帮我|请)?(?:给|把|将)?(?:学生|同学|教师|老师|教职工)?"
        r"([\u4e00-\u9fa5A-Za-z·]{2,20})(?:同学|老师|教师|学生)?"
        r"(?:的)?(?:邮箱|邮件地址|手机号|电话)",
        r"(?:能不能|能否|能|可以|可不可以|是否|帮我|请)?(?:给|把|将)?(?:学生|同学|教师|老师|教职工)?"
        r"([\u4e00-\u9fa5A-Za-z·]{2,20})(?:同学|老师|教师|学生)?"
        r"(?:补充|添加|设置|修改|更新|填写|填入|录入)(?:一下)?(?:邮箱|邮件地址|手机号|电话)",
        r"(?:补充|添加|设置|修改|更新|填写|填入|录入)(?:一下)?(?:学生|同学|教师|老师|教职工)?"
        r"([\u4e00-\u9fa5A-Za-z·]{2,20})(?:同学|老师|教师|学生)?(?:的)?(?:邮箱|邮件地址|手机号|电话)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip(" 的，,。")
            for prefix in ["能不能给", "能否给", "能给", "可以给", "可不可以给", "是否给", "帮我给", "请给", "给", "把", "将", "补充", "添加", "设置", "修改", "更新", "填写", "填入", "录入"]:
                if value.startswith(prefix) and len(value) > len(prefix):
                    value = value[len(prefix):].strip(" 的，,。")
            for suffix in ["补充", "添加", "设置", "修改", "更新", "填写", "填入", "录入"]:
                if value.endswith(suffix) and len(value) > len(suffix):
                    value = value[: -len(suffix)].strip(" 的，,。")
            return value
    return None


def _parse_common_update_changes(message: str, tool_code: str) -> dict:
    text = (message or "").strip()
    changes: dict[str, Any] = {}
    object_key = TOOL_OBJECTS.get(tool_code)

    if object_key in {"student", "teacher"}:
        _set_match(changes, text, "name", [r"姓名[:： ]*([\u4e00-\u9fa5A-Za-z·]{2,20})", r"名字改(?:为|成)([\u4e00-\u9fa5A-Za-z·]{2,20})"])
        _set_match(changes, text, "gender", [r"性别[:： ]*(男|女|1|2)"], cast=_parse_gender_value)
        _set_match(changes, text, "id_card", [r"身份证(?:号)?[:： ]*([0-9Xx]{15,18})"])
        _set_match(changes, text, "phone", [r"手机号[:： ]*(1[3-9]\d{9})", r"电话[:： ]*(1[3-9]\d{9})"])
        _set_match(changes, text, "email", [
            r"邮箱[:： ]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
            r"(?:邮箱|邮件地址)(?:改为|改成|设为|设置为|变成|补充为|添加为|补为|填为|录为|为)[:： ]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
            r"(?:补充|添加|设置|修改|更新|录入|填写).{0,12}?(?:邮箱|邮件地址)[^A-Za-z0-9._%+-]{0,8}([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        ])
        status = _parse_status_value(text, person=True)
        if status is not None:
            changes["status"] = status

    if object_key == "student":
        _set_match(changes, text, "student_no", [r"学号(?:改为|改成|设为|设置为|变成)([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "clazz_keyword", [r"班级[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"转到([\u4e00-\u9fa5A-Za-z0-9_-]+班)"])
        _set_match(changes, text, "enrollment_date", [r"入学日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    elif object_key == "teacher":
        _set_match(changes, text, "employee_no", [r"工号(?:改为|改成|设为|设置为|变成)([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "position", [r"(?:岗位|职位)(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"岗位[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"职位[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "title", [r"职称(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"职称[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "department_keyword", [r"(?:院系|学院)(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"院系[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "entry_date", [r"入职日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    elif object_key == "course":
        _set_match(changes, text, "name", [r"课程名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})"])
        _set_match(changes, text, "code", [r"(?:课程)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "credit", [r"学分[:： ]*(\d+(?:\.\d+)?)", r"学分(?:改为|改成|设为|设置为)(\d+(?:\.\d+)?)"])
        _set_match(changes, text, "hours", [r"学时[:： ]*(\d+)", r"学时(?:改为|改成|设为|设置为)(\d+)"], cast=int)
        course_type = _parse_course_type(text)
        if course_type:
            changes["course_type"] = course_type
        _set_match(changes, text, "department_keyword", [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "teacher_keyword", [r"(?:任课)?教师[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"老师[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "description", [r"简介[:： ]*(.+)$"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "class":
        _set_match(changes, text, "name", [r"班级名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,30})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9·_-]{2,30})"])
        _set_match(changes, text, "code", [r"(?:班级)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "grade", [r"年级[:： ]*(\d{4}|\d{2})", r"年级(?:改为|改成|设为|设置为)(\d{4}|\d{2})"])
        _set_match(changes, text, "department_keyword", [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "counselor_keyword", [r"班主任[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"辅导员[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "department":
        _set_match(changes, text, "name", [r"院系名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})"])
        _set_match(changes, text, "code", [r"(?:代码|编号)(?:改为|改成|设为|设置为|变成)([A-Za-z0-9_-]+)", r"(?:代码|编号)[:： ]+([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "description", [r"描述(?:改为|改成|设为|设置为|变成)(.+)$", r"描述[:： ]+(.+)$"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "classroom":
        _set_match(changes, text, "name", [r"教室名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})"])
        _set_match(changes, text, "building", [r"楼栋(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"楼栋[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "room_no", [r"房间号(?:改为|改成|设为|设置为|变成)([A-Za-z0-9_-]+)", r"房间号[:： ]+([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "campus", [r"校区(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"校区[:： ]+([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "capacity", [r"容量[:： ]*(\d+)", r"容量(?:改为|改成|设为|设置为)(\d+)"], cast=int)
        _set_match(changes, text, "room_type", [r"类型(?:改为|改成|设为|设置为|变成)([A-Za-z0-9_\-\u4e00-\u9fa5]+)", r"类型[:： ]+([A-Za-z0-9_\-\u4e00-\u9fa5]+)"])
        _set_match(changes, text, "remark", [r"备注(?:改为|改成|设为|设置为|变成)(.+)$", r"备注[:： ]+(.+)$"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "term":
        _set_match(changes, text, "name", [r"学期名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})"])
        _set_match(changes, text, "academic_year", [r"学年[:： ]*([0-9]{4}-[0-9]{4}|[0-9]{4})"])
        _set_match(changes, text, "semester", [r"第?([123])学期", r"学期[:： ]*([123])"], cast=int)
        _set_match(changes, text, "start_date", [r"开始日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
        _set_match(changes, text, "end_date", [r"结束日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
        _set_match(changes, text, "week_count", [r"(?:周数|教学周数)[:： ]*(\d+)", r"(?:周数|教学周数)(?:改为|改成|设为|设置为)(\d+)"], cast=int)
        if "当前" in text:
            changes["is_current"] = True
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
        _set_match(changes, text, "remark", [r"备注[:： ]*(.+)$"])
    elif object_key == "announcement":
        _set_match(changes, text, "title", [r"标题(?:改为|改成|设为|设置为|变成)([^，,。\n]+)", r"标题[:： ]+([^，,。\n]+)"])
        _set_match(changes, text, "content", [r"内容(?:改为|改成|设为|设置为|变成)(.+)$", r"内容[:： ]+(.+)$"])
        type_map = {"通知": 1, "活动": 2, "紧急": 3}
        for key, value in type_map.items():
            if key in text:
                changes["type"] = value
                break
        if "取消置顶" in text:
            changes["is_top"] = False
        elif "置顶" in text:
            changes["is_top"] = True
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    return changes


def _extract_possessive_target(message: str) -> dict:
    text = (message or "").strip()
    match = re.search(r"^([\u4e00-\u9fa5A-Za-z·]{2,20})的(?:性别|手机号|电话|邮箱|班级|状态|学号|姓名|名字)", text)
    if not match:
        return {}
    return {"target_keyword": match.group(1).strip()}


def _parse_student_possessive_changes(message: str) -> dict:
    text = (message or "").strip()
    changes: dict[str, Any] = {}
    _set_match(changes, text, "gender", [r"性别(?:改为|改成|设为|设置为|变成)(男|女|1|2)"], cast=_parse_gender_value)
    _set_match(changes, text, "phone", [r"(?:手机号|电话)(?:改为|改成|设为|设置为|变成)(1[3-9]\d{9})"])
    _set_match(changes, text, "email", [
        r"邮箱(?:改为|改成|设为|设置为|变成|补充为|添加为|补为|填为|录为)([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        r"(?:补充|添加|设置|修改|更新|录入|填写).{0,12}?(?:邮箱|邮件地址)[^A-Za-z0-9._%+-]{0,8}([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    ])
    _set_match(changes, text, "student_no", [r"学号(?:改为|改成|设为|设置为|变成)([A-Za-z0-9_-]+)"])
    _set_match(changes, text, "name", [r"(?:姓名|名字)(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z·]{2,20})"])
    _set_match(changes, text, "clazz_keyword", [r"班级(?:改为|改成|设为|设置为|变成)([\u4e00-\u9fa5A-Za-z0-9_-]+班?)", r"转到([\u4e00-\u9fa5A-Za-z0-9_-]+班)"])
    status = _parse_status_value(text, person=True)
    if status is not None:
        changes["status"] = status
    return changes


def _parse_mutation_args(tool_code: str, message: str) -> dict:
    object_key = TOOL_OBJECTS.get(tool_code, "")
    args = _extract_target(message, object_key)
    if tool_code == "update_student":
        args = {**_extract_possessive_target(message), **args}
    if tool_code.startswith("update_"):
        args["changes"] = _parse_common_update_changes(message, tool_code)
        if tool_code == "update_student":
            args["changes"] = {**args.get("changes", {}), **_parse_student_possessive_changes(message)}
    return args


def parse_tool_args(tool_code: str, message: str) -> dict:
    text = message or ""
    if tool_code == "query_teacher":
        employee_no = re.search(r"[Tt]\d{6,}", text)
        return {"keyword": employee_no.group(0).upper()} if employee_no else {}
    if tool_code == "query_student":
        student_no = re.search(r"[Ss]\d{6,}", text)
        return {"keyword": student_no.group(0).upper()} if student_no else {}
    if tool_code == "query_weather":
        return _parse_weather_args(message)
    if tool_code == "send_email":
        return _parse_email_common(message)
    if tool_code == "send_bulk_email":
        return _parse_bulk_email_args(message)
    if tool_code == "create_student":
        return _parse_create_student_args(message)
    if tool_code == "create_teacher":
        return _parse_create_teacher_args(message)
    if tool_code == "create_course":
        return _parse_create_course_args(message)
    if tool_code == "create_class":
        return _parse_create_class_args(message)
    if tool_code == "create_department":
        return _parse_create_department_args(message)
    if tool_code == "create_classroom":
        return _parse_create_classroom_args(message)
    if tool_code == "create_term":
        return _parse_create_term_args(message)
    if tool_code == "create_announcement":
        return _parse_create_announcement_args(message)
    if tool_code in TOOL_OBJECTS:
        return _parse_mutation_args(tool_code, message)
    return {}


def tool_response_mode(tool_code: str) -> str:
    if tool_code in QUERY_TOOL_CODES or tool_code in CREATE_TOOL_CODES or tool_code in TOOL_OBJECTS:
        return "academic_ops"
    return "academic_tools"


class CampusAgentPlanner:
    """Natural-language to tool planner.

    The deterministic rules are still the safety fallback.  When an LLM planner
    is injected it is used for flexible Chinese intent recognition, while all
    execution still goes through registry/executor/tool_handlers.
    """

    def __init__(self, llm_planner=None):
        self.llm_planner = llm_planner

    def plan(
        self,
        message: str,
        *,
        mode: str = "auto",
        available_tool_codes: set[str] | None = None,
        memory_context=None,
    ) -> AgentPlan:
        text = (message or "").strip()
        if not text:
            return AgentPlan(status="clarify", intent="empty_message", reason="消息为空")

        if is_capability_question(text):
            return AgentPlan(status="planned", intent="list_available_tools", response_mode="academic_ops", confidence=1.0)

        if _contains_any(text, CONTINUATION_WORDS):
            return AgentPlan(status="planned", intent="continue_previous", response_mode="academic_ops", confidence=0.95)

        deterministic_tool = _detect_academic_tool(text)
        if not deterministic_tool and _detect_action(text) == "query":
            deterministic_tool = infer_query_tool_from_context(text, memory_context)
        if deterministic_tool and (
            deterministic_tool.startswith("query_")
            or re.search(r"[Tt]\d{6,}|[Ss]\d{6,}", text)
            or _contains_any(text, ["教师", "老师", "教职工", "工号", "学生", "同学", "学号"])
        ):
            return AgentPlan(
                tool_code=deterministic_tool,
                args=parse_tool_args(deterministic_tool, text),
                status="planned",
                intent=deterministic_tool,
                confidence=0.9,
                response_mode=tool_response_mode(deterministic_tool),
            )

        if self.llm_planner:
            llm_plan = self.llm_planner.plan(
                text,
                available_tool_codes=available_tool_codes,
                memory_context=memory_context,
            )
            if llm_plan and llm_plan.tool_code:
                return llm_plan

        if _contains_any(text, PRONOUN_WORDS) and any(word in text for word in ["转到", "调到", "班级", "改到"]):
            return AgentPlan(
                tool_code="update_student",
                args=parse_tool_args("update_student", text),
                status="planned",
                intent="update_student",
                confidence=0.75,
                response_mode="academic_ops",
            )

        tool_code = deterministic_tool or _detect_academic_tool(text)
        if not tool_code and _detect_action(text) == "query":
            tool_code = infer_query_tool_from_context(text, memory_context)
        if not tool_code:
            return AgentPlan(status="unmatched", intent="unmatched", confidence=0.0)

        args = parse_tool_args(tool_code, text)
        return AgentPlan(
            tool_code=tool_code,
            args=args,
            status="planned",
            intent=tool_code,
            confidence=0.8,
            response_mode=tool_response_mode(tool_code),
        )
