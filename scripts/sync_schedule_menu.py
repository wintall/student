"""
Sync academic calendar and schedule menus.
"""
import sys
from pathlib import Path

import redis as redis_lib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import SessionLocal
from app.models.user import Menu, Role, RoleMenu, UserRole


MENUS = [
    {"name": "教学日历", "code": "academic-calendar", "type": 1, "path": "/academic-calendar", "icon": "Calendar", "sort_order": 8, "status": 1, "parent": None},
    {"name": "学期管理", "code": "academic-calendar:term", "type": 2, "path": "/academic-calendar/term", "icon": "Calendar", "sort_order": 1, "status": 1, "parent": "academic-calendar"},
    {"name": "查看", "code": "academic-calendar:term:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "academic-calendar:term"},
    {"name": "新增", "code": "academic-calendar:term:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "academic-calendar:term"},
    {"name": "编辑", "code": "academic-calendar:term:update", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "academic-calendar:term"},
    {"name": "删除", "code": "academic-calendar:term:delete", "type": 3, "path": None, "icon": None, "sort_order": 4, "status": 1, "parent": "academic-calendar:term"},

    {"name": "排课管理", "code": "schedule", "type": 1, "path": "/schedule", "icon": "Tickets", "sort_order": 9, "status": 1, "parent": None},
    {"name": "教室管理", "code": "schedule:classroom", "type": 2, "path": "/schedule/classroom", "icon": "OfficeBuilding", "sort_order": 1, "status": 1, "parent": "schedule"},
    {"name": "查看", "code": "schedule:classroom:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "schedule:classroom"},
    {"name": "新增", "code": "schedule:classroom:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "schedule:classroom"},
    {"name": "编辑", "code": "schedule:classroom:update", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "schedule:classroom"},
    {"name": "删除", "code": "schedule:classroom:delete", "type": 3, "path": None, "icon": None, "sort_order": 4, "status": 1, "parent": "schedule:classroom"},
    {"name": "课表管理", "code": "schedule:timetable", "type": 2, "path": "/schedule/timetable", "icon": "Grid", "sort_order": 2, "status": 1, "parent": "schedule"},
    {"name": "查看", "code": "schedule:timetable:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "schedule:timetable"},
    {"name": "新增", "code": "schedule:timetable:create", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1, "parent": "schedule:timetable"},
    {"name": "编辑", "code": "schedule:timetable:update", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1, "parent": "schedule:timetable"},
    {"name": "删除", "code": "schedule:timetable:delete", "type": 3, "path": None, "icon": None, "sort_order": 4, "status": 1, "parent": "schedule:timetable"},
    {"name": "我的课表", "code": "schedule:my", "type": 2, "path": "/schedule/my", "icon": "Notebook", "sort_order": 3, "status": 1, "parent": "schedule"},
    {"name": "查看", "code": "schedule:my:list", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1, "parent": "schedule:my"},
]

TERM_READ = ["academic-calendar", "academic-calendar:term", "academic-calendar:term:list"]
TERM_MANAGE = TERM_READ + [
    "academic-calendar:term:create",
    "academic-calendar:term:update",
    "academic-calendar:term:delete",
]
MY_SCHEDULE = ["schedule", "schedule:my", "schedule:my:list"]
CLASSROOM_MANAGE = [
    "schedule",
    "schedule:classroom",
    "schedule:classroom:list",
    "schedule:classroom:create",
    "schedule:classroom:update",
    "schedule:classroom:delete",
]
TIMETABLE_READ = ["schedule", "schedule:timetable", "schedule:timetable:list"]
TIMETABLE_MANAGE = TIMETABLE_READ + [
    "schedule:timetable:create",
    "schedule:timetable:update",
    "schedule:timetable:delete",
]


ROLE_CODES = {
    "student": TERM_READ + MY_SCHEDULE,
    "teacher": TERM_READ + MY_SCHEDULE,
    "staff_teacher": TERM_READ + MY_SCHEDULE,
    "counselor": TERM_READ + MY_SCHEDULE + TIMETABLE_READ,
    "staff_counselor": TERM_READ + MY_SCHEDULE + TIMETABLE_READ,
    "department_admin": TERM_READ + MY_SCHEDULE + TIMETABLE_MANAGE,
    "staff_dean": TERM_READ + MY_SCHEDULE + TIMETABLE_MANAGE,
    "academic_admin": TERM_MANAGE + CLASSROOM_MANAGE + TIMETABLE_MANAGE + MY_SCHEDULE,
    "staff_affairs": TERM_MANAGE + CLASSROOM_MANAGE + TIMETABLE_MANAGE + MY_SCHEDULE,
    "staff": TERM_READ + MY_SCHEDULE,
    "admin": TERM_MANAGE + CLASSROOM_MANAGE + TIMETABLE_MANAGE + MY_SCHEDULE,
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
        print("教学日历和排课菜单权限同步完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
