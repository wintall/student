"""
FastAPI 依赖注入
"""
from typing import Generator

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import AuthenticationError, PermissionDenied
from app.core.permissions import has_permission
from app.core.security import decode_token
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    获取当前登录用户
    从 Authorization: Bearer <token> 中提取并验证
    """
    if not credentials:
        raise AuthenticationError("请先登录")

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise AuthenticationError("token 无效或已过期")
    if payload.get("type") != "access":
        raise AuthenticationError("token 类型错误")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("token 无效")

    user = db.query(User).filter(
        User.id == int(user_id),
        User.is_deleted == False,
        User.status == 1,
    ).first()

    if not user:
        raise AuthenticationError("用户不存在或已被禁用")

    # 将 user 挂载到 request.state 便于后续使用
    request.state.current_user = user
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """可选认证：有 token 则解析用户，无 token 返回 None"""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id), User.is_deleted == False).first()


def require_permission(permission_code: str | list[str]):
    """FastAPI dependency factory for RBAC permission checks."""
    def checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if isinstance(permission_code, list):
            allowed = any(has_permission(user, db, code) for code in permission_code)
        else:
            allowed = has_permission(user, db, permission_code)
        if not allowed:
            raise PermissionDenied("无权执行此操作")
        return user

    return checker
