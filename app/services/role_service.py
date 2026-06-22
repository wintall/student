"""
角色权限服务
"""
from typing import List
from sqlalchemy.orm import Session

from app.models.user import Role, Menu, RoleMenu, UserRole
from app.exceptions import BusinessException, NotFoundError
from app.schemas.role import RoleCreate, RoleUpdate, MenuCreate, MenuUpdate


def create_role(data: RoleCreate, db: Session) -> Role:
    """创建角色"""
    if db.query(Role).filter(Role.code == data.code).first():
        raise BusinessException(message="角色代码已存在")

    role = Role(code=data.code, name=data.name, description=data.description)
    db.add(role)
    db.flush()

    if data.menu_ids:
        for mid in data.menu_ids:
            db.add(RoleMenu(role_id=role.id, menu_id=mid))

    db.commit()
    db.refresh(role)
    return role


def get_role(role_id: int, db: Session) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundError("角色不存在")
    return role


def update_role(role_id: int, data: RoleUpdate, db: Session) -> Role:
    role = get_role(role_id, db)
    update_data = data.model_dump(exclude_unset=True)
    menu_ids = update_data.pop("menu_ids", None)

    for k, v in update_data.items():
        setattr(role, k, v)

    if menu_ids is not None:
        db.query(RoleMenu).filter(RoleMenu.role_id == role_id).delete()
        for mid in menu_ids:
            db.add(RoleMenu(role_id=role_id, menu_id=mid))
        # 清除该角色下所有用户的权限缓存
        user_ids = [ur.user_id for ur in db.query(UserRole).filter(UserRole.role_id == role_id).all()]
        from app.core.permissions import clear_user_cache
        for uid in user_ids:
            clear_user_cache(uid)

    db.commit()
    db.refresh(role)
    return role


def delete_role(role_id: int, db: Session):
    role = get_role(role_id, db)
    if role.code == "admin":
        raise BusinessException(message="不能删除管理员角色")
    db.query(RoleMenu).filter(RoleMenu.role_id == role_id).delete()
    db.query(UserRole).filter(UserRole.role_id == role_id).delete()
    db.delete(role)
    db.commit()


def get_role_menu_ids(role_id: int, db: Session) -> List[int]:
    return [rm.menu_id for rm in db.query(RoleMenu).filter(RoleMenu.role_id == role_id).all()]


# ---- 菜单管理 ----

def create_menu(data: MenuCreate, db: Session) -> Menu:
    if db.query(Menu).filter(Menu.code == data.code).first():
        raise BusinessException(message="权限标识已存在")
    menu = Menu(**data.model_dump())
    db.add(menu)
    db.commit()
    db.refresh(menu)
    return menu


def get_menu(menu_id: int, db: Session) -> Menu:
    menu = db.query(Menu).filter(Menu.id == menu_id).first()
    if not menu:
        raise NotFoundError("菜单不存在")
    return menu


def update_menu(menu_id: int, data: MenuUpdate, db: Session) -> Menu:
    menu = get_menu(menu_id, db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(menu, k, v)
    db.commit()
    db.refresh(menu)
    return menu


def delete_menu(menu_id: int, db: Session):
    menu = get_menu(menu_id, db)
    # 检查子菜单
    if db.query(Menu).filter(Menu.parent_id == menu_id).first():
        raise BusinessException(message="请先删除子菜单")
    db.query(RoleMenu).filter(RoleMenu.menu_id == menu_id).delete()
    db.delete(menu)
    db.commit()


def get_all_menus(db: Session) -> List[Menu]:
    return db.query(Menu).order_by(Menu.sort_order).all()
