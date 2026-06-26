"""
同步请假模块菜单和角色权限。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import redis as redis_lib

from app.config import settings
from app.database import SessionLocal
from app.models.user import Menu, Role, RoleMenu, UserRole


LEAVE_MENUS = [
    {"name": "请假管理", "code": "leave", "type": 1, "path": "/leave", "icon": "calendar", "sort_order": 7, "status": 1, "parent": None},
    {"name": "我的请假", "code": "leave:request", "type": 2, "path": "/leave/my", "icon": "edit", "sort_order": 1, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "leave:request:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "leave:request"},
    {"name": "提交", "code": "leave:request:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "leave:request"},
    {"name": "撤销", "code": "leave:request:cancel", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "leave:request"},
    {"name": "请假审批", "code": "leave:review", "type": 2, "path": "/leave/review", "icon": "circle-check", "sort_order": 2, "status": 1, "parent": "leave"},
    {"name": "查看", "code": "leave:review:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "leave:review"},
    {"name": "通过", "code": "leave:review:approve", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "leave:review"},
    {"name": "驳回", "code": "leave:review:reject", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "leave:review"},
]

REQUEST_CODES = [
    "leave", "leave:request", "leave:request:list",
    "leave:request:create", "leave:request:cancel",
]
REVIEW_CODES = [
    "leave:review", "leave:review:list",
    "leave:review:approve", "leave:review:reject",
]


def assign_codes(db, role_code: str, codes: list[str]) -> set[int]:
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        return set()
    menus = db.query(Menu).filter(Menu.code.in_(codes)).all()
    existing = {
        rm.menu_id
        for rm in db.query(RoleMenu).filter(RoleMenu.role_id == role.id).all()
    }
    for menu in menus:
        if menu.id not in existing:
            db.add(RoleMenu(role_id=role.id, menu_id=menu.id))
    return {
        user_id
        for user_id, in db.query(UserRole.user_id).filter(UserRole.role_id == role.id).all()
    }


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
        for item in LEAVE_MENUS:
            menu = db.query(Menu).filter(Menu.code == item["code"]).first()
            parent_id = by_code.get(item["parent"]).id if item["parent"] else None
            data = {k: v for k, v in item.items() if k != "parent"}
            if menu:
                for key, value in data.items():
                    setattr(menu, key, value)
                menu.parent_id = parent_id
            else:
                menu = Menu(**data, parent_id=parent_id)
                db.add(menu)
                db.flush()
            by_code[item["code"]] = menu

        affected_user_ids = set()
        for role_code in [
            "student",
            "teacher",
            "staff",
            "academic_admin",
            "staff_teacher",
            "staff_affairs",
        ]:
            affected_user_ids.update(assign_codes(db, role_code, REQUEST_CODES))
        for role_code in [
            "counselor",
            "department_admin",
            "staff_counselor",
            "staff_dean",
        ]:
            affected_user_ids.update(assign_codes(db, role_code, REQUEST_CODES + REVIEW_CODES))
        affected_user_ids.update(assign_codes(db, "admin", REQUEST_CODES + REVIEW_CODES))

        db.commit()
        clear_cached_permissions(affected_user_ids)
        print("请假菜单和角色权限同步完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
