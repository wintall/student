"""
ORM 实体 → 前端可读字典的统一映射工具
根据真实模型字段：User/Teacher/Student/Department/Clazz/Course/Exam/Score/Announcement/EmailMessage
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date


# ============================================================
# 通用辅助函数
# ============================================================

def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _date_to_year(d: Optional[date]) -> Optional[str]:
    if not d:
        return None
    return str(d.year)


def _format_dt(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(dt, date):
        return dt.strftime("%Y-%m-%d")
    return str(dt)


# ============================================================
# User 实体映射
# ============================================================

def user_to_dict(u) -> Optional[Dict[str, Any]]:
    if not u:
        return None
    try:
        role_names = []
        user_roles = getattr(u, "user_roles", []) or []
        for ur in user_roles:
            role = getattr(ur, "role", None)
            if role:
                role_names.append(getattr(role, "name", ""))
        return {
            "id": u.id,
            "username": getattr(u, "username", ""),
            "real_name": getattr(u, "real_name", ""),
            "phone": getattr(u, "phone", ""),
            "email": getattr(u, "email", ""),
            "avatar": getattr(u, "avatar", ""),
            "status": getattr(u, "status", 1),
            "role_names": role_names,
            "created_at": _format_dt(getattr(u, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(u, "id", None), "username": getattr(u, "username", "")}


# ============================================================
# Department 实体映射
# ============================================================

def department_to_dict(d) -> Optional[Dict[str, Any]]:
    if not d:
        return None
    try:
        return {
            "id": d.id,
            "name": getattr(d, "name", ""),
            "code": getattr(d, "code", ""),
            "description": getattr(d, "description", ""),
            "status": getattr(d, "status", 1),
            "created_at": _format_dt(getattr(d, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(d, "id", None), "name": getattr(d, "name", "")}


# ============================================================
# Clazz 实体映射
# ============================================================

def clazz_to_dict(c) -> Optional[Dict[str, Any]]:
    if not c:
        return None
    try:
        dept = getattr(c, "department", None)
        counselor = getattr(c, "counselor", None)
        return {
            "id": c.id,
            "name": getattr(c, "name", ""),
            "code": getattr(c, "code", ""),
            "department_id": getattr(c, "department_id", None),
            "department": {"id": getattr(dept, "id", None), "name": getattr(dept, "name", "")} if dept else None,
            "department_name": getattr(dept, "name", "") if dept else "",
            "grade": getattr(c, "grade", ""),
            "counselor_id": getattr(c, "counselor_id", None),
            "counselor_name": getattr(counselor, "name", "") if counselor else "",
            "status": getattr(c, "status", 1),
            "created_at": _format_dt(getattr(c, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(c, "id", None), "name": getattr(c, "name", "")}


# ============================================================
# Teacher 实体映射
# ============================================================

def teacher_to_dict(t) -> Optional[Dict[str, Any]]:
    if not t:
        return None
    try:
        user = getattr(t, "user", None)
        dept = getattr(t, "department", None)
        return {
            "id": t.id,
            "user_id": getattr(t, "user_id", None),
            "employee_no": getattr(t, "employee_no", ""),
            "name": getattr(t, "name", ""),
            "gender": getattr(t, "gender", 1),
            "position": getattr(t, "position", ""),
            "title": getattr(t, "title", ""),
            "department_id": getattr(t, "department_id", None),
            "department": {"id": getattr(dept, "id", None), "name": getattr(dept, "name", "")} if dept else None,
            "department_name": getattr(dept, "name", "") if dept else "",
            "entry_date": _format_dt(getattr(t, "entry_date", None)),
            "phone": getattr(user, "phone", "") if user else "",
            "email": getattr(user, "email", "") if user else "",
            "username": getattr(user, "username", "") if user else "",
            "status": getattr(t, "status", 1),
            "created_at": _format_dt(getattr(t, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(t, "id", None), "name": getattr(t, "name", "")}


# ============================================================
# Student 实体映射
# ============================================================

def student_to_dict(s) -> Optional[Dict[str, Any]]:
    if not s:
        return None
    try:
        user = getattr(s, "user", None)
        clazz = getattr(s, "clazz", None)
        department = getattr(clazz, "department", None) if clazz else None
        clazz_dict = {"id": getattr(clazz, "id", None), "name": getattr(clazz, "name", "")} if clazz else None
        dept_dict = {"id": getattr(department, "id", None), "name": getattr(department, "name", "")} if department else None
        return {
            "id": s.id,
            "user_id": getattr(s, "user_id", None),
            "student_no": getattr(s, "student_no", ""),
            "name": getattr(s, "name", ""),
            "gender": getattr(s, "gender", 1),
            "phone": getattr(user, "phone", "") if user else "",
            "email": getattr(user, "email", "") if user else "",
            "username": getattr(user, "username", "") if user else "",
            "clazz_id": getattr(s, "clazz_id", None),
            "clazz": clazz_dict,
            "clazz_name": getattr(clazz, "name", "") if clazz else "",
            "department": dept_dict,
            "department_name": getattr(department, "name", "") if department else "",
            "enrollment_date": _format_dt(getattr(s, "enrollment_date", None)),
            "status": getattr(s, "status", 1),
            "created_at": _format_dt(getattr(s, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(s, "id", None), "name": getattr(s, "name", "")}


# ============================================================
# Course 实体映射
# ============================================================

def course_to_dict(c) -> Optional[Dict[str, Any]]:
    if not c:
        return None
    try:
        teacher = getattr(c, "teacher", None)
        dept = getattr(c, "department", None)
        return {
            "id": c.id,
            "name": getattr(c, "name", ""),
            "code": getattr(c, "code", ""),
            "credit": getattr(c, "credit", 0),
            "hours": getattr(c, "hours", 0),
            "course_type": getattr(c, "course_type", 1),
            "department_id": getattr(c, "department_id", None),
            "department_name": getattr(dept, "name", "") if dept else "",
            "teacher_id": getattr(c, "teacher_id", None),
            "teacher": {"id": getattr(teacher, "id", None), "name": getattr(teacher, "name", "")} if teacher else None,
            "teacher_name": getattr(teacher, "name", "") if teacher else "",
            "description": getattr(c, "description", ""),
            "status": getattr(c, "status", 1),
            "created_at": _format_dt(getattr(c, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(c, "id", None), "name": getattr(c, "name", "")}


# ============================================================
# Exam 实体映射
# ============================================================

def exam_to_dict(e) -> Optional[Dict[str, Any]]:
    if not e:
        return None
    try:
        course = getattr(e, "course", None)
        clazz = getattr(e, "clazz", None)
        return {
            "id": e.id,
            "name": getattr(e, "name", ""),
            "course_id": getattr(e, "course_id", None),
            "course": {"id": getattr(course, "id", None), "name": getattr(course, "name", "")} if course else None,
            "course_name": getattr(course, "name", "") if course else "",
            "exam_type": getattr(e, "exam_type", 1),
            "exam_date": _format_dt(getattr(e, "exam_date", None)),
            "exam_time": getattr(e, "exam_time", ""),
            "location": getattr(e, "location", ""),
            "clazz_id": getattr(e, "clazz_id", None),
            "clazz_name": getattr(clazz, "name", "") if clazz else "",
            "description": getattr(e, "description", ""),
            "status": getattr(e, "status", 1),
            "created_at": _format_dt(getattr(e, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(e, "id", None), "name": getattr(e, "name", "")}


# ============================================================
# Score 实体映射
# ============================================================

def score_to_dict(sc) -> Optional[Dict[str, Any]]:
    if not sc:
        return None
    try:
        student = getattr(sc, "student", None)
        exam = getattr(sc, "exam", None)
        course = getattr(sc, "course", None)
        scorer = getattr(sc, "scorer", None)
        return {
            "id": sc.id,
            "student_id": getattr(sc, "student_id", None),
            "student": {"id": getattr(student, "id", None), "name": getattr(student, "name", "")} if student else None,
            "student_name": getattr(student, "name", "") if student else "",
            "student_no": getattr(student, "student_no", "") if student else "",
            "exam_id": getattr(sc, "exam_id", None),
            "exam": {"id": getattr(exam, "id", None), "name": getattr(exam, "name", "")} if exam else None,
            "exam_name": getattr(exam, "name", "") if exam else "",
            "course_id": getattr(sc, "course_id", None),
            "course_name": getattr(course, "name", "") if course else "",
            "score": float(getattr(sc, "score", 0)) if getattr(sc, "score", None) is not None else None,
            "grade": getattr(sc, "grade", ""),
            "scorer_id": getattr(sc, "scorer_id", None),
            "scorer_name": getattr(scorer, "name", "") if scorer else "",
            "created_at": _format_dt(getattr(sc, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(sc, "id", None), "score": getattr(sc, "score", 0)}


# ============================================================
# Announcement 实体映射
# ============================================================

def announcement_to_dict(a) -> Optional[Dict[str, Any]]:
    if not a:
        return None
    try:
        publisher = getattr(a, "publisher", None)
        return {
            "id": a.id,
            "title": getattr(a, "title", ""),
            "content": getattr(a, "content", ""),
            "type": getattr(a, "type", 1),
            "publisher_id": getattr(a, "publisher_id", None),
            "publisher_name": getattr(publisher, "real_name", "") if publisher else "",
            "publisher": {
                "id": getattr(publisher, "id", None),
                "username": getattr(publisher, "username", ""),
                "real_name": getattr(publisher, "real_name", ""),
            } if publisher else None,
            "is_top": getattr(a, "is_top", False),
            "status": getattr(a, "status", 1),
            "published_at": _format_dt(getattr(a, "published_at", None)),
            "created_at": _format_dt(getattr(a, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(a, "id", None), "title": getattr(a, "title", "")}


# ============================================================
# EmailMessage 实体映射
# ============================================================

def email_to_dict(em) -> Optional[Dict[str, Any]]:
    if not em:
        return None
    try:
        return {
            "id": em.id,
            "sender_id": getattr(em, "sender_id", None),
            "sender_name": getattr(em, "sender_name", ""),
            "sender_email": getattr(em, "sender_email", ""),
            "recipient_email": getattr(em, "recipient_email", ""),
            "recipient_user_id": getattr(em, "recipient_user_id", None),
            "subject": getattr(em, "subject", ""),
            "body": getattr(em, "body", ""),
            "is_external": getattr(em, "is_external", False),
            "status": getattr(em, "status", ""),
            "is_read": getattr(em, "is_read", False),
            "is_deleted_by_sender": getattr(em, "is_deleted_by_sender", False),
            "is_deleted_by_recipient": getattr(em, "is_deleted_by_recipient", False),
            "sent_at": _format_dt(getattr(em, "sent_at", None)),
        }
    except Exception:
        return {"id": getattr(em, "id", None), "subject": getattr(em, "subject", "")}


# ============================================================
# Role 实体映射
# ============================================================

def role_to_dict(r) -> Optional[Dict[str, Any]]:
    if not r:
        return None
    try:
        role_menus = getattr(r, "role_menus", []) or []
        menu_ids = [getattr(rm, "menu_id", None) for rm in role_menus if rm]
        return {
            "id": r.id,
            "code": getattr(r, "code", ""),
            "name": getattr(r, "name", ""),
            "description": getattr(r, "description", ""),
            "menu_ids": menu_ids,
            "menu_count": len(menu_ids),
            "created_at": _format_dt(getattr(r, "created_at", None)),
        }
    except Exception:
        return {"id": getattr(r, "id", None), "name": getattr(r, "name", "")}


# ============================================================
# Menu 实体映射
# ============================================================

def menu_to_dict(m, include_children: bool = False) -> Optional[Dict[str, Any]]:
    if not m:
        return None
    try:
        result = {
            "id": m.id,
            "parent_id": getattr(m, "parent_id", None),
            "name": getattr(m, "name", ""),
            "code": getattr(m, "code", ""),
            "type": getattr(m, "type", 1),
            "path": getattr(m, "path", ""),
            "icon": getattr(m, "icon", ""),
            "sort_order": getattr(m, "sort_order", 0),
            "status": getattr(m, "status", 1),
            "created_at": _format_dt(getattr(m, "created_at", None)),
        }
        if include_children:
            children = getattr(m, "children", []) or []
            if children:
                result["children"] = [menu_to_dict(child, include_children=True) for child in children]
        return result
    except Exception:
        return {"id": getattr(m, "id", None), "name": getattr(m, "name", "")}


# ============================================================
# 列表映射辅助函数
# ============================================================

def map_list(items: List[Any], mapper) -> List[Dict[str, Any]]:
    return [mapper(item) for item in items if item]


# 兼容旧版调用名
map_entities = map_list
