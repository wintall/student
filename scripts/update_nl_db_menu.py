"""
更新智能数据助手菜单配置
运行方式：cd e:\student && python -m scripts.update_nl_db_menu
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import Menu

def update_nl_db_menu(db):
    """更新智能数据助手菜单"""
    # 查找菜单
    parent_menu = db.query(Menu).filter(Menu.code == "nl-db").first()
    if not parent_menu:
        print("  [错误] 智能数据助手菜单不存在")
        return

    # 更新父菜单
    old_path = parent_menu.path
    old_icon = parent_menu.icon
    parent_menu.path = "nl-db"
    parent_menu.icon = "Database"
    
    print(f"  [更新] 菜单路径: {old_path} -> {parent_menu.path}")
    print(f"  [更新] 菜单图标: {old_icon} -> {parent_menu.icon}")
    
    # 更新子菜单，添加path
    child_menu = db.query(Menu).filter(Menu.code == "nl-db:access").first()
    if child_menu:
        old_child_path = child_menu.path
        child_menu.path = "nl-db"
        print(f"  [更新] 子菜单路径: {old_child_path} -> {child_menu.path}")

def main():
    print("=" * 60)
    print("  更新智能数据助手菜单")
    print("=" * 60)

    db = SessionLocal()
    try:
        update_nl_db_menu(db)
        db.commit()
        print("\n" + "=" * 60)
        print("  菜单更新完成!")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"\n  [错误] 更新失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()