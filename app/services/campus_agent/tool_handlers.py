"""Concrete handlers for campus assistant tools."""
import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.clazz import Clazz
from app.models.department import Department
from app.models.teacher import Teacher
from app.models.user import User
from app.models.announcement import Announcement
from app.models.course import Course
from app.models.exam import Exam
from app.models.schedule import Classroom, CourseSchedule, Term
from app.models.score import Score
from app.models.student import Student, StudentCourse
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.schemas.clazz import ClazzCreate, ClazzUpdate
from app.schemas.common import PageParams
from app.schemas.course import CourseCreate, CourseUpdate
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.schemas.leave import LeaveRequestCreate
from app.schemas.schedule import ClassroomCreate, ClassroomUpdate, TermCreate, TermUpdate
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.services import (
    announcement_service,
    attendance_service,
    clazz_service,
    course_service,
    department_service,
    email_service,
    leave_service,
    schedule_service,
    student_service,
    teacher_service,
)
from app.utils.entity_mappers import (
    attendance_record_to_dict,
    announcement_to_dict,
    clazz_to_dict,
    classroom_to_dict,
    course_to_dict,
    course_schedule_to_dict,
    score_to_dict,
    department_to_dict,
    leave_request_to_dict,
    student_to_dict,
    teacher_to_dict,
    term_to_dict,
)
from app.utils.pagination import paginate
from app.services.campus_agent.pending_actions import (
    create_pending_action,
    log_agent_operation,
)
from app.utils.weather import get_weather, get_weather_by_ip


WEEKDAY_NAMES = {
    1: "周一",
    2: "周二",
    3: "周三",
    4: "周四",
    5: "周五",
    6: "周六",
    7: "周日",
}

STATUS_TEXT = {
    "normal": "正常",
    "present": "正常",
    "late": "迟到",
    "early_leave": "早退",
    "absent": "缺勤",
    "leave": "请假",
    "manual": "手工记录",
    "pending": "待审批",
    "approved": "已通过",
    "rejected": "已驳回",
    "cancelled": "已撤销",
}

STUDENT_STATUS_TEXT = {
    0: "退学",
    1: "在读",
    2: "休学",
    3: "毕业",
}

TEACHER_STATUS_TEXT = {
    0: "离职",
    1: "在职",
}

COMMON_STATUS_TEXT = {
    0: "停用",
    1: "正常",
}

TOOL_TARGETS: dict[str, dict[str, Any]] = {}


def _limit(value: Any, default: int = 8, max_value: int = 100) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(1, min(number, max_value))


def _page_params(args: dict | None = None, default_size: int = 8) -> PageParams:
    args = args or {}
    try:
        page = int(args.get("page") or 1)
    except Exception:
        page = 1
    return PageParams(
        page=max(1, page),
        page_size=_limit(args.get("limit"), default=default_size),
        keyword=args.get("keyword"),
    )


def _requested_field(text: str) -> str | None:
    return _student_requested_field(text)


def _student_requested_field(text: str) -> str | None:
    if any(word in text for word in ["性别", "男", "女"]):
        return "gender"
    if any(word in text for word in ["手机号", "电话", "联系方式"]):
        return "phone"
    if "邮箱" in text:
        return "email"
    if "班级" in text:
        return "clazz_name"
    if "哪个班" in text or "哪班" in text:
        return "clazz_name"
    if any(word in text for word in ["院系", "学院"]):
        return "department_name"
    if "状态" in text:
        return "status"
    if "学号" in text:
        return "student_no"
    if "姓名" in text or "名字" in text:
        return "name"
    return None


def _teacher_requested_field(text: str) -> str | None:
    if "工号" in text:
        return "employee_no"
    if any(word in text for word in ["岗位", "职位"]):
        return "position"
    if "职称" in text:
        return "title"
    if any(word in text for word in ["院系", "学院"]):
        return "department_name"
    if any(word in text for word in ["手机号", "电话", "联系方式"]):
        return "phone"
    if "邮箱" in text:
        return "email"
    if "状态" in text:
        return "status"
    if "姓名" in text or "名字" in text:
        return "name"
    return None


def _student_field_text(item: dict, field: str) -> tuple[str, str]:
    labels = {
        "gender": "性别",
        "phone": "手机号",
        "email": "邮箱",
        "clazz_name": "班级",
        "department_name": "院系",
        "status": "状态",
        "student_no": "学号",
        "name": "姓名",
    }
    value = item.get(field)
    if field == "gender":
        value = "男" if item.get("gender") == 1 else "女" if item.get("gender") == 2 else "未设置"
    elif field == "status":
        value = STUDENT_STATUS_TEXT.get(item.get("status"), item.get("status") or "未设置")
    return labels.get(field, field), str(value or "未设置")


def _teacher_field_text(item: dict, field: str) -> tuple[str, str]:
    labels = {
        "employee_no": "工号",
        "position": "岗位",
        "title": "职称",
        "department_name": "院系",
        "phone": "手机号",
        "email": "邮箱",
        "status": "状态",
        "name": "姓名",
    }
    value = item.get(field)
    if field == "status":
        value = TEACHER_STATUS_TEXT.get(item.get("status"), item.get("status") or "未设置")
    return labels.get(field, field), str(value or "未设置")


