"""
添加智能数据助手菜单到数据库
运行方式：cd e:\student && python -m scripts.add_nl_db_menu
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import Menu, Role, RoleMenu, UserRole

def add_nl_db_menu(db):
    """添加智能数据助手菜单"""
    # 检查菜单是否已存在
    existing = db.query(Menu).filter(Menu.code == "nl-db").first()
    if existing:
        print("  [已有] 智能数据助手菜单已存在")
        return

    # 创建菜单
    parent_menu = Menu(
        name="智能数据助手",
        code="nl-db",
        type=2,
        path="nl-db",
        icon="Database",
        sort_order=6,
        status=1,
        parent_id=None,
    )
    db.add(parent_menu)
    db.flush()

    # 创建子权限
    child_menu = Menu(
        name="访问",
        code="nl-db:access",
        type=3,
        sort_order=1,
        status=1,
        parent_id=parent_menu.id,
    )
    db.add(child_menu)
    db.flush()

    print(f"  [新增] 智能数据助手菜单 (ID: {parent_menu.id})")

    # 获取角色
    admin_role = db.query(Role).filter(Role.code == "admin").first()
    staff_role = db.query(Role).filter(Role.code == "staff").first()
    student_role = db.query(Role).filter(Role.code == "student").first()

    # 为角色分配菜单权限
    menu_ids = [parent_menu.id, child_menu.id]

    if admin_role:
        existing_ids = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == admin_role.id).all()}
        for mid in menu_ids:
            if mid not in existing_ids:
                db.add(RoleMenu(role_id=admin_role.id, menu_id=mid))
        print(f"  [分配] admin 角色已分配智能数据助手权限")

    if staff_role:
        existing_ids = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == staff_role.id).all()}
        for mid in menu_ids:
            if mid not in existing_ids:
                db.add(RoleMenu(role_id=staff_role.id, menu_id=mid))
        print(f"  [分配] staff 角色已分配智能数据助手权限")

    if student_role:
        existing_ids = {rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == student_role.id).all()}
        for mid in menu_ids:
            if mid not in existing_ids:
                db.add(RoleMenu(role_id=student_role.id, menu_id=mid))
        print(f"  [分配] student 角色已分配智能数据助手权限")


def main():
    print("=" * 60)
    print("  添加智能数据助手菜单")
    print("=" * 60)

    db = SessionLocal()
    try:
        add_nl_db_menu(db)
        db.commit()
        print("\n" + "=" * 60)
        print("  菜单添加完成!")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"\n  [错误] 添加失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()