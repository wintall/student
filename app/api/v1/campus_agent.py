"""
Campus AI assistant routes.
"""
from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.services import rag_knowledge_service
from app.services.campus_agent import CampusAgentExecutor, get_available_tools, list_capabilities
from app.services.campus_agent.memory import (
    append_turn,
    clear_session,
    conversation_title,
    delete_user_session,
    get_messages,
    get_or_create_session,
    get_user_session,
    last_tool_context,
    list_user_sessions,
)
from app.services.campus_agent.pending_actions import (
    get_pending_action,
    is_action_expired,
    mark_action_cancelled,
    mark_action_executed,
    mark_action_expired,
    mark_action_failed,
    parse_action_args,
)
from app.services.campus_agent.task_drafts import (
    draft_to_context,
    get_active_draft,
    mark_draft_cancelled,
    mark_draft_completed,
    upsert_task_draft,
)
from app.services.campus_agent.tool_handlers import normalize_args
from app.services.campus_agent.orchestrator import CampusAgentOrchestrator
from app.services.campus_agent.document_tools import save_agent_file
from app.utils.response import success

router = APIRouter(prefix="/campus-agent", tags=["校园助手"])


ASSISTANT_MODES = list_capabilities()


def _normalize_mode_item(item: dict) -> dict:
    """Normalize legacy mode names before returning them to the frontend."""
    normalized = dict(item)
    if normalized.get("code") == "code_review":
        normalized.update({
            "name": "编程助手",
            "description": "代码问答、代码生成、文件定位、代码解释和项目体检。",
            "quick_questions": [
                "分析项目 E:\\student",
                "学生新增接口在哪",
                "帮我写一个 FastAPI 上传接口",
                "解释 AIAssistant.vue",
            ],
        })
    return normalized


MODE_HINTS = {
    "rag": "当前处于 RAG 知识问答模式，会优先检索当前账号可访问的综合知识库并返回引用来源。",
    "search": "当前处于搜索引擎模式，会联网检索实时资讯、外部资料和来源链接，并支持基于上一轮搜索结果继续追问。",
    "academic_tools": "当前处于教务助手模式。你可以查询成绩、课表、请假、考勤、公告，也可以在权限范围内维护教务数据。",
    "academic_ops": "当前处于教务助手模式。你可以查询成绩、课表、请假、考勤、公告，也可以用自然语言新增、修改、停用教务数据，敏感操作会先让你确认。",
    "study": "当前处于学习辅导模式。支持课程知识讲解、题目解析、复习计划和诗词鉴赏。",
    "document": "当前处于文档处理模式。支持文本总结、项目/上传目录下的 txt、md、pdf 解析、图片 OCR 和英汉互译。",
    "code_review": "当前处于编程助手模式。支持代码问答、代码生成、文件定位、代码解释和项目体检。",
    "emotion": "当前处于情绪陪伴模式。助手会基于 CBT、压力应对、正念等框架提供支持性心理建议，但不替代专业诊断或治疗。",
    "map": "当前处于路线生活模式。支持路线规划和附近吃喝玩乐搜索。",
    "data_analysis": "当前处于数据分析模式。支持数据体检、成绩趋势、考勤请假统计和管理建议。",
    "worldcup": "当前处于世界杯问答模式。支持世界杯历史、赛制、球队、球星和射手榜问答，实时问题会尝试联网检索。",
    "ai_knowledge": "当前处于 AI 知识问答模式。支持 LangChain、LangGraph、FastAPI、Dify、Python、Linux、SQL 等技术知识问答。",
}

CREATE_TOOL_CODES = {
    "create_student",
    "create_teacher",
    "create_course",
    "create_class",
    "create_department",
    "create_classroom",
    "create_term",
    "create_announcement",
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
}


class CampusAgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    mode: str = Field(default="auto")
    session_id: str | None = None
    file_ids: list[str] = Field(default_factory=list, max_length=10)
    llm_provider: str | None = Field(default=None, max_length=40)
    llm_model: str | None = Field(default=None, max_length=120)


class CampusAgentClearRequest(BaseModel):
    session_id: str | None = None


def _mode_exists(mode: str) -> bool:
    return any(item["code"] == mode for item in ASSISTANT_MODES)


def _suggested_questions(mode: str) -> list[str]:
    for item in ASSISTANT_MODES:
        if item["code"] == mode:
            return _normalize_mode_item(item)["quick_questions"]
    return _normalize_mode_item(ASSISTANT_MODES[0])["quick_questions"]


def _format_available_tools(tools: list[dict]) -> str:
    if not tools:
        return "你当前账号暂时没有可通过足球助手调用的系统工具。"
    lines = ["你当前可以通过足球助手使用这些系统工具：", ""]
    for tool in tools:
        confirm_text = "，需要确认" if tool.get("confirm_required") else ""
        lines.append(
            f"- {tool['name']}（{tool['code']}）：{tool['description']} "
            f"权限码：{tool['permission']}，风险：{tool['risk']}{confirm_text}"
        )
    lines.append("")
    lines.append("你可以直接说：查询学生张三、查询成绩、新增教师李明工号T2026001、把课程高等数学学分改成4。")
    lines.append("新增、修改、停用这类操作会先生成待确认动作，确认后才真正执行。")
    return "\n".join(lines)


