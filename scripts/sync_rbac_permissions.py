"""
Synchronize RBAC menu permissions for the current demo role model.

This keeps visible menu pages aligned with backend API permissions so users do
not see pages that immediately fail with "no permission".
"""
from app.database import SessionLocal
from app.models.user import Menu, Role, RoleMenu, UserRole


ACTION_LABELS = {
    "list": "查看",
    "create": "新增",
    "update": "编辑",
    "delete": "删除",
    "approve": "通过",
    "reject": "驳回",
    "cancel": "撤销",
    "view": "查看",
    "publish": "发布",
    "access": "访问",
}


COMMON = {
    "dashboard",
    "announcement", "announcement:list", "announcement:list:view",
    "email", "email:inbox", "email:sent", "email:compose",
    "leave", "leave:request", "leave:request:list", "leave:request:create", "leave:request:cancel",
    "academic-calendar", "academic-calendar:term", "academic-calendar:term:list",
    "schedule", "schedule:my", "schedule:my:list",
    "notification",
}

ROLE_MENU_CODES = {
    "admin": None,
    "staff_teacher": COMMON | {
        "nl-db", "nl-db:access",
        "operations", "operations:export",
    },
    "staff_dean": COMMON | {
        "org", "org:department", "org:department:list",
        "org:clazz", "org:clazz:list", "org:clazz:create", "org:clazz:update",
        "people", "people:teacher", "people:teacher:list",
        "people:student", "people:student:list", "people:student:create", "people:student:update",
        "teaching", "teaching:course", "teaching:course:list",
        "teaching:exam", "teaching:exam:list", "teaching:exam:create", "teaching:exam:update",
        "teaching:score", "teaching:score:list", "teaching:score:create", "teaching:score:update",
        "schedule:timetable", "schedule:timetable:list", "schedule:timetable:create", "schedule:timetable:update", "schedule:timetable:delete",
        "leave:review", "leave:review:list", "leave:review:approve", "leave:review:reject",
        "operations", "operations:health", "operations:export",
        "nl-db", "nl-db:access",
    },
    "staff_counselor": COMMON | {
        "org", "org:department", "org:department:list",
        "org:clazz", "org:clazz:list", "org:clazz:update",
        "people", "people:student", "people:student:list", "people:student:create", "people:student:update",
        "teaching", "teaching:course", "teaching:course:list",
        "teaching:exam", "teaching:exam:list",
        "teaching:score", "teaching:score:list",
        "schedule:timetable", "schedule:timetable:list",
        "leave:review", "leave:review:list", "leave:review:approve", "leave:review:reject",
        "operations", "operations:health",
        "nl-db", "nl-db:access",
    },
    "staff_affairs": COMMON | {
        "org", "org:department", "org:department:list", "org:department:create", "org:department:update",
        "org:clazz", "org:clazz:list", "org:clazz:create", "org:clazz:update",
        "people", "people:teacher", "people:teacher:list", "people:teacher:create", "people:teacher:update",
        "people:student", "people:student:list", "people:student:create", "people:student:update",
        "teaching", "teaching:course", "teaching:course:list", "teaching:course:create", "teaching:course:update",
        "teaching:exam", "teaching:exam:list", "teaching:exam:create", "teaching:exam:update",
        "teaching:score", "teaching:score:list", "teaching:score:create", "teaching:score:update",
        "academic-calendar:term:create", "academic-calendar:term:update", "academic-calendar:term:delete",
        "schedule:classroom", "schedule:classroom:list", "schedule:classroom:create", "schedule:classroom:update", "schedule:classroom:delete",
        "schedule:timetable", "schedule:timetable:list", "schedule:timetable:create", "schedule:timetable:update", "schedule:timetable:delete",
        "operations", "operations:health", "operations:export",
        "nl-db", "nl-db:access",
    },
    "student": {
        "dashboard",
        "announcement", "announcement:list", "announcement:list:view",
        "email", "email:inbox", "email:sent", "email:compose",
        "leave", "leave:request", "leave:request:list", "leave:request:create", "leave:request:cancel",
        "academic-calendar", "academic-calendar:term", "academic-calendar:term:list",
        "schedule", "schedule:my", "schedule:my:list",
        "operations", "operations:export",
        "notification",
        "nl-db", "nl-db:access",
    },
    "staff": {
        "dashboard",
        "leave", "leave:request", "leave:request:list", "leave:request:create", "leave:request:cancel",
        "academic-calendar", "academic-calendar:term", "academic-calendar:term:list",
        "schedule", "schedule:my", "schedule:my:list",
        "nl-db", "nl-db:access",
    },
}


def _parent_code(code: str) -> str | None:
    parts = code.split(":")
    if len(parts) <= 1:
        return None
    return ":".join(parts[:-1])


def _ensure_permission_menu(db, code: str) -> Menu:
    existing = db.query(Menu).filter(Menu.code == code).first()
    if existing:
        return existing

    parent = None
    parent_code = _parent_code(code)
    if parent_code:
        parent = db.query(Menu).filter(Menu.code == parent_code).first()

    action = code.split(":")[-1]
    menu = Menu(
        parent_id=parent.id if parent else None,
        name=ACTION_LABELS.get(action, action),
        code=code,
        type=3,
        path=None,
        icon=None,
        sort_order=99,
        status=1,
    )
    db.add(menu)
    db.flush()
    print(f"[create] permission menu: {code}")
    return menu


def ensure_required_menus(db):
    required_codes = set()
    for menu_codes in ROLE_MENU_CODES.values():
        if menu_codes:
            required_codes.update(menu_codes)
    for code in sorted(required_codes):
        if ":" in code:
            _ensure_permission_menu(db, code)


def sync_role(db, role_code: str, menu_codes: set[str] | None):
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        print(f"[skip] role not found: {role_code}")
        return

    if menu_codes is None:
        menus = db.query(Menu).filter(Menu.status == 1).all()
    else:
        menus = db.query(Menu).filter(Menu.code.in_(menu_codes), Menu.status == 1).all()

    db.query(RoleMenu).filter(RoleMenu.role_id == role.id).delete(synchronize_session=False)
    for menu in menus:
        db.add(RoleMenu(role_id=role.id, menu_id=menu.id))

    user_ids = [row[0] for row in db.query(UserRole.user_id).filter(UserRole.role_id == role.id).all()]
    print(f"[ok] {role_code}: {len(menus)} permissions, {len(user_ids)} users")


def main():
    db = SessionLocal()
    try:
        ensure_required_menus(db)
        for role_code, menu_codes in ROLE_MENU_CODES.items():
            sync_role(db, role_code, menu_codes)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
