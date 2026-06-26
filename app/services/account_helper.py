"""
Helpers for creating login accounts behind person records.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.core.validators import validate_email, validate_id_card, validate_phone, normalize_phone
from app.exceptions import BusinessException, NotFoundError
from app.models.user import Role, User, UserRole


def _clean(value: Optional[str]) -> Optional[str]:
    value = value.strip() if isinstance(value, str) else value
    return value or None


def _prepare_phone(phone: Optional[str], db: Session, user_id: Optional[int] = None) -> Optional[str]:
    phone = _clean(phone)
    if not phone:
        return None
    valid, msg = validate_phone(phone)
    if not valid:
        raise BusinessException(message=msg)
    phone = normalize_phone(phone)
    q = db.query(User).filter(User.phone == phone, User.is_deleted == False)
    if user_id:
        q = q.filter(User.id != user_id)
    if q.first():
        raise BusinessException(message="手机号已被注册")
    return phone


def _prepare_email(email: Optional[str], db: Session, user_id: Optional[int] = None) -> Optional[str]:
    email = _clean(email)
    if not email:
        return None
    valid, msg = validate_email(email)
    if not valid:
        raise BusinessException(message=msg)
    q = db.query(User).filter(User.email == email, User.is_deleted == False)
    if user_id:
        q = q.filter(User.id != user_id)
    if q.first():
        raise BusinessException(message="邮箱已被注册")
    return email


def _prepare_user_id_card(id_card: Optional[str], db: Session, user_id: Optional[int] = None) -> Optional[str]:
    id_card = _clean(id_card)
    if not id_card:
        return None
    valid, msg = validate_id_card(id_card)
    if not valid:
        return None
    q = db.query(User).filter(User.id_card == id_card, User.is_deleted == False)
    if user_id:
        q = q.filter(User.id != user_id)
    if q.first():
        raise BusinessException(message="身份证号已被注册")
    return id_card


def assign_role(user: User, role_code: str, db: Session) -> None:
    role = db.query(Role).filter(Role.code == role_code).first()
    if not role:
        return
    exists = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    ).first()
    if not exists:
        db.add(UserRole(user_id=user.id, role_id=role.id))


def ensure_person_user(
    db: Session,
    *,
    user_id: Optional[int],
    username: str,
    real_name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    id_card: Optional[str] = None,
    role_code: Optional[str] = None,
) -> User:
    if user_id:
        user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
        if not user:
            raise NotFoundError("关联用户不存在")
        if role_code:
            assign_role(user, role_code, db)
        return user

    username = _clean(username)
    if not username:
        raise BusinessException(message="缺少登录账号")

    user = db.query(User).filter(User.username == username, User.is_deleted == False).first()
    if not user:
        user = User(
            username=username,
            password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
            real_name=real_name,
            phone=_prepare_phone(phone, db),
            email=_prepare_email(email, db),
            id_card=_prepare_user_id_card(id_card, db),
            status=1,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
    if role_code:
        assign_role(user, role_code, db)
    return user


def update_user_contact(
    user: User,
    db: Session,
    *,
    real_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    id_card: Optional[str] = None,
) -> None:
    if real_name is not None:
        user.real_name = real_name
    if phone is not None:
        user.phone = _prepare_phone(phone, db, user.id)
    if email is not None:
        user.email = _prepare_email(email, db, user.id)
    user_id_card = _prepare_user_id_card(id_card, db, user.id)
    if user_id_card:
        user.id_card = user_id_card
