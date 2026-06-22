"""
安全模块：JWT生成/验证 + bcrypt密码哈希
"""
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
import bcrypt

from app.config import settings


def hash_password(password: str) -> str:
    """对明文密码进行bcrypt哈希（超过72字节自动截断）"""
    pw_bytes = password.encode("utf-8")[:72]
    salted = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return salted.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码和哈希密码是否匹配（超过72字节自动截断）"""
    pw_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, extra: dict = None) -> str:
    """
    创建 access_token
    :param user_id: 用户ID
    :param extra: 额外载荷字段
    :return: JWT token 字符串
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """
    创建 refresh_token
    :param user_id: 用户ID
    :return: JWT token 字符串
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    解码 JWT token
    :return: payload dict，失败返回 None
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
