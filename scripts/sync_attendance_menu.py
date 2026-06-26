"""
Sync leave-attendance menus and role permissions.
"""
import sys
from pathlib import Path

import redis as redis_lib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import SessionLocal
from app.models.user import Menu, Role, RoleMenu, UserRole


MENUS = [
    {"name": "请假考勤", "code": "leave", "type": 1, "path": "/leave", "icon": "Calendar", "sort_order": 7, "status": 1, "parent": None},
    {"name": "我的请假", "code": "leave:request", "type": 2, "path": "/leave/my", "icon": "Edit", "sort_order": 1, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "leave:request:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "leave:request"},
    {"name": "提交", "code": "leave:request:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "leave:request"},
    {"name": "撤销", "code": "leave:request:cancel", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "leave:request"},
    {"name": "请假审批", "code": "leave:review", "type": 2, "path": "/leave/review", "icon": "CircleCheck", "sort_order": 2, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "leave:review:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "leave:review"},
    {"name": "通过", "code": "leave:review:approve", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "leave:review"},
    {"name": "驳回", "code": "leave:review:reject", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "leave:review"},
    {"name": "我的考勤", "code": "attendance:my", "type": 2, "path": "/attendance/my", "icon": "Clock", "sort_order": 3, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "attendance:my:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "attendance:my"},
    {"name": "学生考勤", "code": "attendance:student", "type": 2, "path": "/attendance/student", "icon": "Postcard", "sort_order": 4, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "attendance:student:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "attendance:student"},
    {"name": "新增", "code": "attendance:student:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "attendance:student"},
    {"name": "编辑", "code": "attendance:student:update", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "attendance:student"},
    {"name": "删除", "code": "attendance:student:delete", "type": 3, "path": None, "icon": None, "sort_order": 4, "status": 1, "parent": "attendance:student"},
    {"name": "教职工考勤", "code": "attendance:teacher", "type": 2, "path": "/attendance/teacher", "icon": "Avatar", "sort_order": 5, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "attendance:teacher:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "attendance:teacher"},
    {"name": "新增", "code": "attendance:teacher:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "attendance:teacher"},
    {"name": "编辑", "code": "attendance:teacher:update", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "attendance:teacher"},
    {"name": "删除", "code": "attendance:teacher:delete", "type": 3, "path": None, "icon": None, "sort_order": 4, "status": 1, "parent": "attendance:teacher"},
]

REQUEST_CODES = ["leave", "leave:request", "leave:request:list", "leave:request:create", "leave:request:cancel"]
REVIEW_CODES = ["leave:review", "leave:review:list", "leave:review:approve", "leave:review:reject"]
MY_ATTENDANCE = ["leave", "attendance:my", "attendance:my:list"]
STUDENT_ATTENDANCE_MANAGE = [
    "leave", "attendance:student", "attendance:student:list",
    "attendance:student:create", "attendance:student:update", "attendance:student:delete",
]
TEACHER_ATTENDANCE_MANAGE = [
    "leave", "attendance:teacher", "attendance:teacher:list",
    "attendance:teacher:create", "attendance:teacher:update", "attendance:teacher:delete",
]

ROLE_CODES = {
    "student": REQUEST_CODES + MY_ATTENDANCE,
    "teacher": REQUEST_CODES + MY_ATTENDANCE,
    "staff": REQUEST_CODES + MY_ATTENDANCE,
    "staff_teacher": REQUEST_CODES + MY_ATTENDANCE,
    "academic_admin": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE + TEACHER_ATTENDANCE_MANAGE,
    "staff_affairs": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE + TEACHER_ATTENDANCE_MANAGE,
    "counselor": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE,
    "staff_counselor": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE,
    "department_admin": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE + TEACHER_ATTENDANCE_MANAGE,
    "staff_dean": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE + TEACHER_ATTENDANCE_MANAGE,
    "admin": REQUEST_CODES + REVIEW_CODES + MY_ATTENDANCE + STUDENT_ATTENDANCE_MANAGE + TEACHER_ATTENDANCE_MANAGE,
}


def assign_codes(db, role_code: str, codes: list[str]) -> set[int]:
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        return set()
    menus = db.query(Menu).filter(Menu.code.in_(codes)).all()
    existing = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == role.id).all()}
    for menu in menus:
        if menu.id not in existing:
            db.add(RoleMenu(role_id=role.id, menu_id=menu.id))
    return {user_id for user_id, in db.query(UserRole.user_id).filter(UserRole.role_id == role.id).all()}


def clear_cached_permissions(user_ids: set[int]):
    if not user_ids:
        return
    try:
        client = redis_lib.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        keys = []
        for user_id in user_ids:
            keys.extend([f"user_perms:{user_id}", f"user_menus:{user_id}"])
        client.delete(*keys)
    except Exception:
        pass


def main():
    db = SessionLocal()
    try:
        by_code = {}
        for item in MENUS:
            parent = by_code.get(item["parent"]) if item["parent"] else None
            data = {k: v for k, v in item.items() if k != "parent"}
            menu = db.query(Menu).filter(Menu.code == item["code"]).first()
            if menu:
                for key, value in data.items():
                    setattr(menu, key, value)
                menu.parent_id = parent.id if parent else None
            else:
                menu = Menu(**data, parent_id=parent.id if parent else None)
                db.add(menu)
                db.flush()
            by_code[item["code"]] = menu

        affected_user_ids = set()
        for role_code, codes in ROLE_CODES.items():
            affected_user_ids.update(assign_codes(db, role_code, codes))

        db.commit()
        clear_cached_permissions(affected_user_ids)
        print("请假考勤菜单和角色权限同步完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
