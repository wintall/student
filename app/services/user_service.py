"""
用户管理服务
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, Role
from app.core.security import hash_password
from app.core.validators import validate_phone, normalize_phone, validate_email, validate_id_card
from app.exceptions import BusinessException, NotFoundError
from app.config import settings
from app.schemas.user import UserCreate, UserUpdate


def create_user(data: UserCreate, db: Session) -> User:
    """创建用户"""
    # 检查用户名
    if db.query(User).filter(User.username == data.username).first():
        raise BusinessException(message="用户名已存在")

    # 校验并处理手机号
    phone = data.phone
    if phone:
        valid, msg = validate_phone(phone)
        if not valid:
            raise BusinessException(message=msg)
        phone = normalize_phone(phone)
        if db.query(User).filter(User.phone == phone).first():
            raise BusinessException(message="手机号已被注册")

    # 校验邮箱
    if data.email:
        valid, msg = validate_email(data.email)
        if not valid:
            raise BusinessException(message=msg)
        if db.query(User).filter(User.email == data.email).first():
            raise BusinessException(message="邮箱已被注册")

    # 校验身份证
    if data.id_card:
        valid, msg = validate_id_card(data.id_card)
        if not valid:
            raise BusinessException(message=msg)
        if db.query(User).filter(User.id_card == data.id_card).first():
            raise BusinessException(message="身份证号已被注册")

    # 处理密码
    raw_password = data.password if data.password else settings.DEFAULT_USER_PASSWORD
    user = User(
        username=data.username,
        real_name=data.real_name,
        phone=phone,
        email=data.email,
        id_card=data.id_card,
        status=data.status,
        password_hash=hash_password(raw_password),
        must_change_password=not bool(data.password),
    )
    db.add(user)
    db.flush()

    # 分配角色
    if data.role_ids:
        for rid in data.role_ids:
            db.add(UserRole(user_id=user.id, role_id=rid))

    db.commit()
    db.refresh(user)
    return user


def get_user(user_id: int, db: Session) -> User:
    """获取用户"""
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise NotFoundError("用户不存在")
    return user


def update_user(user_id: int, data: UserUpdate, db: Session) -> User:
    """更新用户"""
    user = get_user(user_id, db)

    update_data = data.model_dump(exclude_unset=True)

    if "phone" in update_data and update_data["phone"]:
        valid, msg = validate_phone(update_data["phone"])
        if not valid:
            raise BusinessException(message=msg)
        update_data["phone"] = normalize_phone(update_data["phone"])

    if "email" in update_data and update_data["email"]:
        valid, msg = validate_email(update_data["email"])
        if not valid:
            raise BusinessException(message=msg)

    if "id_card" in update_data and update_data["id_card"]:
        valid, msg = validate_id_card(update_data["id_card"])
        if not valid:
            raise BusinessException(message=msg)

    role_ids = update_data.pop("role_ids", None)

    # 密码字段需单独哈希处理，不能直接 setattr
    raw_password = update_data.pop("password", None)
    if raw_password:
        user.password_hash = hash_password(raw_password)

    for k, v in update_data.items():
        setattr(user, k, v)

    if role_ids is not None:
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        for rid in role_ids:
            db.add(UserRole(user_id=user_id, role_id=rid))

    db.commit()
    db.refresh(user)
    return user


def delete_user(user_id: int, db: Session):
    """软删除用户"""
    user = get_user(user_id, db)
    user.soft_delete()
    db.commit()


def get_user_role_ids(user_id: int, db: Session) -> List[int]:
    """获取用户角色ID列表"""
    return [ur.role_id for ur in db.query(UserRole).filter(UserRole.user_id == user_id).all()]


def get_user_role_names(user_id: int, db: Session) -> List[str]:
    """获取用户角色名称列表"""
    roles = db.query(Role).join(UserRole, UserRole.role_id == Role.id).filter(
        UserRole.user_id == user_id
    ).all()
    return [r.name for r in roles]
