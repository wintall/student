"""
RBAC 权限检查模块
- admin 自动放行
- 其他角色通过 UserRole -> Role -> RoleMenu -> Menu 链路获取权限
- 优先从 Redis 缓存读取权限列表
"""
import json
from typing import List, Set

from sqlalchemy.orm import Session

from app.models.user import User, Role, Menu, UserRole, RoleMenu
from app.redis import redis_get, redis_set


def get_user_role_codes(user: User, db: Session) -> Set[str]:
    """Return role codes assigned to a user."""
    roles = db.query(Role.code).join(UserRole, UserRole.role_id == Role.id).filter(
        UserRole.user_id == user.id
    ).all()
    return {row[0] for row in roles}


def get_user_permission_codes(user: User, db: Session) -> Set[str]:
    """
    获取用户的所有权限代码集合
    :param user: 用户对象
    :param db: 数据库会话
    :return: 权限代码集合，如 {"student:list", "student:create", ...}
    """
    # 1. 检查是否是 admin（直接放行）
    role_codes = get_user_role_codes(user, db)
    if "admin" in role_codes:
        return {"*"}  # 超级管理员拥有全部权限

    # 2. 尝试从 Redis 缓存读取（Redis 不可用时跳过）
    cache_key = f"user_perms:{user.id}"
    try:
        cached = redis_get(cache_key)
        if cached:
            return set(json.loads(cached))
    except Exception:
        pass

    # 3. 从数据库查询权限列表
    perm_codes = (
        db.query(Menu.code)
        .join(RoleMenu, RoleMenu.menu_id == Menu.id)
        .join(UserRole, UserRole.role_id == RoleMenu.role_id)
        .filter(
            UserRole.user_id == user.id,
            Menu.status == 1,  # 只取启用状态的菜单
        )
        .distinct()
        .all()
    )

    codes = {row[0] for row in perm_codes}

    # 4. 缓存到 Redis（10分钟过期，Redis 不可用时跳过）
    try:
        redis_set(cache_key, json.dumps(list(codes)), ex=600)
    except Exception:
        pass

    return codes


def has_permission(user: User, db: Session, required_code: str) -> bool:
    """
    检查用户是否拥有指定权限
    :param user: 用户对象
    :param db: 数据库会话
    :param required_code: 所需权限代码
    :return: True=有权限
    """
    perms = get_user_permission_codes(user, db)
    if "*" in perms:
        return True
    return required_code in perms


def get_user_menu_tree(user: User, db: Session) -> List[dict]:
    """
    获取用户的菜单树（仅启用状态）
    :param user: 用户对象
    :param db: 数据库会话
    :return: 菜单树列表
    """
    # admin 获取所有菜单
    user_roles = db.query(Role).join(UserRole, UserRole.role_id == Role.id).filter(
        UserRole.user_id == user.id
    ).all()
    role_codes = {r.code for r in user_roles}

    if "admin" in role_codes:
        menus = db.query(Menu).filter(Menu.status == 1).order_by(Menu.sort_order).all()
    else:
        # 尝试从缓存读取（Redis 不可用时跳过）
        cache_key = f"user_menus:{user.id}"
        try:
            cached = redis_get(cache_key)
            if cached:
                return _build_tree(json.loads(cached))
        except Exception:
            pass

        menus = (
            db.query(Menu)
            .join(RoleMenu, RoleMenu.menu_id == Menu.id)
            .join(UserRole, UserRole.role_id == RoleMenu.role_id)
            .filter(
                UserRole.user_id == user.id,
                Menu.status == 1,
            )
            .order_by(Menu.sort_order)
            .distinct()
            .all()
        )

    # 构建树形结构
    menu_list = []
    for m in menus:
        menu_list.append({
            "id": m.id,
            "parent_id": m.parent_id,
            "name": m.name,
            "code": m.code,
            "type": m.type,
            "path": m.path,
            "icon": m.icon,
            "sort_order": m.sort_order,
        })

    if "admin" not in role_codes:
        # 缓存菜单树（10分钟，Redis 不可用时跳过）
        try:
            redis_set(f"user_menus:{user.id}", json.dumps(menu_list), ex=600)
        except Exception:
            pass

    return _build_tree(menu_list)


def _build_tree(items: List[dict], parent_id=None) -> List[dict]:
    """将平铺的菜单列表构建为树形结构"""
    tree = []
    for item in items:
        if item.get("parent_id") == parent_id:
            children = _build_tree(items, item["id"])
            node = {**item}
            if children:
                node["children"] = children
            tree.append(node)
    return tree


def clear_user_cache(user_id: int):
    """清除用户的权限和菜单缓存"""
    try:
        from app.redis import redis_delete
        redis_delete(f"user_perms:{user_id}")
        redis_delete(f"user_menus:{user_id}")
    except Exception:
        pass  # Redis 不可用时跳过
