"""
角色与菜单路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_permission
from app.models.user import User
from app.services import role_service
from app.schemas.role import RoleCreate, RoleUpdate, MenuCreate, MenuUpdate
from app.utils.response import success

router = APIRouter(prefix="/roles", tags=["角色权限"])


@router.post("")
def create_role(body: RoleCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("system:role:create"))):
    role = role_service.create_role(body, db)
    return success(data={"id": role.id})


@router.get("")
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_permission("system:role:list"))):
    roles = db.query(role_service.Role).all()
    data = []
    for r in roles:
        menu_ids = role_service.get_role_menu_ids(r.id, db)
        data.append({"id": r.id, "code": r.code, "name": r.name, "description": r.description, "menu_ids": menu_ids})
    return success(data=data)


@router.get("/{role_id}")
def get_role(role_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("system:role:list"))):
    role = role_service.get_role(role_id, db)
    menu_ids = role_service.get_role_menu_ids(role_id, db)
    return success(data={"id": role.id, "code": role.code, "name": role.name, "description": role.description, "menu_ids": menu_ids})


@router.put("/{role_id}")
def update_role(role_id: int, body: RoleUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("system:role:update"))):
    role = role_service.update_role(role_id, body, db)
    return success(data={"id": role.id})


@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("system:role:delete"))):
    role_service.delete_role(role_id, db)
    return success(message="删除成功")


# ---- 菜单 ----

@router.post("/menus")
def create_menu(body: MenuCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("system:menu:create"))):
    menu = role_service.create_menu(body, db)
    return success(data={"id": menu.id})


@router.get("/menus/all")
def list_menus(db: Session = Depends(get_db), _: User = Depends(require_permission("system:menu:list"))):
    menus = role_service.get_all_menus(db)
    from app.core.permissions import _build_tree
    menu_list = [
        {"id": m.id, "parent_id": m.parent_id, "name": m.name, "code": m.code,
         "type": m.type, "path": m.path, "icon": m.icon, "sort_order": m.sort_order, "status": m.status}
        for m in menus
    ]
    tree = _build_tree(menu_list)
    return success(data=tree)


@router.put("/menus/{menu_id}")
def update_menu(menu_id: int, body: MenuUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("system:menu:update"))):
    menu = role_service.update_menu(menu_id, body, db)
    return success(data={"id": menu.id})


@router.delete("/menus/{menu_id}")
def delete_menu(menu_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("system:menu:delete"))):
    role_service.delete_menu(menu_id, db)
    return success(message="删除成功")

# ---- 菜单树 + 分配菜单 ----

@router.get("/menus/tree")
def menu_tree(db: Session = Depends(get_db), _: User = Depends(require_permission("system:menu:list"))):
    menus = role_service.get_all_menus(db)
    from app.core.permissions import _build_tree
    menu_list = [
        {"id": m.id, "parent_id": m.parent_id, "name": m.name, "code": m.code,
         "type": m.type, "path": m.path, "icon": m.icon, "sort_order": m.sort_order, "status": m.status}
        for m in menus
    ]
    tree = _build_tree(menu_list)
    return success(data=tree)


@router.post("/assign-menus")
def assign_menus(body: dict, db: Session = Depends(get_db), _: User = Depends(require_permission("system:role:update"))):
    role_id = body.get("role_id")
    menu_ids = body.get("menu_ids", [])
    from app.models.user import RoleMenu
    db.query(RoleMenu).filter(RoleMenu.role_id == role_id).delete()
    for mid in menu_ids:
        db.add(RoleMenu(role_id=role_id, menu_id=mid))
    db.commit()
    return success(message="权限分配成功")
