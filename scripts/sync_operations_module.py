"""
Synchronize operations/notification menus and seed basic notifications.

Run:
    python -m scripts.sync_operations_module
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.notification import Notification
from app.models.user import Menu, Role, RoleMenu, User, UserRole
from app.services.notification_service import create_notification


MENUS = [
    {
        "name": "运营工作台",
        "code": "operations",
        "type": 1,
        "path": "/operations",
        "icon": "DataAnalysis",
        "sort_order": 8,
        "status": 1,
        "children": [
            {"name": "数据体检", "code": "operations:health", "type": 2, "path": "/operations/health", "icon": "CircleCheck", "sort_order": 1, "status": 1},
            {"name": "数据导出", "code": "operations:export", "type": 2, "path": "/operations/export", "icon": "Download", "sort_order": 2, "status": 1},
            {"name": "导出学生", "code": "operations:export:students", "type": 3, "path": None, "icon": None, "sort_order": 1, "status": 1},
            {"name": "导出教师", "code": "operations:export:teachers", "type": 3, "path": None, "icon": None, "sort_order": 2, "status": 1},
            {"name": "导出课程", "code": "operations:export:courses", "type": 3, "path": None, "icon": None, "sort_order": 3, "status": 1},
            {"name": "导出课表", "code": "operations:export:schedules", "type": 3, "path": None, "icon": None, "sort_order": 4, "status": 1},
            {"name": "导出成绩", "code": "operations:export:scores", "type": 3, "path": None, "icon": None, "sort_order": 5, "status": 1},
            {"name": "导出成绩单", "code": "operations:export:transcript", "type": 3, "path": None, "icon": None, "sort_order": 6, "status": 1},
        ],
    },
    {
        "name": "通知中心",
        "code": "notification",
        "type": 2,
        "path": "/notifications",
        "icon": "Bell",
        "sort_order": 9,
        "status": 1,
    },
]

ROLE_MENU_CODES = {
    "admin": ["operations", "operations:health", "operations:export", "operations:export:students", "operations:export:teachers", "operations:export:courses", "operations:export:schedules", "operations:export:scores", "operations:export:transcript", "notification"],
    "academic_admin": ["operations", "operations:health", "operations:export", "operations:export:students", "operations:export:teachers", "operations:export:courses", "operations:export:schedules", "operations:export:scores", "operations:export:transcript", "notification"],
    "department_admin": ["operations", "operations:health", "operations:export", "operations:export:students", "operations:export:teachers", "operations:export:courses", "operations:export:schedules", "operations:export:scores", "operations:export:transcript", "notification"],
    "staff_dean": ["operations", "operations:health", "operations:export", "operations:export:students", "operations:export:teachers", "operations:export:courses", "operations:export:schedules", "operations:export:scores", "operations:export:transcript", "notification"],
    "counselor": ["operations", "operations:health", "notification"],
    "staff_counselor": ["operations", "operations:health", "notification"],
    "teacher": ["operations", "operations:export", "operations:export:courses", "operations:export:schedules", "operations:export:scores", "operations:export:transcript", "notification"],
    "staff_teacher": ["operations", "operations:export", "operations:export:courses", "operations:export:schedules", "operations:export:scores", "operations:export:transcript", "notification"],
    "student": ["operations", "operations:export", "operations:export:transcript", "notification"],
}


def upsert_menu(db, item, parent_id=None):
    children = item.pop("children", [])
    menu = db.query(Menu).filter(Menu.code == item["code"]).first()
    if not menu:
        menu = Menu(**item, parent_id=parent_id)
        db.add(menu)
        db.flush()
    else:
        for key, value in item.items():
            setattr(menu, key, value)
        menu.parent_id = parent_id
    for child in children:
        upsert_menu(db, child.copy(), menu.id)
    return menu


def sync_role_menus(db):
    menus_by_code = {m.code: m for m in db.query(Menu).filter(Menu.code.in_({code for codes in ROLE_MENU_CODES.values() for code in codes})).all()}
    for role_code, menu_codes in ROLE_MENU_CODES.items():
        role = db.query(Role).filter(Role.code == role_code).first()
        if not role:
            continue
        existing = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == role.id).all()}
        for code in menu_codes:
            menu = menus_by_code.get(code)
            if menu and menu.id not in existing:
                db.add(RoleMenu(role_id=role.id, menu_id=menu.id))


def seed_notifications(db):
    created = 0
    users = db.query(User).filter(User.is_deleted == False, User.status == 1).order_by(User.id).limit(10).all()
    for user in users:
        exists = db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.title == "系统工作台已升级",
        ).first()
        if exists:
            continue
        create_notification(
            db,
            user_id=user.id,
            title="系统工作台已升级",
            content="现在可以在首页查看待办、通知和数据体检摘要。",
            category="system",
            related_type="dashboard",
        )
        created += 1
    return created


def main():
    engine.echo = False
    Base.metadata.create_all(bind=engine, tables=[Notification.__table__])
    db = SessionLocal()
    try:
        for item in MENUS:
            upsert_menu(db, item.copy())
        sync_role_menus(db)
        created = seed_notifications(db)
        db.commit()
        print(f"Operations module synchronized. Notifications created: {created}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