def _format_date(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _format_datetime(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _gender_text(value: Any) -> str:
    return {1: "男", 2: "女"}.get(value, str(value or "未设置"))


def _mask_id_card(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) < 10:
        return text or "未设置"
    return f"{text[:6]}********{text[-4:]}"


def _resolve_clazz(args: dict, db: Session) -> tuple[int | None, str | None, list[dict]]:
    clazz_id = args.get("clazz_id")
    if clazz_id:
        clazz = db.query(Clazz).filter(Clazz.id == int(clazz_id), Clazz.is_deleted == False).first()
        if clazz:
            return clazz.id, clazz.name, []
        return None, None, []

    keyword = (args.get("clazz_keyword") or args.get("clazz_name") or "").strip()
    if not keyword:
        return None, None, []

    matches = db.query(Clazz).filter(
        Clazz.is_deleted == False,
        or_(Clazz.name.contains(keyword), Clazz.code.contains(keyword)),
    ).limit(5).all()
    if len(matches) == 1:
        return matches[0].id, matches[0].name, []
    candidates = [
        {"id": item.id, "name": item.name, "code": item.code, "grade": item.grade}
        for item in matches
    ]
    return None, None, candidates


def _resolve_department(args: dict, db: Session) -> tuple[int | None, str | None, list[dict]]:
    department_id = args.get("department_id")
    if department_id:
        dept = db.query(Department).filter(Department.id == int(department_id), Department.is_deleted == False).first()
        if dept:
            return dept.id, dept.name, []
        return None, None, []

    keyword = (args.get("department_keyword") or args.get("department_name") or "").strip()
    if not keyword:
        return None, None, []
    matches = db.query(Department).filter(
        Department.is_deleted == False,
        or_(Department.name.contains(keyword), Department.code.contains(keyword)),
    ).limit(5).all()
    if len(matches) == 1:
        return matches[0].id, matches[0].name, []
    candidates = [{"id": item.id, "name": item.name, "code": item.code} for item in matches]
    return None, None, candidates


def _resolve_teacher(args: dict, db: Session, key_prefix: str = "teacher") -> tuple[int | None, str | None, list[dict]]:
    teacher_id = args.get(f"{key_prefix}_id")
    if teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == int(teacher_id), Teacher.is_deleted == False).first()
        if teacher:
            return teacher.id, teacher.name, []
        return None, None, []

    keyword = (args.get(f"{key_prefix}_keyword") or args.get(f"{key_prefix}_name") or "").strip()
    if not keyword:
        return None, None, []
    matches = db.query(Teacher).filter(
        Teacher.is_deleted == False,
        or_(Teacher.name.contains(keyword), Teacher.employee_no.contains(keyword)),
    ).limit(5).all()
    if len(matches) == 1:
        return matches[0].id, matches[0].name, []
    candidates = [
        {"id": item.id, "name": item.name, "employee_no": item.employee_no, "position": item.position}
        for item in matches
    ]
    return None, None, candidates


def _get_config(tool_code: str) -> dict[str, Any]:
    config = TOOL_TARGETS.get(tool_code)
    if not config:
        raise ValueError(f"Unsupported tool: {tool_code}")
    return config


def _target_keyword(args: dict) -> str:
    return str(args.get("target_keyword") or args.get("keyword") or "").strip()


def _target_id(args: dict) -> int | None:
    value = args.get("target_id") or args.get("id")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _target_label(config: dict[str, Any], item: Any) -> str:
    name = getattr(item, config["name_attr"], None) or ""
    code_attr = config.get("code_attr")
    code = getattr(item, code_attr, None) if code_attr else None
    if code:
        return f"{name}（{code}）"
    return str(name or f"ID {item.id}")


def _candidate_dict(config: dict[str, Any], item: Any) -> dict:
    data = {"id": item.id, "name": getattr(item, config["name_attr"], None)}
    code_attr = config.get("code_attr")
    if code_attr:
        data[code_attr] = getattr(item, code_attr, None)
    return data


def _find_targets(config: dict[str, Any], args: dict, db: Session) -> tuple[Any | None, list[dict]]:
    target_id = _target_id(args)
    model = config["model"]
    if target_id:
        item = db.query(model).filter(model.id == target_id, model.is_deleted == False).first()
        return item, [] if item else []

    keyword = _target_keyword(args)
    if not keyword:
        return None, []

    filters = [getattr(model, config["name_attr"]).contains(keyword)]
    code_attr = config.get("code_attr")
    if code_attr:
        filters.append(getattr(model, code_attr).contains(keyword))
    matches = db.query(model).filter(model.is_deleted == False, or_(*filters)).limit(6).all()
    if len(matches) == 1:
        return matches[0], []
    return None, [_candidate_dict(config, item) for item in matches]


def _need_target_message(config: dict[str, Any], candidates: list[dict] | None = None) -> dict:
    label = config["label"]
    if candidates:
        lines = [f"我找到了多个可能的{label}，请补充更准确的名称、编号，或直接指定 ID："]
        for item in candidates:
            extra = ""
            for key, value in item.items():
                if key not in {"id", "name"} and value:
                    extra = f"，{key}：{value}"
                    break
            lines.append(f"- ID {item['id']}：{item.get('name')}{extra}")
        return {
            "status": "need_more_info",
            "message": "\n".join(lines),
            "confirm_required": False,
            "data": {"candidates": candidates},
        }
    return {
        "status": "need_more_info",
        "message": f"请告诉我要操作哪一个{label}，可以提供 ID、名称或编号。",
        "confirm_required": False,
        "data": {"missing_fields": ["target"], "args": {}},
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "未设置"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _field_label(config: dict[str, Any], field: str) -> str:
    return config.get("field_labels", {}).get(field, field)


def _normalize_update_changes(tool_code: str, changes: dict, db: Session) -> tuple[dict, str | None]:
    prepared = dict(changes or {})
    if not prepared:
        return {}, None

    if tool_code == "update_student":
        if prepared.get("clazz_keyword") or prepared.get("clazz_name") or prepared.get("clazz_id"):
            clazz_id, _, candidates = _resolve_clazz(prepared, db)
            if candidates:
                return {}, "班级匹配到多个候选，请补充更准确的班级名称或指定班级 ID。"
            if not clazz_id:
                return {}, "没有找到匹配的班级，请补充正确的班级名称或班级 ID。"
            prepared["clazz_id"] = clazz_id
    elif tool_code in {"update_teacher", "update_course", "update_class"}:
        if prepared.get("department_keyword") or prepared.get("department_name") or prepared.get("department_id"):
            department_id, _, candidates = _resolve_department(prepared, db)
            if candidates:
                return {}, "院系匹配到多个候选，请补充更准确的院系名称或指定院系 ID。"
            if not department_id:
                return {}, "没有找到匹配的院系，请补充正确的院系名称或院系 ID。"
            prepared["department_id"] = department_id
        if tool_code == "update_course" and (
            prepared.get("teacher_keyword") or prepared.get("teacher_name") or prepared.get("teacher_id")
        ):
            teacher_id, _, candidates = _resolve_teacher(prepared, db, "teacher")
            if candidates:
                return {}, "教师匹配到多个候选，请补充更准确的教师姓名/工号或指定教师 ID。"
            if not teacher_id:
                return {}, "没有找到匹配的教师，请补充正确的教师姓名、工号或教师 ID。"
            prepared["teacher_id"] = teacher_id
        if tool_code == "update_class" and (
            prepared.get("counselor_keyword") or prepared.get("counselor_name") or prepared.get("counselor_id")
        ):
            teacher_id, _, candidates = _resolve_teacher(prepared, db, "counselor")
            if candidates:
                return {}, "班主任/辅导员匹配到多个候选，请补充更准确的教师姓名/工号或指定教师 ID。"
            if not teacher_id:
                return {}, "没有找到匹配的班主任/辅导员，请补充正确的教师姓名、工号或教师 ID。"
            prepared["counselor_id"] = teacher_id

    for key in ["enrollment_date", "entry_date", "start_date", "end_date"]:
        if prepared.get(key):
            parsed = _parse_date(prepared.get(key))
            if not parsed:
                return {}, f"{key} 日期格式建议使用 YYYY-MM-DD。"
            prepared[key] = parsed.isoformat()

    for temp_key in [
        "clazz_keyword",
        "clazz_name",
        "department_keyword",
        "department_name",
        "teacher_keyword",
        "teacher_name",
        "counselor_keyword",
        "counselor_name",
    ]:
        prepared.pop(temp_key, None)
    return prepared, None


def _pending_action_response(
    user: User,
    args: dict,
    db: Session,
    *,
    tool_code: str,
    payload: dict,
    summary: str,
    risk: str,
) -> dict:
    pending = create_pending_action(
        db,
        user=user,
        session_id=args.get("_session_id"),
        tool_code=tool_code,
        args=payload,
        summary=summary,
        risk=risk,
    )
    return {
        "status": "confirm_required",
        "message": f"{summary}\n\n待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后执行，10 分钟内有效。",
        "confirm_required": True,
        "data": {
            "pending_action_id": pending.id,
            "tool": tool_code,
            "args": payload,
            "summary": summary,
            "expires_at": _format_datetime(pending.expires_at),
        },
    }


def _prepare_update_object(user: User, args: dict, db: Session, tool_code: str) -> dict:
    config = _get_config(tool_code)
    target, candidates = _find_targets(config, args, db)
    if not target:
        return _need_target_message(config, candidates)

    changes, error = _normalize_update_changes(tool_code, args.get("changes") or {}, db)
    if error:
        return {"status": "need_more_info", "message": error, "confirm_required": False, "data": {"args": args}}
    if not changes:
        return {
            "status": "need_more_info",
            "message": f"请告诉我要修改{config['label']}的哪些字段，例如名称、编号、状态、联系方式等。",
            "confirm_required": False,
            "data": {"missing_fields": ["changes"], "target_id": target.id},
        }

    schema = config["update_schema"](**changes)
    payload = schema.model_dump(mode="json", exclude_unset=True)
    if not payload:
        return {
            "status": "need_more_info",
            "message": f"没有识别到可修改的{config['label']}字段，请换一种说法再试。",
            "confirm_required": False,
            "data": {"target_id": target.id},
        }

    lines = [f"请确认是否修改{config['label']}：{_target_label(config, target)}"]
    for field, new_value in payload.items():
        if field in {"phone", "email"}:
            old_value = getattr(getattr(target, "user", None), field, None)
        else:
            old_value = getattr(target, field, None)
        lines.append(f"- {_field_label(config, field)}：{_format_value(old_value)} -> {_format_value(new_value)}")
    summary = "\n".join(lines)
    return _pending_action_response(
        user,
        args,
        db,
        tool_code=tool_code,
        payload={"target_id": target.id, "changes": payload},
        summary=summary,
        risk="medium",
    )


def _update_object(user: User, args: dict, db: Session, tool_code: str) -> dict:
    if args.get("_prepare"):
        return _prepare_update_object(user, args, db, tool_code)
    config = _get_config(tool_code)
    target_id = int(args["target_id"])
    changes = args.get("changes") or {}
    schema = config["update_schema"](**changes)
    item = config["update_service"](target_id, schema, db) if tool_code != "update_announcement" else config["update_service"](target_id, schema, user.id, db)
    item = config["get_service"](item.id, db)
    log_agent_operation(
        db,
        user=user,
        tool_code=tool_code,
        module=config["module"],
        action="update",
        target_id=item.id,
        detail={"target": config["target"], "target_id": item.id, "changes": changes},
    )
    return {"message": f"已修改{config['label']}：{_target_label(config, item)}。", "data": config["to_dict"](item)}


def _prepare_delete_object(user: User, args: dict, db: Session, tool_code: str) -> dict:
    config = _get_config(tool_code)
    target, candidates = _find_targets(config, args, db)
    if not target:
        return _need_target_message(config, candidates)
    summary = (
        f"请确认是否{config.get('delete_word', '停用')}{config['label']}：{_target_label(config, target)}\n"
        "- 该操作会调用系统现有删除逻辑，当前项目中多数业务对象为软删除。\n"
        "- 如该对象已被课表、成绩等数据引用，原 service 可能会拒绝执行。"
    )
    return _pending_action_response(
        user,
        args,
        db,
        tool_code=tool_code,
        payload={"target_id": target.id},
        summary=summary,
        risk="high",
    )


def _delete_object(user: User, args: dict, db: Session, tool_code: str) -> dict:
    if args.get("_prepare"):
        return _prepare_delete_object(user, args, db, tool_code)
    config = _get_config(tool_code)
    target_id = int(args["target_id"])
    target = config["get_service"](target_id, db)
    label = _target_label(config, target)
    if tool_code == "delete_announcement":
        config["delete_service"](target_id, user.id, db)
    else:
        config["delete_service"](target_id, db)
    log_agent_operation(
        db,
        user=user,
        tool_code=tool_code,
        module=config["module"],
        action="delete",
        target_id=target_id,
        detail={"target": config["target"], "target_id": target_id, "label": label},
    )
    return {"message": f"已{config.get('delete_word', '停用')}{config['label']}：{label}。", "data": {"id": target_id}}


def _student_summary(args: dict, clazz_name: str | None = None) -> str:
    lines = [
        "请确认是否新增以下学生：",
        f"- 姓名：{args.get('name')}",
        f"- 学号：{args.get('student_no')}",
        f"- 性别：{_gender_text(args.get('gender'))}",
        f"- 身份证号：{_mask_id_card(args.get('id_card'))}",
        f"- 班级：{clazz_name or args.get('clazz_name') or args.get('clazz_id')}",
    ]
    if args.get("phone"):
        lines.append(f"- 手机号：{args.get('phone')}")
    if args.get("email"):
        lines.append(f"- 邮箱：{args.get('email')}")
    if args.get("enrollment_date"):
        lines.append(f"- 入学日期：{args.get('enrollment_date')}")
    lines.append("")
    lines.append("确认后我会创建学生档案和对应登录账号。")
    return "\n".join(lines)


def _teacher_summary(args: dict, department_name: str | None = None) -> str:
    lines = [
        "请确认是否新增以下教师：",
        f"- 姓名：{args.get('name')}",
        f"- 工号：{args.get('employee_no')}",
        f"- 性别：{_gender_text(args.get('gender'))}",
        f"- 身份证号：{_mask_id_card(args.get('id_card'))}",
        f"- 岗位：{args.get('position')}",
        f"- 院系：{department_name or args.get('department_name') or args.get('department_id') or '未设置'}",
    ]
    if args.get("title"):
        lines.append(f"- 职称：{args.get('title')}")
    if args.get("phone"):
        lines.append(f"- 手机号：{args.get('phone')}")
    if args.get("email"):
        lines.append(f"- 邮箱：{args.get('email')}")
    if args.get("entry_date"):
        lines.append(f"- 入职日期：{args.get('entry_date')}")
    lines.append("")
    lines.append("确认后我会创建教师档案和对应登录账号。")
    return "\n".join(lines)


def _course_type_text(value: Any) -> str:
    return {1: "必修", 2: "选修", 3: "公共课"}.get(value, str(value or "未设置"))


def _course_summary(args: dict, department_name: str | None = None, teacher_name: str | None = None) -> str:
    lines = [
        "请确认是否新增以下课程：",
        f"- 课程名称：{args.get('name')}",
        f"- 课程编号：{args.get('code')}",
        f"- 学分：{args.get('credit')}",
        f"- 学时：{args.get('hours')}",
        f"- 课程类型：{_course_type_text(args.get('course_type'))}",
        f"- 院系：{department_name or args.get('department_name') or args.get('department_id')}",
    ]
    if args.get("teacher_id") or teacher_name:
        lines.append(f"- 任课教师：{teacher_name or args.get('teacher_id')}")
    if args.get("description"):
        lines.append(f"- 简介：{args.get('description')}")
    lines.append("")
    lines.append("确认后我会创建课程记录。")
    return "\n".join(lines)


def _class_summary(args: dict, department_name: str | None = None, counselor_name: str | None = None) -> str:
    lines = [
        "请确认是否新增以下班级：",
        f"- 班级名称：{args.get('name')}",
        f"- 班级编号：{args.get('code')}",
        f"- 年级：{args.get('grade')}",
        f"- 院系：{department_name or args.get('department_name') or args.get('department_id')}",
    ]
    if args.get("counselor_id") or counselor_name:
        lines.append(f"- 班主任/辅导员：{counselor_name or args.get('counselor_id')}")
    lines.append("")
    lines.append("确认后我会创建班级记录。")
    return "\n".join(lines)


def _prepare_create_student(user: User, args: dict, db: Session) -> dict:
    prepared = dict(args)
    clazz_id, clazz_name, candidates = _resolve_clazz(prepared, db)
    if candidates:
        lines = ["我找到了多个可能的班级，请补充更准确的班级名称或直接指定班级编号："]
        for item in candidates:
            lines.append(f"- ID {item['id']}：{item['name']}（{item['code']}，{item['grade']}级）")
        return {
            "status": "need_more_info",
            "message": "\n".join(lines),
            "confirm_required": False,
            "data": {"missing_fields": ["clazz_id"], "candidates": candidates},
        }
    if clazz_id:
        prepared["clazz_id"] = clazz_id

    required = {
        "name": "姓名",
        "student_no": "学号",
        "gender": "性别",
        "id_card": "身份证号",
        "clazz_id": "班级",
    }
    missing = [label for key, label in required.items() if not prepared.get(key)]
    if missing:
        return {
            "status": "need_more_info",
            "message": "新增学生还缺少这些必填信息：" + "、".join(missing) + "。请补充后我再继续。",
            "confirm_required": False,
            "data": {"missing_fields": missing, "args": prepared},
        }

    enrollment_date = _parse_date(prepared.get("enrollment_date"))
    if prepared.get("enrollment_date") and not enrollment_date:
        return {
            "status": "need_more_info",
            "message": "入学日期格式建议使用 YYYY-MM-DD，例如 2026-09-01。",
            "confirm_required": False,
            "data": {"missing_fields": ["enrollment_date"], "args": prepared},
        }
    if enrollment_date:
        prepared["enrollment_date"] = enrollment_date.isoformat()

    try:
        student_data = StudentCreate(**prepared)
    except Exception as exc:
        return {
            "status": "need_more_info",
            "message": f"学生信息校验未通过：{exc}",
            "confirm_required": False,
            "data": {"args": prepared},
        }

    summary = _student_summary(student_data.model_dump(), clazz_name)
    pending = create_pending_action(
        db,
        user=user,
        session_id=args.get("_session_id"),
        tool_code="create_student",
        args=student_data.model_dump(mode="json"),
        summary=summary,
        risk="medium",
    )
    return {
        "status": "confirm_required",
        "message": f"{summary}\n\n待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后执行，10 分钟内有效。",
        "confirm_required": True,
        "data": {
            "pending_action_id": pending.id,
            "tool": "create_student",
            "args": student_data.model_dump(mode="json"),
            "summary": summary,
            "expires_at": _format_datetime(pending.expires_at),
        },
    }


def _create_student(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_student(user, args, db)

    student_data = StudentCreate(**args)
    student = student_service.create_student(student_data, db)
    log_agent_operation(
        db,
        user=user,
        tool_code="create_student",
        module="people",
        action="create",
        target_id=student.id,
        detail={
            "target": "student",
            "student_id": student.id,
            "student_no": student.student_no,
            "name": student.name,
            "clazz_id": student.clazz_id,
        },
    )
    item = student_to_dict(student_service.get_student(student.id, db))
    return {
        "message": f"已新增学生：{student.name}（学号：{student.student_no}）。",
        "data": item,
    }


def _prepare_create_teacher(user: User, args: dict, db: Session) -> dict:
    prepared = dict(args)
    department_id, department_name, candidates = _resolve_department(prepared, db)
    if candidates:
        lines = ["我找到了多个可能的院系，请补充更准确的院系名称或直接指定院系 ID："]
        for item in candidates:
            lines.append(f"- ID {item['id']}：{item['name']}（{item['code']}）")
        return {"status": "need_more_info", "message": "\n".join(lines), "confirm_required": False, "data": {"candidates": candidates}}
    if department_id:
        prepared["department_id"] = department_id

    required = {
        "name": "姓名",
        "employee_no": "工号",
        "gender": "性别",
        "id_card": "身份证号",
        "position": "岗位",
    }
    missing = [label for key, label in required.items() if not prepared.get(key)]
    if missing:
        return {
            "status": "need_more_info",
            "message": "新增教师还缺少这些必填信息：" + "、".join(missing) + "。请补充后我再继续。",
            "confirm_required": False,
            "data": {"missing_fields": missing, "args": prepared},
        }

    entry_date = _parse_date(prepared.get("entry_date"))
    if prepared.get("entry_date") and not entry_date:
        return {"status": "need_more_info", "message": "入职日期格式建议使用 YYYY-MM-DD。", "confirm_required": False, "data": {"args": prepared}}
    if entry_date:
        prepared["entry_date"] = entry_date.isoformat()

    try:
        teacher_data = TeacherCreate(**prepared)
    except Exception as exc:
        return {"status": "need_more_info", "message": f"教师信息校验未通过：{exc}", "confirm_required": False, "data": {"args": prepared}}

    summary = _teacher_summary(teacher_data.model_dump(), department_name)
    pending = create_pending_action(
        db,
        user=user,
        session_id=args.get("_session_id"),
        tool_code="create_teacher",
        args=teacher_data.model_dump(mode="json"),
        summary=summary,
        risk="medium",
    )
    return {
        "status": "confirm_required",
        "message": f"{summary}\n\n待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后执行，10 分钟内有效。",
        "confirm_required": True,
        "data": {"pending_action_id": pending.id, "tool": "create_teacher", "args": teacher_data.model_dump(mode="json"), "summary": summary},
    }


def _create_teacher(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_teacher(user, args, db)
    teacher_data = TeacherCreate(**args)
    teacher = teacher_service.create_teacher(teacher_data, db)
    log_agent_operation(
        db,
        user=user,
        tool_code="create_teacher",
        module="people",
        action="create",
        target_id=teacher.id,
        detail={"target": "teacher", "teacher_id": teacher.id, "employee_no": teacher.employee_no, "name": teacher.name},
    )
    item = teacher_to_dict(teacher_service.get_teacher(teacher.id, db))
    return {"message": f"已新增教师：{teacher.name}（工号：{teacher.employee_no}）。", "data": item}


def _prepare_create_course(user: User, args: dict, db: Session) -> dict:
    prepared = dict(args)
    department_id, department_name, dept_candidates = _resolve_department(prepared, db)
    if dept_candidates:
        lines = ["我找到了多个可能的院系，请补充更准确的院系名称或直接指定院系 ID："]
        for item in dept_candidates:
            lines.append(f"- ID {item['id']}：{item['name']}（{item['code']}）")
        return {"status": "need_more_info", "message": "\n".join(lines), "confirm_required": False, "data": {"candidates": dept_candidates}}
    if department_id:
        prepared["department_id"] = department_id

    teacher_name = None
    if prepared.get("teacher_keyword") or prepared.get("teacher_name") or prepared.get("teacher_id"):
        teacher_id, teacher_name, teacher_candidates = _resolve_teacher(prepared, db, "teacher")
        if teacher_candidates:
            lines = ["我找到了多个可能的任课教师，请补充更准确的教师姓名/工号或直接指定教师 ID："]
            for item in teacher_candidates:
                lines.append(f"- ID {item['id']}：{item['name']}（{item['employee_no']}，{item['position']}）")
            return {"status": "need_more_info", "message": "\n".join(lines), "confirm_required": False, "data": {"candidates": teacher_candidates}}
        if teacher_id:
            prepared["teacher_id"] = teacher_id

    required = {"name": "课程名称", "code": "课程编号", "credit": "学分", "hours": "学时", "course_type": "课程类型", "department_id": "院系"}
    missing = [label for key, label in required.items() if not prepared.get(key)]
    if missing:
        return {"status": "need_more_info", "message": "新增课程还缺少这些必填信息：" + "、".join(missing) + "。请补充后我再继续。", "confirm_required": False, "data": {"missing_fields": missing, "args": prepared}}

    try:
        course_data = CourseCreate(**prepared)
    except Exception as exc:
        return {"status": "need_more_info", "message": f"课程信息校验未通过：{exc}", "confirm_required": False, "data": {"args": prepared}}

    summary = _course_summary(course_data.model_dump(mode="json"), department_name, teacher_name)
    pending = create_pending_action(
        db,
        user=user,
        session_id=args.get("_session_id"),
        tool_code="create_course",
        args=course_data.model_dump(mode="json"),
        summary=summary,
        risk="medium",
    )
    return {"status": "confirm_required", "message": f"{summary}\n\n待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后执行，10 分钟内有效。", "confirm_required": True, "data": {"pending_action_id": pending.id, "tool": "create_course", "args": course_data.model_dump(mode="json"), "summary": summary}}


def _create_course(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_course(user, args, db)
    course_data = CourseCreate(**args)
    course = course_service.create_course(course_data, db)
    log_agent_operation(
        db,
        user=user,
        tool_code="create_course",
        module="teaching",
        action="create",
        target_id=course.id,
        detail={"target": "course", "course_id": course.id, "code": course.code, "name": course.name},
    )
    item = course_to_dict(course_service.get_course(course.id, db))
    return {"message": f"已新增课程：{course.name}（编号：{course.code}）。", "data": item}


def _prepare_create_class(user: User, args: dict, db: Session) -> dict:
    prepared = dict(args)
    department_id, department_name, dept_candidates = _resolve_department(prepared, db)
    if dept_candidates:
        lines = ["我找到了多个可能的院系，请补充更准确的院系名称或直接指定院系 ID："]
        for item in dept_candidates:
            lines.append(f"- ID {item['id']}：{item['name']}（{item['code']}）")
        return {"status": "need_more_info", "message": "\n".join(lines), "confirm_required": False, "data": {"candidates": dept_candidates}}
    if department_id:
        prepared["department_id"] = department_id

    counselor_name = None
    if prepared.get("counselor_keyword") or prepared.get("counselor_name") or prepared.get("counselor_id"):
        counselor_id, counselor_name, counselor_candidates = _resolve_teacher(prepared, db, "counselor")
        if counselor_candidates:
            lines = ["我找到了多个可能的班主任/辅导员，请补充更准确的姓名/工号或直接指定教师 ID："]
            for item in counselor_candidates:
                lines.append(f"- ID {item['id']}：{item['name']}（{item['employee_no']}，{item['position']}）")
            return {"status": "need_more_info", "message": "\n".join(lines), "confirm_required": False, "data": {"candidates": counselor_candidates}}
        if counselor_id:
            prepared["counselor_id"] = counselor_id

    required = {"name": "班级名称", "code": "班级编号", "department_id": "院系", "grade": "年级"}
    missing = [label for key, label in required.items() if not prepared.get(key)]
    if missing:
        return {"status": "need_more_info", "message": "新增班级还缺少这些必填信息：" + "、".join(missing) + "。请补充后我再继续。", "confirm_required": False, "data": {"missing_fields": missing, "args": prepared}}

    try:
        class_data = ClazzCreate(**prepared)
    except Exception as exc:
        return {"status": "need_more_info", "message": f"班级信息校验未通过：{exc}", "confirm_required": False, "data": {"args": prepared}}

    summary = _class_summary(class_data.model_dump(), department_name, counselor_name)
    pending = create_pending_action(
        db,
        user=user,
        session_id=args.get("_session_id"),
        tool_code="create_class",
        args=class_data.model_dump(mode="json"),
        summary=summary,
        risk="medium",
    )
    return {"status": "confirm_required", "message": f"{summary}\n\n待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后执行，10 分钟内有效。", "confirm_required": True, "data": {"pending_action_id": pending.id, "tool": "create_class", "args": class_data.model_dump(mode="json"), "summary": summary}}


def _create_class(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_class(user, args, db)
    class_data = ClazzCreate(**args)
    clazz = clazz_service.create_clazz(class_data, db)
    log_agent_operation(
        db,
        user=user,
        tool_code="create_class",
        module="org",
        action="create",
        target_id=clazz.id,
        detail={"target": "class", "clazz_id": clazz.id, "code": clazz.code, "name": clazz.name},
    )
    item = clazz_to_dict(clazz_service.get_clazz(clazz.id, db))
    return {"message": f"已新增班级：{clazz.name}（编号：{clazz.code}）。", "data": item}


def _query_department(user: User, args: dict, db: Session) -> dict:
    keyword = args.get("keyword")
    items = [department_to_dict(item) for item in department_service.list_departments(db, keyword)[:_limit(args.get("limit"), 8)]]
    if not items:
        return {"message": "没有查询到匹配的院系。", "data": {"total": 0, "items": []}}
    lines = [f"查询到 {len(items)} 个院系："]
    for item in items:
        lines.append(f"- {item.get('name')}（代码：{item.get('code')}），状态：{COMMON_STATUS_TEXT.get(item.get('status'), item.get('status'))}")
    return {"message": "\n".join(lines), "data": {"total": len(items), "items": items}}


def _query_classroom(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = schedule_service.list_classrooms(params, db)
    result = paginate(q, params)
    items = [classroom_to_dict(item) for item in result.get("items", [])]
    if not items:
        return {"message": "没有查询到匹配的教室。", "data": {"total": result.get("total", 0), "items": []}}
    lines = [f"查询到 {result.get('total', len(items))} 间教室，先显示 {len(items)} 间："]
    for item in items:
        lines.append(f"- {item.get('name')}，楼栋：{item.get('building') or '未设置'}，容量：{item.get('capacity')}，状态：{COMMON_STATUS_TEXT.get(item.get('status'), item.get('status'))}")
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_term(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = schedule_service.list_terms(params, db)
    result = paginate(q, params)
    items = [term_to_dict(item) for item in result.get("items", [])]
    if not items:
        return {"message": "没有查询到匹配的学期。", "data": {"total": result.get("total", 0), "items": []}}
    lines = [f"查询到 {result.get('total', len(items))} 个学期，先显示 {len(items)} 个："]
    for item in items:
        current = "，当前学期" if item.get("is_current") else ""
        lines.append(f"- {item.get('name')}（{item.get('academic_year')} 第{item.get('semester')}学期），{item.get('start_date')} 至 {item.get('end_date')}{current}")
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_weather(user: User, args: dict, db: Session) -> dict:
    city = (args.get("city") or "").strip()
    data = get_weather(city) if city else get_weather_by_ip()
    if not data:
        hint = f"{city}天气" if city else "默认城市天气"
        return {"message": f"暂时没有查到{hint}，可以换成“查询北京天气”这种说法再试一次。", "data": {"city": city}}

    current = data.get("current") or {}
    forecast = data.get("forecast") or []
    display_city = current.get("city") or city or "默认城市"
    temp = current.get("temperature") or "--"
    desc = current.get("description") or "天气暂缺"
    humidity = current.get("humidity") or "--"
    wind = current.get("feels_like") or current.get("wind_speed") or "--"
    lines = [f"{display_city}现在{desc}，气温 {temp}℃，湿度 {humidity}，风力/风向 {wind}。"]
    if forecast:
        lines.append("近几天预报：")
        for day in forecast[:3]:
            date_text = day.get("date") or "日期未知"
            low = day.get("min_temp") or "--"
            high = day.get("max_temp") or "--"
            day_desc = day.get("description") or "天气暂缺"
            lines.append(f"- {date_text}：{day_desc}，{low}-{high}℃")
    return {"message": "\n".join(lines), "data": data}


def _user_email_label(target: User) -> str:
    name = target.real_name or target.username
    return f"{name} <{target.email}>"


def _resolve_email_recipient(args: dict, db: Session, current_user: User) -> tuple[User | None, list[dict]]:
    recipient_email = (args.get("recipient_email") or "").strip().lower()
    if recipient_email:
        target = db.query(User).filter(User.email == recipient_email, User.is_deleted == False).first()
        return target, [] if target else []

    keyword = (args.get("recipient_keyword") or args.get("keyword") or "").strip()
    if not keyword:
        return None, []

    matches = email_service.search_users(keyword, current_user, db, limit=6)
    if len(matches) == 1:
        target = db.query(User).filter(User.id == int(matches[0]["id"]), User.is_deleted == False).first()
        return target, []
    return None, matches


def _person_email_candidates(keyword: str, db: Session, limit: int = 6) -> list[dict]:
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    like = f"%{keyword}%"
    items: list[dict] = []

    students = db.query(Student).options(joinedload(Student.user)).filter(
        Student.is_deleted == False,
        or_(
            Student.name.like(like),
            Student.student_no.like(like),
            Student.user.has(User.username.like(like)),
            Student.user.has(User.real_name.like(like)),
        ),
    ).order_by(Student.student_no.asc()).limit(limit + 1).all()
    for student in students:
        account = getattr(student, "user", None)
        items.append({
            "person_type": "student",
            "label": "学生",
            "id": student.id,
            "user_id": student.user_id,
            "name": student.name,
            "code": student.student_no,
            "email": getattr(account, "email", None),
            "username": getattr(account, "username", None),
        })
        if len(items) >= limit:
            return items

    teachers = db.query(Teacher).options(joinedload(Teacher.user)).filter(
        Teacher.is_deleted == False,
        or_(
            Teacher.name.like(like),
            Teacher.employee_no.like(like),
            Teacher.user.has(User.username.like(like)),
            Teacher.user.has(User.real_name.like(like)),
        ),
    ).order_by(Teacher.employee_no.asc()).limit(limit + 1).all()
    for teacher in teachers:
        account = getattr(teacher, "user", None)
        items.append({
            "person_type": "teacher",
            "label": "教师",
            "id": teacher.id,
            "user_id": teacher.user_id,
            "name": teacher.name,
            "code": teacher.employee_no,
            "email": getattr(account, "email", None),
            "username": getattr(account, "username", None),
        })
        if len(items) >= limit:
            break
    return items


def _clean_recipient_keyword(keyword: str | None) -> str:
    value = (keyword or "").strip(" ，,。")
    for phrase in ["发个邮件", "发一下邮件", "发份邮件", "发封邮件", "发邮件", "写邮件", "发送邮件", "发个信", "发信"]:
        value = value.replace(phrase, "")
    titles = ["学生", "同学", "教师", "老师", "教职工", "用户", "收件人"]
    changed = True
    while changed:
        changed = False
        for title in titles:
            if value.startswith(title) and len(value) > len(title):
                value = value[len(title):].strip(" 的，,。")
                changed = True
            if value.endswith(title) and len(value) > len(title):
                value = value[: -len(title)].strip(" 的，,。")
                changed = True
    return value


def _missing_email_fields(args: dict, *, bulk: bool = False) -> list[str]:
    missing = []
    if bulk and not args.get("recipient_scope"):
        missing.append("收件范围")
    if not bulk and not (args.get("recipient_email") or args.get("recipient_keyword") or args.get("recipient_user_id")):
        missing.append("收件人")
    if not args.get("subject"):
        missing.append("主题")
    if not args.get("body"):
        missing.append("正文")
    return missing


def _prepare_send_email(user: User, args: dict, db: Session) -> dict:
    prepared = dict(args)
    if prepared.get("recipient_keyword"):
        prepared["recipient_keyword"] = _clean_recipient_keyword(prepared.get("recipient_keyword"))
    if prepared.get("recipient_user_id"):
        target = db.query(User).filter(User.id == int(prepared["recipient_user_id"]), User.is_deleted == False).first()
        if target and target.email:
            prepared["recipient_email"] = target.email
    else:
        target, candidates = _resolve_email_recipient(prepared, db, user)
        if candidates:
            lines = ["我找到了多个可能的收件人，请补充姓名、用户名、邮箱，或直接指定用户 ID："]
            for item in candidates:
                lines.append(f"- ID {item['id']}：{item.get('real_name') or item.get('username')} <{item.get('email')}>")
            return {
                "status": "need_more_info",
                "message": "\n".join(lines),
                "confirm_required": False,
                "data": {"missing_fields": ["收件人"], "candidates": candidates, "args": prepared},
            }
        if target and target.email:
            prepared["recipient_user_id"] = target.id
            prepared["recipient_email"] = target.email

    if (prepared.get("recipient_keyword") or prepared.get("recipient_user_id")) and not prepared.get("recipient_email"):
        keyword = str(prepared.get("recipient_keyword") or "").strip()
        person_candidates = _person_email_candidates(keyword, db) if keyword else []
        if len(person_candidates) == 1 and not person_candidates[0].get("email"):
            person = person_candidates[0]
            update_hint = (
                f"把{person['name']}邮箱改为 {person['code'].lower()}@student.local"
                if person["person_type"] == "student"
                else f"把{person['name']}邮箱改为 {person['code'].lower()}@teacher.local"
            )
            return {
                "status": "need_more_info",
                "message": (
                    f"我找到了{person['label']}{person['name']}（{person['code']}），但他的账号还没有邮箱。\n"
                    f"管理员可以先补齐邮箱，例如：{update_hint}。补齐并确认后，再说“给{person['name']}发邮件”。"
                ),
                "confirm_required": False,
                "data": {
                    "missing_fields": ["收件人邮箱"],
                    "recipient_missing_email": person,
                    "args": prepared,
                },
            }
        if len(person_candidates) > 1:
            lines = ["我找到了多位姓名/账号相近的人，请说明发给哪一位："]
            for person in person_candidates:
                email = person.get("email") or "未设置邮箱"
                lines.append(f"- {person['label']}{person['name']}（{person['code']}，{email}）")
            return {
                "status": "need_more_info",
                "message": "\n".join(lines),
                "confirm_required": False,
                "data": {"missing_fields": ["收件人"], "candidates": person_candidates, "args": prepared},
            }
        return {
            "status": "need_more_info",
            "message": f"我没有找到“{prepared.get('recipient_keyword') or prepared.get('recipient_user_id')}”对应的可用邮箱，请补充更准确的姓名、用户名或邮箱。",
            "confirm_required": False,
            "data": {"missing_fields": ["收件人"], "args": prepared},
        }

    missing = _missing_email_fields(prepared)
    if missing:
        return {
            "status": "need_more_info",
            "message": "发邮件还缺少：" + "、".join(missing) + "。你可以直接补一句“主题是…… 内容是……”。",
            "confirm_required": False,
            "data": {"missing_fields": missing, "args": prepared},
        }

    summary = (
        "请确认是否发送邮件：\n"
        f"- 收件人：{prepared.get('recipient_email')}\n"
        f"- 主题：{prepared.get('subject')}\n"
        f"- 正文：{str(prepared.get('body') or '')[:120]}"
    )
    return _pending_action_response(
        user,
        prepared,
        db,
        tool_code="send_email",
        payload={
            "recipient_email": prepared["recipient_email"],
            "subject": prepared["subject"],
            "body": prepared["body"],
        },
        summary=summary,
        risk="medium",
    )


def _send_email(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_send_email(user, args, db)
    msg = email_service.send_email(
        sender=user,
        recipient_email=args["recipient_email"],
        subject=args["subject"],
        body=args.get("body") or "",
        attachments=None,
        db=db,
    )
    log_agent_operation(
        db,
        user=user,
        tool_code="send_email",
        module="email",
        action="send",
        target_id=msg.id,
        detail={"email_id": msg.id, "recipient_email": msg.recipient_email, "subject": msg.subject},
    )
    return {"message": f"邮件已发送给 {msg.recipient_email}，主题：{msg.subject}。", "data": {"id": msg.id}}


def _scope_label(scope: str) -> str:
    return {
        "students": "所有学生",
        "teachers": "所有教师",
        "all_users": "所有系统用户",
    }.get(scope, scope or "未指定范围")


def _collect_bulk_recipients(scope: str, db: Session, sender: User) -> tuple[list[User], int]:
    if scope == "students":
        records = db.query(Student).options(joinedload(Student.user)).filter(Student.is_deleted == False, Student.status == 1).all()
        users = [item.user for item in records if item.user and not item.user.is_deleted and item.user.id != sender.id]
    elif scope == "teachers":
        records = db.query(Teacher).options(joinedload(Teacher.user)).filter(Teacher.is_deleted == False, Teacher.status == 1).all()
        users = [item.user for item in records if item.user and not item.user.is_deleted and item.user.id != sender.id]
    elif scope == "all_users":
        users = db.query(User).filter(User.is_deleted == False, User.status == 1, User.id != sender.id).all()
    else:
        return [], 0

    with_email = []
    without_email = 0
    seen = set()
    for item in users:
        email = (item.email or "").strip().lower()
        if not email:
            without_email += 1
            continue
        if email in seen:
            continue
        seen.add(email)
        with_email.append(item)
    return with_email, without_email


def _prepare_send_bulk_email(user: User, args: dict, db: Session) -> dict:
    prepared = dict(args)
    missing = _missing_email_fields(prepared, bulk=True)
    if missing:
        return {
            "status": "need_more_info",
            "message": "群发邮件还缺少：" + "、".join(missing) + "。例如：主题是期末安排 内容是请按时完成复习。",
            "confirm_required": False,
            "data": {"missing_fields": missing, "args": prepared},
        }

    recipients, without_email = _collect_bulk_recipients(prepared["recipient_scope"], db, user)
    if not recipients:
        return {
            "status": "need_more_info",
            "message": f"{_scope_label(prepared['recipient_scope'])}里没有可发送邮箱的用户，请先补齐用户邮箱或换一个范围。",
            "confirm_required": False,
            "data": {"args": prepared, "missing_email_count": without_email},
        }

    recipient_ids = [item.id for item in recipients]
    preview = "、".join(_user_email_label(item) for item in recipients[:5])
    if len(recipients) > 5:
        preview += f" 等 {len(recipients)} 人"
    summary = (
        "请确认是否群发邮件：\n"
        f"- 范围：{_scope_label(prepared['recipient_scope'])}\n"
        f"- 可发送人数：{len(recipients)}\n"
        f"- 缺少邮箱人数：{without_email}\n"
        f"- 收件预览：{preview}\n"
        f"- 主题：{prepared.get('subject')}\n"
        f"- 正文：{str(prepared.get('body') or '')[:120]}"
    )
    return _pending_action_response(
        user,
        prepared,
        db,
        tool_code="send_bulk_email",
        payload={
            "recipient_scope": prepared["recipient_scope"],
            "recipient_user_ids": recipient_ids,
            "subject": prepared["subject"],
            "body": prepared["body"],
        },
        summary=summary,
        risk="high",
    )


def _send_bulk_email(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_send_bulk_email(user, args, db)

    user_ids = [int(item) for item in (args.get("recipient_user_ids") or [])]
    recipients = db.query(User).filter(User.id.in_(user_ids), User.is_deleted == False).all() if user_ids else []
    sent = 0
    failed = []
    for target in recipients:
        if not target.email:
            failed.append({"id": target.id, "reason": "缺少邮箱"})
            continue
        try:
            email_service.send_email(
                sender=user,
                recipient_email=target.email,
                subject=args["subject"],
                body=args.get("body") or "",
                attachments=None,
                db=db,
            )
            sent += 1
        except Exception as exc:
            failed.append({"id": target.id, "email": target.email, "reason": str(exc)})

    log_agent_operation(
        db,
        user=user,
        tool_code="send_bulk_email",
        module="email",
        action="send",
        target_id=None,
        detail={
            "scope": args.get("recipient_scope"),
            "sent": sent,
            "failed": len(failed),
            "subject": args.get("subject"),
        },
    )
    message = f"群发邮件完成：成功 {sent} 封"
    if failed:
        message += f"，失败 {len(failed)} 封。"
    else:
        message += "。"
    return {"message": message, "data": {"sent": sent, "failed": failed[:20]}}


def _create_pending_payload(user: User, args: dict, tool_code: str, schema_cls, summary: str, db: Session) -> dict:
    pending = create_pending_action(
        db,
        user=user,
        session_id=args.get("_session_id"),
        tool_code=tool_code,
        args=schema_cls.model_dump(mode="json"),
        summary=summary,
        risk="medium",
    )
    return {
        "status": "confirm_required",
        "message": f"{summary}\n\n待确认动作 ID：{pending.id}。回复“确认 {pending.id}”后执行，10 分钟内有效。",
        "confirm_required": True,
        "data": {"pending_action_id": pending.id, "tool": tool_code, "args": schema_cls.model_dump(mode="json"), "summary": summary},
    }


def _prepare_create_department(user: User, args: dict, db: Session) -> dict:
    missing = [label for key, label in {"name": "院系名称", "code": "院系代码"}.items() if not args.get(key)]
    if missing:
        return {"status": "need_more_info", "message": "新增院系还缺少：" + "、".join(missing) + "。", "confirm_required": False, "data": {"missing_fields": missing, "args": args}}
    data = DepartmentCreate(**args)
    summary = f"请确认是否新增院系：\n- 名称：{data.name}\n- 代码：{data.code}\n- 描述：{data.description or '无'}"
    return _create_pending_payload(user, args, "create_department", data, summary, db)


def _create_department(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_department(user, args, db)
    dept = department_service.create_department(DepartmentCreate(**args), db)
    log_agent_operation(db, user=user, tool_code="create_department", module="org", action="create", target_id=dept.id, detail={"target": "department", "department_id": dept.id, "code": dept.code, "name": dept.name})
    return {"message": f"已新增院系：{dept.name}（代码：{dept.code}）。", "data": department_to_dict(dept)}


def _prepare_create_classroom(user: User, args: dict, db: Session) -> dict:
    if not args.get("name"):
        return {"status": "need_more_info", "message": "新增教室还缺少教室名称。", "confirm_required": False, "data": {"missing_fields": ["教室名称"], "args": args}}
    data = ClassroomCreate(**args)
    summary = f"请确认是否新增教室：\n- 名称：{data.name}\n- 楼栋：{data.building or '未设置'}\n- 房间号：{data.room_no or '未设置'}\n- 校区：{data.campus or '未设置'}\n- 容量：{data.capacity}\n- 类型：{data.room_type}"
    return _create_pending_payload(user, args, "create_classroom", data, summary, db)


def _create_classroom(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_classroom(user, args, db)
    classroom = schedule_service.create_classroom(ClassroomCreate(**args), db)
    log_agent_operation(db, user=user, tool_code="create_classroom", module="schedule", action="create", target_id=classroom.id, detail={"target": "classroom", "classroom_id": classroom.id, "name": classroom.name})
    return {"message": f"已新增教室：{classroom.name}。", "data": classroom_to_dict(classroom)}


def _prepare_create_term(user: User, args: dict, db: Session) -> dict:
    for key in ["start_date", "end_date"]:
        if args.get(key):
            parsed = _parse_date(args.get(key))
            if not parsed:
                return {"status": "need_more_info", "message": f"{key} 日期格式建议使用 YYYY-MM-DD。", "confirm_required": False, "data": {"args": args}}
            args[key] = parsed.isoformat()
    required = {"name": "学期名称", "academic_year": "学年", "semester": "学期序号", "start_date": "开始日期", "end_date": "结束日期", "week_count": "教学周数"}
    missing = [label for key, label in required.items() if not args.get(key)]
    if missing:
        return {"status": "need_more_info", "message": "新增学期还缺少：" + "、".join(missing) + "。", "confirm_required": False, "data": {"missing_fields": missing, "args": args}}
    data = TermCreate(**args)
    summary = f"请确认是否新增学期：\n- 名称：{data.name}\n- 学年：{data.academic_year}\n- 学期：第{data.semester}学期\n- 日期：{data.start_date} 至 {data.end_date}\n- 周数：{data.week_count}\n- 当前学期：{'是' if data.is_current else '否'}"
    return _create_pending_payload(user, args, "create_term", data, summary, db)


def _create_term(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_term(user, args, db)
    term = schedule_service.create_term(TermCreate(**args), db)
    log_agent_operation(db, user=user, tool_code="create_term", module="schedule", action="create", target_id=term.id, detail={"target": "term", "term_id": term.id, "name": term.name})
    return {"message": f"已新增学期：{term.name}。", "data": term_to_dict(term)}


def _prepare_create_announcement(user: User, args: dict, db: Session) -> dict:
    if not args.get("title") or not args.get("content"):
        missing = []
        if not args.get("title"):
            missing.append("标题")
        if not args.get("content"):
            missing.append("内容")
        return {"status": "need_more_info", "message": "发布公告还缺少：" + "、".join(missing) + "。", "confirm_required": False, "data": {"missing_fields": missing, "args": args}}
    args.setdefault("type", 1)
    data = AnnouncementCreate(**args)
    summary = f"请确认是否发布公告：\n- 标题：{data.title}\n- 类型：{data.type}\n- 置顶：{'是' if data.is_top else '否'}\n- 状态：{data.status}\n- 内容：{data.content[:100]}"
    return _create_pending_payload(user, args, "create_announcement", data, summary, db)


def _create_announcement(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_announcement(user, args, db)
    ann = announcement_service.create_announcement(AnnouncementCreate(**args), user.id, db)
    log_agent_operation(db, user=user, tool_code="create_announcement", module="announcement", action="create", target_id=ann.id, detail={"target": "announcement", "announcement_id": ann.id, "title": ann.title})
    return {"message": f"已发布公告：{ann.title}。", "data": announcement_to_dict(ann)}


TOOL_TARGETS.update({
    "update_student": {
        "target": "student",
        "label": "学生",
        "module": "people",
        "model": Student,
        "name_attr": "name",
        "code_attr": "student_no",
        "update_schema": StudentUpdate,
        "update_service": student_service.update_student,
        "get_service": student_service.get_student,
        "to_dict": student_to_dict,
        "field_labels": {
            "student_no": "学号",
            "name": "姓名",
            "gender": "性别",
            "id_card": "身份证号",
            "clazz_id": "班级ID",
            "enrollment_date": "入学日期",
            "phone": "手机号",
            "email": "邮箱",
            "status": "状态",
        },
    },
    "delete_student": {
        "target": "student",
        "label": "学生",
        "module": "people",
        "model": Student,
        "name_attr": "name",
        "code_attr": "student_no",
        "get_service": student_service.get_student,
        "delete_service": student_service.delete_student,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_teacher": {
        "target": "teacher",
        "label": "教师",
        "module": "people",
        "model": Teacher,
        "name_attr": "name",
        "code_attr": "employee_no",
        "update_schema": TeacherUpdate,
        "update_service": teacher_service.update_teacher,
        "get_service": teacher_service.get_teacher,
        "to_dict": teacher_to_dict,
        "field_labels": {
            "employee_no": "工号",
            "name": "姓名",
            "gender": "性别",
            "id_card": "身份证号",
            "position": "岗位",
            "title": "职称",
            "department_id": "院系ID",
            "entry_date": "入职日期",
            "phone": "手机号",
            "email": "邮箱",
            "status": "状态",
        },
    },
    "delete_teacher": {
        "target": "teacher",
        "label": "教师",
        "module": "people",
        "model": Teacher,
        "name_attr": "name",
        "code_attr": "employee_no",
        "get_service": teacher_service.get_teacher,
        "delete_service": teacher_service.delete_teacher,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_course": {
        "target": "course",
        "label": "课程",
        "module": "teaching",
        "model": Course,
        "name_attr": "name",
        "code_attr": "code",
        "update_schema": CourseUpdate,
        "update_service": course_service.update_course,
        "get_service": course_service.get_course,
        "to_dict": course_to_dict,
        "field_labels": {
            "name": "课程名称",
            "code": "课程编号",
            "credit": "学分",
            "hours": "学时",
            "course_type": "课程类型",
            "department_id": "院系ID",
            "teacher_id": "教师ID",
            "description": "简介",
            "status": "状态",
        },
    },
    "delete_course": {
        "target": "course",
        "label": "课程",
        "module": "teaching",
        "model": Course,
        "name_attr": "name",
        "code_attr": "code",
        "get_service": course_service.get_course,
        "delete_service": course_service.delete_course,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_class": {
        "target": "class",
        "label": "班级",
        "module": "org",
        "model": Clazz,
        "name_attr": "name",
        "code_attr": "code",
        "update_schema": ClazzUpdate,
        "update_service": clazz_service.update_clazz,
        "get_service": clazz_service.get_clazz,
        "to_dict": clazz_to_dict,
        "field_labels": {
            "name": "班级名称",
            "code": "班级编号",
            "department_id": "院系ID",
            "grade": "年级",
            "counselor_id": "班主任/辅导员ID",
            "status": "状态",
        },
    },
    "delete_class": {
        "target": "class",
        "label": "班级",
        "module": "org",
        "model": Clazz,
        "name_attr": "name",
        "code_attr": "code",
        "get_service": clazz_service.get_clazz,
        "delete_service": clazz_service.delete_clazz,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_department": {
        "target": "department",
        "label": "院系",
        "module": "org",
        "model": Department,
        "name_attr": "name",
        "code_attr": "code",
        "update_schema": DepartmentUpdate,
        "update_service": department_service.update_department,
        "get_service": department_service.get_department,
        "to_dict": department_to_dict,
        "field_labels": {
            "name": "院系名称",
            "code": "院系代码",
            "description": "描述",
            "status": "状态",
        },
    },
    "delete_department": {
        "target": "department",
        "label": "院系",
        "module": "org",
        "model": Department,
        "name_attr": "name",
        "code_attr": "code",
        "get_service": department_service.get_department,
        "delete_service": department_service.delete_department,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_classroom": {
        "target": "classroom",
        "label": "教室",
        "module": "schedule",
        "model": Classroom,
        "name_attr": "name",
        "code_attr": "room_no",
        "update_schema": ClassroomUpdate,
        "update_service": schedule_service.update_classroom,
        "get_service": schedule_service.get_classroom,
        "to_dict": classroom_to_dict,
        "field_labels": {
            "name": "教室名称",
            "building": "楼栋",
            "room_no": "房间号",
            "campus": "校区",
            "capacity": "容量",
            "room_type": "类型",
            "status": "状态",
            "remark": "备注",
        },
    },
    "delete_classroom": {
        "target": "classroom",
        "label": "教室",
        "module": "schedule",
        "model": Classroom,
        "name_attr": "name",
        "code_attr": "room_no",
        "get_service": schedule_service.get_classroom,
        "delete_service": schedule_service.delete_classroom,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_term": {
        "target": "term",
        "label": "学期",
        "module": "schedule",
        "model": Term,
        "name_attr": "name",
        "code_attr": "academic_year",
        "update_schema": TermUpdate,
        "update_service": schedule_service.update_term,
        "get_service": schedule_service.get_term,
        "to_dict": term_to_dict,
        "field_labels": {
            "name": "学期名称",
            "academic_year": "学年",
            "semester": "学期序号",
            "start_date": "开始日期",
            "end_date": "结束日期",
            "week_count": "教学周数",
            "is_current": "当前学期",
            "status": "状态",
            "remark": "备注",
        },
    },
    "delete_term": {
        "target": "term",
        "label": "学期",
        "module": "schedule",
        "model": Term,
        "name_attr": "name",
        "code_attr": "academic_year",
        "get_service": schedule_service.get_term,
        "delete_service": schedule_service.delete_term,
        "delete_word": "停用",
        "field_labels": {},
    },
    "update_announcement": {
        "target": "announcement",
        "label": "公告",
        "module": "announcement",
        "model": Announcement,
        "name_attr": "title",
        "update_schema": AnnouncementUpdate,
        "update_service": announcement_service.update_announcement,
        "get_service": announcement_service.get_announcement,
        "to_dict": announcement_to_dict,
        "field_labels": {
            "title": "标题",
            "content": "内容",
            "type": "类型",
            "is_top": "置顶",
            "status": "状态",
        },
    },
    "delete_announcement": {
        "target": "announcement",
        "label": "公告",
        "module": "announcement",
        "model": Announcement,
        "name_attr": "title",
        "get_service": announcement_service.get_announcement,
        "delete_service": announcement_service.delete_announcement,
        "delete_word": "删除",
        "field_labels": {},
    },
})


def _user_role_names(user: User) -> list[str]:
    names = []
    for item in getattr(user, "user_roles", []) or []:
        role = getattr(item, "role", None)
        if role:
            names.append(getattr(role, "name", "") or getattr(role, "code", ""))
    return [name for name in names if name]


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


def _teacher_summary(teacher: Teacher | None) -> str:
    if not teacher:
        return "未安排"
    dept = getattr(getattr(teacher, "department", None), "name", "") or "未设置院系"
    title = f"，职称：{teacher.title}" if getattr(teacher, "title", None) else ""
    return f"{teacher.name}（工号：{teacher.employee_no}，岗位：{teacher.position or '未设置'}{title}，院系：{dept}）"


def _query_my_profile(user: User, args: dict, db: Session) -> dict:
    student = _current_student(user, db)
    teacher = _current_teacher(user, db)
    role_names = _user_role_names(user)
    lines = [
        f"你当前登录的是：{user.real_name or user.username}。",
        f"登录名：{user.username}",
        f"系统角色：{'、'.join(role_names) if role_names else '未分配角色'}",
    ]
    data: dict[str, Any] = {
        "user": {"id": user.id, "username": user.username, "real_name": user.real_name, "roles": role_names},
        "student": None,
        "teacher": None,
    }

    if student:
        item = student_to_dict(student)
        data["student"] = item
        lines.append("学生档案：")
        lines.append(f"- 姓名：{student.name}")
        lines.append(f"- 学号：{student.student_no}")
        lines.append(f"- 班级：{item.get('clazz_name') or '未分配'}")
        lines.append(f"- 院系：{item.get('department_name') or '未设置'}")
        lines.append(f"- 状态：{STUDENT_STATUS_TEXT.get(student.status, student.status)}")

    if teacher:
        item = teacher_to_dict(teacher)
        data["teacher"] = item
        lines.append("教职工档案：")
        lines.append(f"- 姓名：{teacher.name}")
        lines.append(f"- 工号：{teacher.employee_no}")
        lines.append(f"- 岗位：{teacher.position or '未设置'}")
        lines.append(f"- 职称：{teacher.title or '未设置'}")
        lines.append(f"- 院系：{item.get('department_name') or '未设置'}")
        lines.append(f"- 状态：{TEACHER_STATUS_TEXT.get(teacher.status, teacher.status)}")

    if not student and not teacher:
        lines.append("该账号没有关联学生或教职工档案，因此没有班级、学号、工号或任课信息。")

    return {"message": "\n".join(lines), "data": data}


def _student_course_schedules(student: Student, db: Session, keyword: str | None = None):
    q = db.query(CourseSchedule).options(
        joinedload(CourseSchedule.term),
        joinedload(CourseSchedule.course).joinedload(Course.department),
        joinedload(CourseSchedule.teacher).joinedload(Teacher.department),
        joinedload(CourseSchedule.classroom),
        joinedload(CourseSchedule.clazz),
    ).filter(
        CourseSchedule.clazz_id == student.clazz_id,
        CourseSchedule.is_deleted == False,
        CourseSchedule.status == 1,
    )
    if keyword:
        q = q.join(Course, CourseSchedule.course_id == Course.id).filter(Course.name.contains(keyword))
    return q.order_by(CourseSchedule.weekday, CourseSchedule.start_section).all()


def _student_selected_courses(student: Student, db: Session, keyword: str | None = None):
    q = db.query(StudentCourse).options(
        joinedload(StudentCourse.course).joinedload(Course.teacher).joinedload(Teacher.department),
        joinedload(StudentCourse.course).joinedload(Course.department),
    ).filter(StudentCourse.student_id == student.id)
    if keyword:
        q = q.join(Course, StudentCourse.course_id == Course.id).filter(Course.name.contains(keyword))
    return q.all()


def _query_my_teachers(user: User, args: dict, db: Session) -> dict:
    student = _current_student(user, db)
    teacher = _current_teacher(user, db)
    if not student:
        if teacher:
            return {
                "message": "当前账号是教职工账号，没有“我的任课老师”这一学生视角信息。你可以问“我教哪些课”。",
                "data": {"teacher": teacher_to_dict(teacher), "items": []},
            }
        return {
            "message": "当前账号没有关联学生档案，无法查询“我的老师”。",
            "data": {"items": []},
        }

    scope = args.get("teacher_scope") or "all"
    course_keyword = (args.get("course_keyword") or "").strip() or None
    lines = []
    data: dict[str, Any] = {"student": student_to_dict(student), "counselor": None, "course_teachers": []}

    if scope in {"all", "counselor"}:
        counselor = getattr(getattr(student, "clazz", None), "counselor", None)
        if counselor:
            data["counselor"] = teacher_to_dict(counselor)
            lines.append(f"你的班主任/辅导员是：{_teacher_summary(counselor)}")
        else:
            lines.append("你的班级暂未设置班主任/辅导员。")

    if scope in {"all", "course"}:
        schedules = _student_course_schedules(student, db, course_keyword)
        seen = set()
        course_lines = []
        for schedule in schedules:
            course = getattr(schedule, "course", None)
            teacher_obj = getattr(schedule, "teacher", None)
            if not course or not teacher_obj:
                continue
            key = (course.id, teacher_obj.id)
            if key in seen:
                continue
            seen.add(key)
            item = {
                "course_id": course.id,
                "course_name": course.name,
                "teacher": teacher_to_dict(teacher_obj),
            }
            data["course_teachers"].append(item)
            course_lines.append(f"- {course.name}：{_teacher_summary(teacher_obj)}")
        if course_keyword and not course_lines:
            lines.append(f"没有找到课程“{course_keyword}”对应的任课教师。")
        elif course_lines:
            lines.append("你的任课教师有：")
            lines.extend(course_lines[:20])
        elif scope == "course":
            lines.append("暂未查询到你的任课教师。")

    return {"message": "\n".join(lines), "data": data}


def _query_my_courses(user: User, args: dict, db: Session) -> dict:
    student = _current_student(user, db)
    teacher = _current_teacher(user, db)
    keyword = (args.get("keyword") or "").strip() or None
    if student:
        schedules = _student_course_schedules(student, db, keyword)
        items = [course_schedule_to_dict(item) for item in schedules]
        if not items:
            return {"message": "暂未查询到你的课程。", "data": {"items": [], "total": 0}}
        seen = set()
        lines = [f"查询到你相关的 {len(items)} 条课程安排，先按课程汇总："]
        for item in items:
            key = item.get("course_id")
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- {item.get('course_name') or '未知课程'}，教师：{item.get('teacher_name') or '未安排'}，"
                f"班级：{item.get('clazz_name') or '未设置'}"
            )
        return {"message": "\n".join(lines[:21]), "data": {"items": items, "total": len(items)}}

    if teacher:
        q = db.query(Course).options(joinedload(Course.department), joinedload(Course.teacher)).filter(
            Course.teacher_id == teacher.id,
            Course.is_deleted == False,
        )
        if keyword:
            q = q.filter(Course.name.contains(keyword))
        courses = q.order_by(Course.id.desc()).limit(50).all()
        items = [course_to_dict(item) for item in courses]
        if not items:
            return {"message": "暂未查询到你负责的课程。", "data": {"items": [], "total": 0}}
        lines = [f"你负责的课程有 {len(items)} 门："]
        for item in items[:20]:
            lines.append(f"- {item.get('name')}（编号：{item.get('code')}），学分：{item.get('credit')}，院系：{item.get('department_name') or '未设置'}")
        return {"message": "\n".join(lines), "data": {"items": items, "total": len(items)}}

    return {
        "message": "当前账号没有关联学生或教职工档案，无法查询“我的课程”。",
        "data": {"items": [], "total": 0},
    }


def _query_my_schedule(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=10)
    q = schedule_service.list_my_course_schedules(user, params, db, args.get("term_id"))
    if args.get("weekday"):
        q = q.filter_by(weekday=int(args["weekday"]))
    result = paginate(q, params)
    items = [course_schedule_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {
            "message": "没有查询到你的课表记录。",
            "data": {"total": result.get("total", 0), "items": []},
        }

    lines = [f"查询到 {result.get('total', len(items))} 条课表，先显示 {len(items)} 条："]
    for item in items:
        weekday = WEEKDAY_NAMES.get(item.get("weekday"), f"周{item.get('weekday')}")
        sections = f"{item.get('start_section')}-{item.get('end_section')}节"
        weeks = f"第{item.get('start_week')}-{item.get('end_week')}周"
        course_name = item.get("course_name") or "未知课程"
        teacher_name = item.get("teacher_name") or "未安排"
        room = item.get("classroom_name") or "未安排教室"
        lines.append(
            f"- {weekday} {sections}，{weeks}：{course_name}，"
            f"教师：{teacher_name}，地点：{room}"
        )

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_my_attendance(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = attendance_service.list_my_attendance(
        user=user,
        params=params,
        db=db,
        status=args.get("status"),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
    )
    result = paginate(q, params)
    items = [attendance_record_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {
            "message": "没有查询到你的考勤记录。",
            "data": {"total": result.get("total", 0), "items": []},
        }

    lines = [f"查询到 {result.get('total', len(items))} 条考勤记录，先显示 {len(items)} 条："]
    for item in items:
        status = STATUS_TEXT.get(item.get("status"), item.get("status") or "未知")
        period = item.get("period_type") or "day"
        remark = f"，备注：{item.get('remark')}" if item.get("remark") else ""
        lines.append(f"- {_format_date(item.get('attendance_date'))}，时段：{period}，状态：{status}{remark}")

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_my_leave(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = leave_service.list_my_leave_requests(
        user=user,
        params=params,
        db=db,
        status=args.get("status"),
        applicant_type=args.get("applicant_type"),
        leave_type=args.get("leave_type"),
    )
    result = paginate(q, params)
    items = [leave_request_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {
            "message": "没有查询到你的请假申请。",
            "data": {"total": result.get("total", 0), "items": []},
        }

    lines = [f"查询到 {result.get('total', len(items))} 条请假申请，先显示 {len(items)} 条："]
    for item in items:
        status = STATUS_TEXT.get(item.get("status"), item.get("status") or "未知")
        lines.append(
            f"- {item.get('leave_type', '请假')}：{_format_datetime(item.get('start_time'))} 至 "
            f"{_format_datetime(item.get('end_time'))}，状态：{status}，原因：{item.get('reason', '')}"
        )

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _leave_type_label(value: str | None) -> str:
    return {
        "sick": "病假",
        "personal": "事假",
        "official": "公假",
        "funeral": "丧假",
        "marriage": "婚假",
        "maternity": "产假",
        "other": "其他",
    }.get(value or "", value or "未设置")


def _prepare_create_leave_request(user: User, args: dict, db: Session) -> dict:
    prepared = {k: v for k, v in dict(args or {}).items() if not str(k).startswith("_")}
    student_profile = db.query(Student.id).filter(Student.user_id == user.id, Student.is_deleted == False).first()
    teacher_profile = db.query(Teacher.id).filter(Teacher.user_id == user.id, Teacher.is_deleted == False).first()
    if not prepared.get("applicant_type"):
        if student_profile and not teacher_profile:
            prepared["applicant_type"] = "student"
        elif teacher_profile and not student_profile:
            prepared["applicant_type"] = "teacher"
        elif not student_profile and not teacher_profile:
            return {
                "status": "need_more_info",
                "message": (
                    "当前账号没有关联学生或教职工档案，不能作为请假申请人提交“自己的请假”。"
                    "如果你是管理员，请使用学生或教师测试账号提交请假，再用管理员账号审核。"
                ),
                "confirm_required": False,
                "data": {"missing_fields": ["申请人身份"], "args": prepared},
            }
        else:
            return {
                "status": "need_more_info",
                "message": "当前账号同时关联学生和教职工档案，请补充请假身份：学生请假或教职工请假。",
                "confirm_required": False,
                "data": {"missing_fields": ["申请人身份"], "args": prepared},
            }
    required = {
        "leave_type": "请假类型",
        "start_time": "开始时间",
        "end_time": "结束时间",
        "reason": "请假原因",
    }
    missing = [label for key, label in required.items() if not prepared.get(key)]
    if missing:
        return {
            "status": "need_more_info",
            "message": (
                "可以，我来帮你提交请假申请。还需要补充："
                + "、".join(missing)
                + "。你可以直接说：明天上午病假，原因是发烧。"
            ),
            "confirm_required": False,
            "data": {"missing_fields": missing, "args": prepared},
        }
    try:
        data = LeaveRequestCreate(**prepared)
    except Exception as exc:
        return {
            "status": "need_more_info",
            "message": f"请假信息还需要调整：{exc}",
            "confirm_required": False,
            "data": {"args": prepared},
        }
    summary = (
        "请确认是否提交请假申请：\n"
        f"- 类型：{_leave_type_label(data.leave_type)}\n"
        f"- 时间：{_format_datetime(data.start_time)} 至 {_format_datetime(data.end_time)}\n"
        f"- 原因：{data.reason}"
    )
    if data.destination:
        summary += f"\n- 去向：{data.destination}"
    return _pending_action_response(
        user,
        args,
        db,
        tool_code="create_leave_request",
        payload=data.model_dump(mode="json"),
        summary=summary,
        risk="medium",
    )


def _create_leave_request(user: User, args: dict, db: Session) -> dict:
    if args.get("_prepare"):
        return _prepare_create_leave_request(user, args, db)
    req = leave_service.create_leave_request(user, LeaveRequestCreate(**args), db)
    log_agent_operation(
        db,
        user=user,
        tool_code="create_leave_request",
        module="leave",
        action="create",
        target_id=req.id,
        detail={"leave_request_id": req.id, "leave_type": req.leave_type, "status": req.status},
    )
    return {
        "message": (
            f"已提交请假申请：{_leave_type_label(req.leave_type)}，"
            f"{_format_datetime(req.start_time)} 至 {_format_datetime(req.end_time)}，当前状态：待审批。"
        ),
        "data": leave_request_to_dict(req),
    }


def _query_announcements(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=6)
    q = announcement_service.list_announcements(params, db)
    result = paginate(q, params)
    items = []
    for ann in result.get("items", []):
        content = ann.content or ""
        items.append({
            "id": ann.id,
            "title": ann.title,
            "summary": content[:60],
            "status": ann.status,
            "is_top": ann.is_top,
            "published_at": _format_datetime(ann.published_at),
            "created_at": _format_datetime(ann.created_at),
        })

    if not items:
        return {"message": "没有查询到公告。", "data": {"total": result.get("total", 0), "items": []}}

    lines = [f"查询到 {result.get('total', len(items))} 条公告，先显示 {len(items)} 条："]
    for item in items:
        top = "置顶，" if item.get("is_top") else ""
        published = item.get("published_at") or item.get("created_at")
        summary = f"：{item.get('summary')}" if item.get("summary") else ""
        lines.append(f"- {top}{item.get('title')}（{published}）{summary}")

    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_student(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = student_service.list_students(params, db, clazz_id=args.get("clazz_id"))
    result = paginate(q, params)
    items = [student_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {"message": "没有查询到匹配的学生。", "data": {"total": result.get("total", 0), "items": []}}

    requested_field = args.get("requested_field")
    if requested_field and len(items) == 1:
        label, value = _student_field_text(items[0], requested_field)
        return {
            "message": f"{items[0].get('name')}（学号：{items[0].get('student_no')}）的{label}是：{value}。",
            "data": {"total": result.get("total", 0), "items": items, "requested_field": requested_field},
        }

    lines = [f"查询到 {result.get('total', len(items))} 名学生，先显示 {len(items)} 名："]
    for item in items:
        status = STUDENT_STATUS_TEXT.get(item.get("status"), item.get("status"))
        gender = "男" if item.get("gender") == 1 else "女" if item.get("gender") == 2 else "未设置"
        lines.append(
            f"- {item.get('name')}（学号：{item.get('student_no')}），"
            f"性别：{gender}，"
            f"班级：{item.get('clazz_name') or '未分配'}，"
            f"院系：{item.get('department_name') or '未设置'}，"
            f"状态：{status or item.get('status')}"
        )
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_teacher(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = teacher_service.list_teachers(params, db, department_id=args.get("department_id"))
    result = paginate(q, params)
    items = [teacher_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {"message": "没有查询到匹配的教师。", "data": {"total": result.get("total", 0), "items": []}}

    requested_field = args.get("requested_field")
    if requested_field and len(items) == 1:
        label, value = _teacher_field_text(items[0], requested_field)
        return {
            "message": f"{items[0].get('name')}（工号：{items[0].get('employee_no')}）的{label}是：{value}。",
            "data": {"total": result.get("total", 0), "items": items, "requested_field": requested_field},
        }

    lines = [f"查询到 {result.get('total', len(items))} 名教师，先显示 {len(items)} 名："]
    for item in items:
        status = TEACHER_STATUS_TEXT.get(item.get("status"), item.get("status"))
        lines.append(
            f"- {item.get('name')}（工号：{item.get('employee_no')}），"
            f"院系：{item.get('department_name') or '未设置'}，"
            f"岗位：{item.get('position') or '未设置'}，"
            f"职称：{item.get('title') or '未设置'}，"
            f"状态：{status}"
        )
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_course(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = course_service.list_courses(params, db, department_id=args.get("department_id"))
    result = paginate(q, params)
    items = [course_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {"message": "没有查询到匹配的课程。", "data": {"total": result.get("total", 0), "items": []}}

    lines = [f"查询到 {result.get('total', len(items))} 门课程，先显示 {len(items)} 门："]
    for item in items:
        status = COMMON_STATUS_TEXT.get(item.get("status"), item.get("status"))
        lines.append(
            f"- {item.get('name')}（编号：{item.get('code')}），"
            f"学分：{item.get('credit')}，学时：{item.get('hours')}，"
            f"院系：{item.get('department_name') or '未设置'}，"
            f"教师：{item.get('teacher_name') or '未安排'}，"
            f"状态：{status}"
        )
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_score(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = db.query(Score).options(
        joinedload(Score.student),
        joinedload(Score.course),
        joinedload(Score.exam),
    ).filter(Score.is_deleted == False)

    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        q = q.join(Student, Score.student_id == Student.id).join(Course, Score.course_id == Course.id).join(Exam, Score.exam_id == Exam.id)
        q = q.filter(or_(Student.name.like(like), Student.student_no.like(like), Course.name.like(like), Exam.name.like(like)))

    if args.get("student_id"):
        q = q.filter(Score.student_id == int(args["student_id"]))
    if args.get("course_id"):
        q = q.filter(Score.course_id == int(args["course_id"]))
    if args.get("exam_id"):
        q = q.filter(Score.exam_id == int(args["exam_id"]))

    result = paginate(q.order_by(Score.id.desc()), params)
    items = [score_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {"message": "没有查询到匹配的成绩记录。", "data": {"total": result.get("total", 0), "items": []}}

    lines = [f"查询到 {result.get('total', len(items))} 条成绩记录，先显示 {len(items)} 条："]
    for item in items:
        score_text = "未录入" if item.get("score") is None else f"{item.get('score')}分"
        rank_text = f"，班级排名：{item.get('rank_in_class')}" if item.get("rank_in_class") else ""
        lines.append(
            f"- {item.get('student_name') or '未知学生'}（学号：{item.get('student_no') or '未知'}），"
            f"{item.get('course_name') or '未知课程'} / {item.get('exam_name') or '未知考试'}："
            f"{score_text}，等级：{item.get('grade') or '未评定'}{rank_text}"
        )
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def _query_class(user: User, args: dict, db: Session) -> dict:
    params = _page_params(args, default_size=8)
    q = clazz_service.list_clazzes(params, db, department_id=args.get("department_id"))
    result = paginate(q, params)
    items = [clazz_to_dict(item) for item in result.get("items", [])]

    if not items:
        return {"message": "没有查询到匹配的班级。", "data": {"total": result.get("total", 0), "items": []}}

    lines = [f"查询到 {result.get('total', len(items))} 个班级，先显示 {len(items)} 个："]
    for item in items:
        status = COMMON_STATUS_TEXT.get(item.get("status"), item.get("status"))
        lines.append(
            f"- {item.get('name')}（编号：{item.get('code')}），"
            f"年级：{item.get('grade') or '未设置'}，"
            f"院系：{item.get('department_name') or '未设置'}，"
            f"班主任/辅导员：{item.get('counselor_name') or '未安排'}，"
            f"状态：{status}"
        )
    return {"message": "\n".join(lines), "data": {"total": result.get("total", 0), "items": items}}


def normalize_args(tool_code: str, message: str, args: dict | None = None) -> dict:
    normalized = dict(args or {})
    text = message or ""
    if tool_code == "send_email" and normalized.get("recipient_keyword"):
        normalized["recipient_keyword"] = _clean_recipient_keyword(normalized.get("recipient_keyword"))
    if tool_code == "query_my_schedule":
        today = date.today()
        if "今天" in text:
            normalized["weekday"] = today.isoweekday()
        elif "明天" in text:
            normalized["weekday"] = (today + timedelta(days=1)).isoweekday()
    if "待审批" in text or "待审核" in text:
        normalized["status"] = "pending"
    elif "已通过" in text or "通过" in text:
        normalized["status"] = "approved"
    elif "驳回" in text:
        normalized["status"] = "rejected"
    elif "请假" in text and tool_code == "query_my_attendance":
        normalized["status"] = "leave"
    if tool_code in {"query_student", "query_teacher", "query_course", "query_score", "query_class"}:
        if any(word in text for word in ["继续", "下一页", "下页", "显示更多", "更多", "全部显示", "显示全部", "都显示", "完整显示", "显示所有", "能显示全部", "可以显示全部"]):
            return normalized

        requested_field = _teacher_requested_field(text) if tool_code == "query_teacher" else _student_requested_field(text)
        if requested_field and tool_code == "query_student":
            normalized["requested_field"] = requested_field
        if requested_field and tool_code == "query_teacher":
            normalized["requested_field"] = requested_field

        student_no_match = re.search(r"[Ss]\d{6,}", text)
        if student_no_match and tool_code == "query_student":
            normalized["keyword"] = student_no_match.group(0).upper()
            return normalized

        teacher_no_match = re.search(r"[Tt]\d{6,}", text)
        if teacher_no_match and tool_code == "query_teacher":
            normalized["keyword"] = teacher_no_match.group(0).upper()
            return normalized

        existing_keyword = (normalized.get("keyword") or "").strip()
        if existing_keyword and any(word in text for word in ["这个", "这个人", "这个学生", "这名学生", "该学生", "他", "她", "TA", "ta"]):
            return normalized
        keyword = text
        cleanup_words = [
            "帮我",
            "请",
            "查询一下",
            "查一下",
            "查询",
            "查找",
            "查",
            "搜索",
            "看一下",
            "看看",
            "学生",
            "教师",
            "老师",
            "教职工",
            "课程",
            "成绩",
            "分数",
            "考试",
            "班级",
            "信息",
            "资料",
            "列表",
            "显示",
            "显示全部",
            "全部显示",
            "都显示",
            "完整显示",
            "继续",
            "下一页",
            "下页",
            "更多",
            "显示更多",
            "所有",
            "全部",
            "全体",
            "全部的",
            "所有的",
            "的",
            "这个人",
            "这个学生",
            "这名学生",
            "该学生",
            "这个",
            "这个人的",
            "这个学生的",
            "这名学生的",
            "该学生的",
            "他的",
            "她的",
            "他",
            "她",
            "这个人性别是啥",
            "性别是啥",
            "是啥",
            "是什么",
            "多少",
        ]
        for word in cleanup_words:
            keyword = keyword.replace(word, " ")
        keyword = " ".join(keyword.split()).strip(" ，,。")
        if keyword:
            normalized["keyword"] = keyword
        elif not existing_keyword:
            normalized.pop("keyword", None)
    return normalized


TOOL_HANDLERS = {
    "query_my_profile": _query_my_profile,
    "query_my_teachers": _query_my_teachers,
    "query_my_courses": _query_my_courses,
    "query_my_schedule": _query_my_schedule,
    "query_my_attendance": _query_my_attendance,
    "query_my_leave": _query_my_leave,
    "create_leave_request": _create_leave_request,
    "query_announcements": _query_announcements,
    "query_weather": _query_weather,
    "send_email": _send_email,
    "send_bulk_email": _send_bulk_email,
    "query_student": _query_student,
    "create_student": _create_student,
    "update_student": lambda user, args, db: _update_object(user, args, db, "update_student"),
    "delete_student": lambda user, args, db: _delete_object(user, args, db, "delete_student"),
    "query_teacher": _query_teacher,
    "create_teacher": _create_teacher,
    "update_teacher": lambda user, args, db: _update_object(user, args, db, "update_teacher"),
    "delete_teacher": lambda user, args, db: _delete_object(user, args, db, "delete_teacher"),
    "query_course": _query_course,
    "query_score": _query_score,
    "create_course": _create_course,
    "update_course": lambda user, args, db: _update_object(user, args, db, "update_course"),
    "delete_course": lambda user, args, db: _delete_object(user, args, db, "delete_course"),
    "query_class": _query_class,
    "create_class": _create_class,
    "update_class": lambda user, args, db: _update_object(user, args, db, "update_class"),
    "delete_class": lambda user, args, db: _delete_object(user, args, db, "delete_class"),
    "query_department": _query_department,
    "create_department": _create_department,
    "update_department": lambda user, args, db: _update_object(user, args, db, "update_department"),
    "delete_department": lambda user, args, db: _delete_object(user, args, db, "delete_department"),
    "query_classroom": _query_classroom,
    "create_classroom": _create_classroom,
    "update_classroom": lambda user, args, db: _update_object(user, args, db, "update_classroom"),
    "delete_classroom": lambda user, args, db: _delete_object(user, args, db, "delete_classroom"),
    "query_term": _query_term,
    "create_term": _create_term,
    "update_term": lambda user, args, db: _update_object(user, args, db, "update_term"),
    "delete_term": lambda user, args, db: _delete_object(user, args, db, "delete_term"),
    "create_announcement": _create_announcement,
    "update_announcement": lambda user, args, db: _update_object(user, args, db, "update_announcement"),
    "delete_announcement": lambda user, args, db: _delete_object(user, args, db, "delete_announcement"),
}


def execute_registered_tool(tool_code: str, user: User, args: dict, db: Session) -> dict | None:
    handler = TOOL_HANDLERS.get(tool_code)
    if not handler:
        return None
    return handler(user, args or {}, db)