def _compact_message(message: str) -> str:
    return re.sub(r"[\s,，.。!！?？、;；:：~～]+", "", message or "")


def _is_tool_capability_question(message: str) -> bool:
    text = _compact_message(message)
    keywords = [
        "你能做什么",
        "能做什么",
        "可以做什么",
        "会做什么",
        "你会做什么",
        "能干什么",
        "可以干什么",
        "可以干嘛",
        "能干嘛",
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


def _detect_academic_tool(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    student_field_words = ["性别", "手机号", "电话", "邮箱", "班级", "院系", "学院", "状态", "学号", "姓名"]
    if re.search(r"[Ss]\d{6,}", text) and any(word in text for word in student_field_words):
        return "query_student"
    if any(word in text for word in ["这个人", "这个学生", "这名学生", "该学生"]) and any(word in text for word in student_field_words):
        return "query_student"
    if any(word in text for word in ["我的成绩", "我的分数", "我自己的成绩", "本人成绩"]):
        return "query_score"
    if any(word in text for word in ["课表", "课程表", "今天有什么课", "明天有什么课", "在哪上课", "上什么课"]):
        return "query_my_schedule"
    if any(word in text for word in ["成绩", "分数", "考试成绩", "学生成绩"]):
        return "query_score"
    if any(word in text for word in ["考勤", "出勤", "缺勤", "迟到", "早退"]):
        return "query_my_attendance"
    if any(word in text for word in ["我的请假", "请假进度", "请假申请", "请假状态"]):
        return "query_my_leave"
    if any(word in text for word in ["公告", "通知", "校园通知", "最新消息"]):
        return "query_announcements"
    return None


def _detect_operation_tool(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    student_field_words = ["性别", "手机号", "电话", "邮箱", "班级", "院系", "学院", "状态", "学号", "姓名"]
    if re.search(r"[Ss]\d{6,}", text) and any(word in text for word in student_field_words):
        return "query_student"
    if any(word in text for word in ["这个人", "这个学生", "这名学生", "该学生"]) and any(word in text for word in student_field_words):
        return "query_student"
    update_words = ["修改", "更新", "调整", "改一下", "更改", "设置"]
    delete_words = ["删除", "停用", "禁用", "移除", "注销"]
    if any(word in text for word in update_words):
        if any(word in text for word in ["学生", "学号", "同学"]):
            return "update_student"
        if any(word in text for word in ["教师", "老师", "教职工", "工号"]):
            return "update_teacher"
        if any(word in text for word in ["课程", "课程编号", "课程代码"]):
            return "update_course"
        if any(word in text for word in ["班级", "班号"]):
            return "update_class"
        if any(word in text for word in ["院系", "学院", "系部"]):
            return "update_department"
        if any(word in text for word in ["教室", "楼栋", "房间"]):
            return "update_classroom"
        if any(word in text for word in ["学期", "学年"]):
            return "update_term"
        if any(word in text for word in ["公告", "通知"]):
            return "update_announcement"
    if any(word in text for word in delete_words):
        if any(word in text for word in ["学生", "学号", "同学"]):
            return "delete_student"
        if any(word in text for word in ["教师", "老师", "教职工", "工号"]):
            return "delete_teacher"
        if any(word in text for word in ["课程", "课程编号", "课程代码"]):
            return "delete_course"
        if any(word in text for word in ["班级", "班号"]):
            return "delete_class"
        if any(word in text for word in ["院系", "学院", "系部"]):
            return "delete_department"
        if any(word in text for word in ["教室", "楼栋", "房间"]):
            return "delete_classroom"
        if any(word in text for word in ["学期", "学年"]):
            return "delete_term"
        if any(word in text for word in ["公告", "通知"]):
            return "delete_announcement"
    if any(word in text for word in ["新增学生", "添加学生", "创建学生", "录入学生", "新建学生"]):
        return "create_student"
    if any(word in text for word in ["新增教师", "添加教师", "创建教师", "录入教师", "新建教师", "新增老师", "添加老师"]):
        return "create_teacher"
    if any(word in text for word in ["新增课程", "添加课程", "创建课程", "录入课程", "新建课程"]):
        return "create_course"
    if any(word in text for word in ["新增班级", "添加班级", "创建班级", "录入班级", "新建班级"]):
        return "create_class"
    if any(word in text for word in ["新增院系", "添加院系", "创建院系", "新建院系"]):
        return "create_department"
    if any(word in text for word in ["新增教室", "添加教室", "创建教室", "新建教室"]):
        return "create_classroom"
    if any(word in text for word in ["新增学期", "添加学期", "创建学期", "新建学期"]):
        return "create_term"
    if any(word in text for word in ["发布公告", "新增公告", "添加公告", "创建公告"]):
        return "create_announcement"
    query_words = ["查", "查询", "搜索", "找", "看一下", "看看", "列出", "显示"]
    if not any(word in text for word in query_words):
        return None
    if any(word in text for word in ["学生", "学号", "同学"]):
        return "query_student"
    if any(word in text for word in ["教师", "老师", "教职工", "工号"]):
        return "query_teacher"
    if any(word in text for word in ["课程", "课程编号", "课程代码"]):
        return "query_course"
    if any(word in text for word in ["成绩", "分数", "考试成绩", "学生成绩"]):
        return "query_score"
    if any(word in text for word in ["班级", "班号"]):
        return "query_class"
    if any(word in text for word in ["院系", "学院", "系部"]):
        return "query_department"
    if any(word in text for word in ["教室", "楼栋", "房间"]):
        return "query_classroom"
    if any(word in text for word in ["学期", "学年"]):
        return "query_term"
    return None


def _parse_confirmation(message: str) -> tuple[str, int] | None:
    text = (message or "").strip()
    match = re.search(r"(确认|执行|同意|取消|放弃)\s*(?:动作|操作|ID|id)?\s*#?(\d+)", text)
    if not match:
        if text in {"确认", "执行", "同意", "取消", "放弃"}:
            return text, 0
        return None
    return match.group(1), int(match.group(2))


def _parse_create_student_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}

    patterns = {
        "student_no": [r"学号[:： ]*([A-Za-z0-9_-]+)", r"学号是([A-Za-z0-9_-]+)"],
        "id_card": [r"身份证(?:号)?[:： ]*([0-9Xx]{15,18})", r"身份证(?:号)?是([0-9Xx]{15,18})"],
        "phone": [r"手机号[:： ]*(1[3-9]\d{9})", r"电话[:： ]*(1[3-9]\d{9})", r"(1[3-9]\d{9})"],
        "email": [r"邮箱[:： ]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"],
        "enrollment_date": [r"入学日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"],
        "clazz_keyword": [r"班级[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"到([\u4e00-\u9fa5A-Za-z0-9_-]+班)"],
    }
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1)
                break

    gender_match = re.search(r"性别[:： ]*(男|女|1|2)", text)
    if gender_match:
        value = gender_match.group(1)
        args["gender"] = 1 if value in {"男", "1"} else 2
    elif "男" in text and "女" not in text:
        args["gender"] = 1
    elif "女" in text:
        args["gender"] = 2

    name_match = re.search(r"(?:新增|添加|创建|录入|新建)学生([\u4e00-\u9fa5A-Za-z·]{2,20})", text)
    if not name_match:
        name_match = re.search(r"姓名[:： ]*([\u4e00-\u9fa5A-Za-z·]{2,20})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in ["学号", "性别", "男", "女", "身份证", "手机号", "电话", "邮箱", "班级", "到"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")

    return args


def _parse_person_common_args(message: str, *, id_label: str, id_key: str, create_words: list[str]) -> dict:
    text = (message or "").strip()
    args: dict = {}
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
        value = gender_match.group(1)
        args["gender"] = 1 if value in {"男", "1"} else 2
    elif "男" in text and "女" not in text:
        args["gender"] = 1
    elif "女" in text:
        args["gender"] = 2

    create_pattern = "|".join(create_words)
    name_match = re.search(fr"(?:{create_pattern})([\u4e00-\u9fa5A-Za-z·]{{2,20}})", text)
    if not name_match:
        name_match = re.search(r"姓名[:： ]*([\u4e00-\u9fa5A-Za-z·]{2,20})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in [id_label, "性别", "男", "女", "身份证", "手机号", "电话", "邮箱", "院系", "学院", "岗位", "职位", "职称", "入职"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")
    return args


def _parse_create_teacher_args(message: str) -> dict:
    text = (message or "").strip()
    args = _parse_person_common_args(
        text,
        id_label="工号",
        id_key="employee_no",
        create_words=["新增教师", "添加教师", "创建教师", "录入教师", "新建教师", "新增老师", "添加老师"],
    )
    extra_patterns = {
        "position": [r"岗位[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"职位[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "title": [r"职称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "entry_date": [r"入职日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"],
    }
    for key, regexes in extra_patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1)
                break
    return args


def _parse_course_type(text: str) -> int | None:
    if "必修" in text:
        return 1
    if "选修" in text:
        return 2
    if "公共课" in text or "公共" in text:
        return 3
    match = re.search(r"课程类型[:： ]*([123])", text)
    return int(match.group(1)) if match else None


def _parse_create_course_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    name_match = re.search(r"(?:新增课程|添加课程|创建课程|录入课程|新建课程)([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})", text)
    if not name_match:
        name_match = re.search(r"课程名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in ["编号", "代码", "学分", "学时", "类型", "院系", "学院", "教师", "老师", "简介"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")

    patterns = {
        "code": [r"(?:课程)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"],
        "credit": [r"学分[:： ]*(\d+(?:\.\d+)?)"],
        "hours": [r"学时[:： ]*(\d+)"],
        "department_keyword": [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "teacher_keyword": [r"(?:任课)?教师[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"老师[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "description": [r"简介[:： ]*(.+)$"],
    }
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1).strip()
                break
    course_type = _parse_course_type(text)
    if course_type:
        args["course_type"] = course_type
    if "hours" in args:
        args["hours"] = int(args["hours"])
    return args


def _parse_create_class_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    name_match = re.search(r"(?:新增班级|添加班级|创建班级|录入班级|新建班级)([\u4e00-\u9fa5A-Za-z0-9·_-]{2,30})", text)
    if not name_match:
        name_match = re.search(r"班级名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,30})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in ["编号", "代码", "年级", "院系", "学院", "班主任", "辅导员"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")
    patterns = {
        "code": [r"(?:班级)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"],
        "grade": [r"年级[:： ]*(\d{4}|\d{2})"],
        "department_keyword": [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "counselor_keyword": [r"班主任[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"辅导员[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
    }
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1).strip()
                break
    return args


def _parse_create_department_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    name_match = re.search(r"(?:新增院系|添加院系|创建院系|新建院系)([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})", text)
    if not name_match:
        name_match = re.search(r"院系名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in ["代码", "编号", "描述"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")
    code_match = re.search(r"(?:代码|编号)[:： ]*([A-Za-z0-9_-]+)", text)
    if code_match:
        args["code"] = code_match.group(1)
    desc_match = re.search(r"描述[:： ]*(.+)$", text)
    if desc_match:
        args["description"] = desc_match.group(1).strip()
    return args


def _parse_create_classroom_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    name_match = re.search(r"(?:新增教室|添加教室|创建教室|新建教室)([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})", text)
    if not name_match:
        name_match = re.search(r"教室名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in ["楼栋", "房间号", "校区", "容量", "类型", "备注"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")
    patterns = {
        "building": [r"楼栋[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "room_no": [r"房间号[:： ]*([A-Za-z0-9_-]+)"],
        "campus": [r"校区[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"],
        "capacity": [r"容量[:： ]*(\d+)"],
        "room_type": [r"类型[:： ]*([A-Za-z0-9_\-\u4e00-\u9fa5]+)"],
        "remark": [r"备注[:： ]*(.+)$"],
    }
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1).strip()
                break
    if "capacity" in args:
        args["capacity"] = int(args["capacity"])
    return args


def _parse_create_term_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    name_match = re.search(r"(?:新增学期|添加学期|创建学期|新建学期)([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})", text)
    if not name_match:
        name_match = re.search(r"学期名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})", text)
    if name_match:
        name = name_match.group(1)
        for stopper in ["学年", "第", "开始", "结束", "周数", "当前"]:
            if stopper in name:
                name = name.split(stopper)[0]
        args["name"] = name.strip(" ，,。")
    patterns = {
        "academic_year": [r"学年[:： ]*([0-9]{4}-[0-9]{4}|[0-9]{4})"],
        "semester": [r"第?([123])学期", r"学期[:： ]*([123])"],
        "start_date": [r"开始日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"],
        "end_date": [r"结束日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"],
        "week_count": [r"(?:周数|教学周数)[:： ]*(\d+)"],
        "remark": [r"备注[:： ]*(.+)$"],
    }
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, text)
            if match:
                args[key] = match.group(1).strip()
                break
    for key in ["semester", "week_count"]:
        if key in args:
            args[key] = int(args[key])
    if "当前" in text:
        args["is_current"] = True
    return args


def _parse_create_announcement_args(message: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    title_match = re.search(r"标题[:： ]*([^，,。\\n]+)", text)
    if not title_match:
        title_match = re.search(r"(?:发布公告|新增公告|添加公告|创建公告)([^，,。\\n]{2,80})", text)
    if title_match:
        title = title_match.group(1)
        for stopper in ["内容", "类型", "置顶", "草稿"]:
            if stopper in title:
                title = title.split(stopper)[0]
        args["title"] = title.strip(" ，,。")
    content_match = re.search(r"内容[:： ]*(.+)$", text)
    if content_match:
        args["content"] = content_match.group(1).strip()
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


def _extract_target(message: str, object_key: str) -> dict:
    text = (message or "").strip()
    args: dict = {}
    id_match = re.search(r"(?:ID|id)[:： ]*#?(\d+)", text)
    if id_match:
        args["target_id"] = int(id_match.group(1))
        return args

    aliases = TARGET_ALIASES.get(object_key, [])
    verbs = r"(?:修改|更新|调整|更改|设置|改一下|删除|停用|禁用|移除|注销)"
    for alias in aliases:
        match = re.search(fr"{verbs}{alias}([\u4e00-\u9fa5A-Za-z0-9·_-]{{1,50}})", text)
        if not match:
            match = re.search(fr"{alias}[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{{1,50}})", text)
        if match:
            target = match.group(1)
            for stopper in [
                "的", "姓名", "名称", "标题", "学号", "工号", "编号", "代码", "状态", "性别", "电话", "手机号",
                "邮箱", "身份证", "班级", "院系", "学院", "岗位", "职位", "职称", "年级", "容量", "楼栋", "房间号",
                "内容", "描述", "备注", "改为", "改成", "设置为", "为",
            ]:
                if stopper in target:
                    target = target.split(stopper)[0]
            target = target.strip(" ，,。")
            if target:
                args["target_keyword"] = target
                return args
    return args


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


def _parse_common_update_changes(message: str, tool_code: str) -> dict:
    text = (message or "").strip()
    changes: dict = {}
    object_key = TOOL_OBJECTS.get(tool_code)

    if object_key in {"student", "teacher"}:
        _set_match(changes, text, "name", [r"姓名[:： ]*([\u4e00-\u9fa5A-Za-z·]{2,20})", r"名字改(?:为|成)([\u4e00-\u9fa5A-Za-z·]{2,20})"])
        _set_match(changes, text, "gender", [r"性别[:： ]*(男|女|1|2)"], cast=_parse_gender_value)
        _set_match(changes, text, "id_card", [r"身份证(?:号)?[:： ]*([0-9Xx]{15,18})"])
        _set_match(changes, text, "phone", [r"手机号[:： ]*(1[3-9]\d{9})", r"电话[:： ]*(1[3-9]\d{9})"])
        _set_match(changes, text, "email", [r"邮箱[:： ]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"])
        status = _parse_status_value(text, person=True)
        if status is not None:
            changes["status"] = status

    if object_key == "student":
        _set_match(changes, text, "student_no", [r"学号[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "clazz_keyword", [r"班级[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"转到([\u4e00-\u9fa5A-Za-z0-9_-]+班)"])
        _set_match(changes, text, "enrollment_date", [r"入学日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    elif object_key == "teacher":
        _set_match(changes, text, "employee_no", [r"工号[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "position", [r"岗位[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"职位[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "title", [r"职称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "department_keyword", [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "entry_date", [r"入职日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
    elif object_key == "course":
        _set_match(changes, text, "name", [r"课程名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9·_-]{2,40})"])
        _set_match(changes, text, "code", [r"(?:课程)?(?:编号|代码)[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "credit", [r"学分[:： ]*(\d+(?:\.\d+)?)"])
        _set_match(changes, text, "hours", [r"学时[:： ]*(\d+)"], cast=int)
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
        _set_match(changes, text, "grade", [r"年级[:： ]*(\d{4}|\d{2})"])
        _set_match(changes, text, "department_keyword", [r"院系[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"学院[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "counselor_keyword", [r"班主任[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)", r"辅导员[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "department":
        _set_match(changes, text, "name", [r"院系名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9_-]{2,50})"])
        _set_match(changes, text, "code", [r"(?:代码|编号)[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "description", [r"描述[:： ]*(.+)$"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "classroom":
        _set_match(changes, text, "name", [r"教室名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9_-]{2,40})"])
        _set_match(changes, text, "building", [r"楼栋[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "room_no", [r"房间号[:： ]*([A-Za-z0-9_-]+)"])
        _set_match(changes, text, "campus", [r"校区[:： ]*([\u4e00-\u9fa5A-Za-z0-9_-]+)"])
        _set_match(changes, text, "capacity", [r"容量[:： ]*(\d+)"], cast=int)
        _set_match(changes, text, "room_type", [r"类型[:： ]*([A-Za-z0-9_\-\u4e00-\u9fa5]+)"])
        _set_match(changes, text, "remark", [r"备注[:： ]*(.+)$"])
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    elif object_key == "term":
        _set_match(changes, text, "name", [r"学期名称[:： ]*([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})", r"名称改(?:为|成)([\u4e00-\u9fa5A-Za-z0-9_\\-年第学期]{2,50})"])
        _set_match(changes, text, "academic_year", [r"学年[:： ]*([0-9]{4}-[0-9]{4}|[0-9]{4})"])
        _set_match(changes, text, "semester", [r"第?([123])学期", r"学期[:： ]*([123])"], cast=int)
        _set_match(changes, text, "start_date", [r"开始日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
        _set_match(changes, text, "end_date", [r"结束日期[:： ]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"])
        _set_match(changes, text, "week_count", [r"(?:周数|教学周数)[:： ]*(\d+)"], cast=int)
        if "当前" in text:
            changes["is_current"] = True
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
        _set_match(changes, text, "remark", [r"备注[:： ]*(.+)$"])
    elif object_key == "announcement":
        _set_match(changes, text, "title", [r"标题[:： ]*([^，,。\\n]+)", r"标题改(?:为|成)([^，,。\\n]+)"])
        _set_match(changes, text, "content", [r"内容[:： ]*(.+)$"])
        type_map = {"通知": 1, "活动": 2, "紧急": 3}
        for key, value in type_map.items():
            if key in text:
                changes["type"] = value
                break
        if "置顶" in text:
            changes["is_top"] = True
        if "取消置顶" in text:
            changes["is_top"] = False
        status = _parse_status_value(text)
        if status is not None:
            changes["status"] = status
    return changes


def _parse_mutation_args(tool_code: str, message: str) -> dict:
    object_key = TOOL_OBJECTS.get(tool_code, "")
    args = _extract_target(message, object_key)
    if tool_code.startswith("update_"):
        args["changes"] = _parse_common_update_changes(message, tool_code)
    return args


def _deep_merge_tool_args(base: dict | None, incoming: dict | None) -> dict:
    merged = dict(base or {})
    for transient_key in ["pending_action_id"]:
        merged.pop(transient_key, None)
    for key, value in (incoming or {}).items():
        if value in (None, "", [], {}):
            continue
        if key == "changes" and isinstance(value, dict):
            existing = merged.get("changes") if isinstance(merged.get("changes"), dict) else {}
            merged["changes"] = {**existing, **value}
        else:
            merged[key] = value
    return merged


def _candidate_selection_index(message: str) -> int | None:
    text = (message or "").strip()
    match = re.search(r"(?:选|选择|用|就)?\s*第?\s*([一二三四五六七八九十\d]+)\s*(?:个|条|项)?", text)
    if not match:
        return None
    raw = match.group(1)
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if raw.isdigit():
        return int(raw) - 1
    return cn_map.get(raw, 0) - 1


def _extract_candidate_target_args(message: str, previous_context: dict | None) -> dict:
    if not previous_context:
        return {}
    direct_id = re.search(r"(?:ID|id)[:： ]*#?(\d+)", message or "")
    previous_tool = previous_context.get("tool_code") or ""
    data = previous_context.get("tool_data") or {}
    candidates = data.get("candidates") or []
    if direct_id:
        selected_id = int(direct_id.group(1))
        if previous_tool in TOOL_OBJECTS:
            return {"target_id": selected_id}
        for candidate in candidates:
            if int(candidate.get("id") or 0) == selected_id:
                if previous_tool == "create_student":
                    return {"clazz_id": selected_id}
                if previous_tool == "create_class":
                    return {"counselor_id": selected_id} if candidate.get("employee_no") or candidate.get("position") else {"department_id": selected_id}
                if previous_tool in {"create_teacher", "create_course"}:
                    return {"teacher_id": selected_id} if candidate.get("employee_no") or candidate.get("position") else {"department_id": selected_id}
    if not candidates:
        return {}
    idx = _candidate_selection_index(message)
    if idx is None or idx < 0 or idx >= len(candidates):
        return {}
    candidate = candidates[idx]
    selected_id = candidate.get("id")
    if not selected_id:
        return {}
    if previous_tool in TOOL_OBJECTS:
        return {"target_id": selected_id}
    if previous_tool == "create_student":
        return {"clazz_id": selected_id}
    if previous_tool in {"create_teacher", "create_course", "create_class"}:
        if candidate.get("employee_no") or candidate.get("position"):
            if previous_tool == "create_class":
                return {"counselor_id": selected_id}
            return {"teacher_id": selected_id}
        return {"department_id": selected_id}
    return {}


def _parse_tool_args_for_message(tool_code: str, message: str) -> dict:
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


def _can_continue_previous_tool(message: str, previous_context: dict | None) -> bool:
    if not previous_context:
        return False
    previous_tool = previous_context.get("tool_code")
    previous_status = previous_context.get("tool_status")
    if previous_tool not in CREATE_TOOL_CODES and previous_tool not in TOOL_OBJECTS:
        return False
    if previous_status not in {"need_more_info", "confirm_required"}:
        return False
    if _extract_candidate_target_args(message, previous_context):
        return True
    if _detect_operation_tool(message):
        return False
    parsed = _parse_tool_args_for_message(previous_tool, message)
    if previous_tool in TOOL_OBJECTS:
        return bool(parsed.get("target_id") or parsed.get("target_keyword") or parsed.get("changes"))
    return bool(parsed)


def _tool_response_mode(tool_code: str) -> str:
    if tool_code in QUERY_TOOL_CODES or tool_code in CREATE_TOOL_CODES or tool_code in TOOL_OBJECTS:
        return "academic_ops"
    return "academic_tools"


def _draft_payload_from_tool_result(tool_result) -> tuple[list, list]:
    data = tool_result.data if isinstance(tool_result.data, dict) else {}
    missing_fields = data.get("missing_fields") or []
    candidates = data.get("candidates") or []
    return missing_fields, candidates


def _should_store_draft(tool_code: str, tool_result) -> bool:
    return (
        tool_code in CREATE_TOOL_CODES or tool_code in TOOL_OBJECTS
    ) and tool_result.status == "need_more_info"


def _should_finish_draft(tool_result) -> bool:
    return tool_result.status in {"confirm_required", "success"}


def _detect_followup_tool(message: str, previous_tool: str | None) -> str | None:
    if not previous_tool:
        return None
    text = (message or "").strip()
    if not text:
        return None
    followup_words = ["那", "再", "只看", "筛选", "换成", "今天", "明天", "上一条", "详细", "继续", "这个", "这个人", "这个学生", "这名学生", "该学生", "他", "她"]
    if not any(word in text for word in followup_words):
        return None
    if previous_tool == "query_my_schedule" and any(word in text for word in ["今天", "明天", "课", "上课", "那"]):
        return previous_tool
    if previous_tool == "query_my_attendance" and any(word in text for word in ["请假", "迟到", "缺勤", "考勤", "只看", "那"]):
        return previous_tool
    if previous_tool == "query_my_leave" and any(word in text for word in ["待审批", "通过", "驳回", "请假", "那", "只看"]):
        return previous_tool
    if previous_tool == "query_announcements" and any(word in text for word in ["公告", "通知", "再", "上一条", "详细"]):
        return previous_tool
    if previous_tool in {"query_student", "query_teacher", "query_course", "query_score", "query_class"} and any(
        word in text for word in ["再", "换成", "查", "查询", "搜索", "只看", "详细", "那"]
    ):
        return previous_tool
    return None


def _extract_memory_reference_args(message: str, previous_context: dict | None, detected_tool: str | None) -> dict:
    if detected_tool != "query_student" or not previous_context:
        return {}
    text = message or ""
    if not any(word in text for word in ["这个", "这个人", "这个学生", "这名学生", "该学生", "他", "她"]):
        return {}
    if re.search(r"[Ss]\d{6,}", text):
        return {}
    if previous_context.get("tool_code") != "query_student":
        return {}
    data = previous_context.get("tool_data") or {}
    items = data.get("items") or []
    if not items:
        return {}
    item = items[0]
    student_no = item.get("student_no")
    if student_no:
        return {"keyword": student_no}
    if item.get("name"):
        return {"keyword": item.get("name")}
    return {}


def _format_previous_context_hint(previous_context: dict | None) -> str:
    if not previous_context:
        return ""
    tool_code = previous_context.get("tool_code")
    if not tool_code:
        return ""
    tool_names = {
        "query_student": "学生查询",
        "query_teacher": "教师查询",
        "query_course": "课程查询",
        "query_score": "成绩查询",
        "query_class": "班级查询",
        "query_department": "院系查询",
        "query_classroom": "教室查询",
        "query_term": "学期查询",
        "create_student": "新增学生",
        "create_teacher": "新增教师",
        "create_course": "新增课程",
        "create_class": "新增班级",
        "update_student": "修改学生",
        "update_teacher": "修改教师",
        "update_course": "修改课程",
        "update_class": "修改班级",
    }
    name = tool_names.get(tool_code, tool_code)
    status = previous_context.get("tool_status")
    if status in {"need_more_info", "confirm_required"}:
        return f"\n我还记得上一轮正在处理“{name}”，你可以继续补充缺少的信息，或者说“取消”。"
    return f"\n我会结合上一轮的“{name}”结果理解类似“这个人”“他/她”“再筛选一下”的追问。"


def _format_unmatched_reply(
    *,
    mode: str,
    available_tools: list[dict],
    previous_context: dict | None,
) -> str:
    memory_hint = _format_previous_context_hint(previous_context)
    if mode in {"auto", "academic_tools", "academic_ops"}:
        examples = [
            "查询学生张三",
            "查询成绩",
            "查询教师王老师",
            "新增学生李雷 学号2026001 性别男 班级软件2401",
            "把课程高等数学学分改成4",
            "发布公告 标题期末安排 内容本周五前完成复习",
        ]
        available_names = "、".join(tool.get("name", "") for tool in available_tools[:8] if tool.get("name"))
        lines = [
            "我还没抓准你要查询或操作哪类数据。",
            f"当前账号可用能力包括：{available_names or '暂无可用工具'}。",
            "你可以换一种更明确的说法，例如：",
        ]
        lines.extend(f"- {item}" for item in examples)
        if memory_hint:
            lines.append(memory_hint.strip())
        return "\n".join(lines)

    hint = MODE_HINTS.get(mode, "当前能力模块还没有专用处理器。")
    return f"{hint}\n这个模块还需要更明确的问题描述；也可以切回“自动”或“教务助手”来查询和维护系统数据。{memory_hint}"


def _chat_response(
    *,
    session_id: str,
    reply: str,
    mode: str,
    intent: str,
    tool_calls: list,
    suggested_mode: str | None = None,
    references: list | None = None,
):
    return success(data={
        "session_id": session_id,
        "reply": reply,
        "mode": mode,
        "intent": intent,
        "tool_calls": tool_calls,
        "references": references or [],
        "suggested_questions": _suggested_questions(suggested_mode or mode),
    })


def _format_rag_references(sources: list[dict]) -> list[dict]:
    refs = []
    for item in sources or []:
        refs.append({
            "id": item.get("chunk_id"),
            "title": item.get("title") or f"文档 {item.get('document_id')}",
            "content": "",
            "score": item.get("score") or 0,
            "metadata": {
                "kb_id": item.get("kb_id"),
                "document_id": item.get("document_id"),
                "chunk_no": item.get("chunk_no"),
                "vector_score": item.get("vector_score"),
                "bm25_score": item.get("bm25_score"),
                "title_score": item.get("title_score"),
            },
        })
    return refs


def _answer_with_knowledge_base(
    *,
    db: Session,
    user: User,
    conversation,
    session_id: str,
    message: str,
    mode: str,
):
    result = rag_knowledge_service.answer(
        db=db,
        user=user,
        question=message,
        kb_ids=None,
        top_k=5,
        min_score=0,
    )
    reply = result.get("answer") or "我没有在当前可访问的知识库中检索到足够相关的内容。"
    references = _format_rag_references(result.get("sources") or [])
    if not references:
        reply = (
            "我还没有在你的综合知识库里找到可引用的资料。\n"
            "你可以先进入“综合知识库”页面，新建知识库并导入文本、Markdown 或 PDF，然后再回来问我。"
        )
    append_turn(
        db,
        conversation,
        user_message=message,
        assistant_reply=reply,
        mode="rag",
        intent="rag_knowledge_ask",
        tool_data={"references": references},
    )
    return _chat_response(
        session_id=session_id,
        reply=reply,
        mode="rag",
        intent="rag_knowledge_ask",
        tool_calls=[],
        references=references,
        suggested_mode="rag",
    )


@router.get("/modes")
def list_modes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = []
    available_tools = get_available_tools(user, db)
    for mode in ASSISTANT_MODES:
        item = _normalize_mode_item(mode)
        if mode["code"] in {"academic_tools", "academic_ops"}:
            item["tools"] = available_tools
        data.append(item)
    return success(data=data)


@router.get("/tools")
def list_tools(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(data=get_available_tools(user, db))


def _format_session_item(conversation) -> dict:
    messages = get_messages(conversation)
    last_message = messages[-1] if messages else {}
    last_user_message = next(
        (msg for msg in reversed(messages) if msg.get("role") == "user"),
        {},
    )
    return {
        "session_id": conversation.session_id,
        "title": conversation_title(conversation),
        "message_count": len(messages),
        "last_message": (last_message.get("content") or "")[:120],
        "last_user_message": (last_user_message.get("content") or "")[:120],
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


@router.get("/sessions")
def list_chat_sessions(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = list_user_sessions(db, user, limit=limit)
    return success(data=[_format_session_item(item) for item in sessions])


@router.get("/sessions/{session_id}")
def get_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_user_session(db, user, session_id)
    if not conversation:
        return success(data=None, message="会话不存在或已失效")
    return success(data={
        **_format_session_item(conversation),
        "messages": get_messages(conversation),
    })


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = delete_user_session(db, user, session_id)
    return success(data={"deleted": deleted}, message="会话已删除" if deleted else "会话不存在或已删除")


@router.get("/payment-code")
def get_payment_code(
    user: User = Depends(get_current_user),
):
    """Return the demo payment QR code used by the floating assistant."""
    project_root = Path(__file__).resolve().parents[3]
    image_path = project_root / "文本" / "wintall_pay.jpg"
    if not image_path.exists():
        return success(data=None, message="收款码暂未配置")
    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename="wintall_pay.jpg",
    )


@router.post("/files")
async def upload_agent_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    return success(data=await save_agent_file(user, file), message="上传成功")


@router.post("/clear")
def clear_chat(
    body: CampusAgentClearRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.session_id:
        _, conversation = get_or_create_session(db, body.session_id, user)
        clear_session(db, conversation)
        active_draft = get_active_draft(db, user=user, session_id=body.session_id)
        if active_draft:
            mark_draft_cancelled(db, active_draft)
    return success(message="校园助手对话已清空")


@router.post("/chat")
def chat(
    body: CampusAgentChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mode = body.mode if _mode_exists(body.mode) else "auto"
    session_id, conversation = get_or_create_session(db, body.session_id, user)
    agent_response = CampusAgentOrchestrator(db).chat(
        user=user,
        conversation=conversation,
        session_id=session_id,
        message=body.message.strip(),
        mode=mode,
        file_ids=body.file_ids,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
    )
    return _chat_response(
        session_id=session_id,
        reply=agent_response.reply,
        mode=agent_response.mode,
        intent=agent_response.intent,
        tool_calls=agent_response.tool_calls,
        references=agent_response.references,
        suggested_mode=agent_response.suggested_mode,
    )
