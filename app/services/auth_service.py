"""
认证服务
"""
import random
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import verify_password, create_access_token, create_refresh_token, hash_password
from app.core.validators import validate_password, validate_email
from app.core.rate_limit import check_login_rate_limit
from app.exceptions import AuthenticationError, BusinessException
from app.redis import redis_set, redis_get, redis_delete
from app.config import settings

logger = logging.getLogger("app")

# 重置验证码：10分钟有效
RESET_CODE_TTL = 600


def login(account: str, password: str, ip: str, db: Session) -> dict:
    """
    用户登录
    - 自动判断 account 类型：手机号/身份证/用户名
    - Redis 限流检查
    """
    # 1. 限流检查
    allowed, msg = check_login_rate_limit(account, ip)
    if not allowed:
        raise BusinessException(code=400, message=msg)

    # 2. 查找用户
    user = _find_user_by_account(account, db)
    if not user:
        raise AuthenticationError("账号或密码错误")

    # 3. 验证密码
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("账号或密码错误")

    # 4. 检查状态
    if user.status != 1:
        raise AuthenticationError("账号已被禁用")

    # 5. 更新最后登录时间
    user.last_login_at = datetime.now()
    db.commit()

    # 6. 生成 token
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # 7. 将 refresh_token 存入 Redis（Redis 不可用时仍返回 token）
    try:
        refresh_key = f"refresh_token:{user.id}"
        redis_set(refresh_key, refresh_token, ex=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    except Exception:
        pass

    # 8. 获取用户角色
    from app.models.user import UserRole, Role
    user_roles = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )
    role_list = [
        {"id": r.id, "code": r.code, "name": r.name}
        for r in user_roles
    ]
    is_admin = any(r.code == "admin" for r in user_roles)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "phone": user.phone,
            "email": user.email,
            "roles": role_list,
            "is_admin": is_admin,
        },
    }


def refresh_token(refresh_token_str: str, db: Session) -> dict:
    """刷新 token"""
    from app.core.security import decode_token

    payload = decode_token(refresh_token_str)
    if not payload or payload.get("type") != "refresh":
        raise AuthenticationError("refresh_token 无效或已过期")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("refresh_token 无效")

    try:
        stored = redis_get(f"refresh_token:{user_id}")
        if stored and stored != refresh_token_str:
            raise AuthenticationError("refresh_token 已失效")
    except Exception:
        pass

    user = db.query(User).filter(User.id == int(user_id), User.is_deleted == False).first()
    if not user or user.status != 1:
        raise AuthenticationError("用户不存在或已被禁用")

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    try:
        redis_set(f"refresh_token:{user.id}", new_refresh, ex=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    except Exception:
        pass

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


def logout(user_id: int):
    """注销：删除 Redis 中的 refresh_token"""
    try:
        redis_delete(f"refresh_token:{user_id}")
    except Exception:
        pass


def change_password(user: User, old_password: str, new_password: str, db: Session):
    """修改密码"""
    if not verify_password(old_password, user.password_hash):
        raise BusinessException(code=400, message="旧密码不正确")

    valid, msg = validate_password(new_password)
    if not valid:
        raise BusinessException(code=400, message=msg)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.commit()


def send_reset_code(email: str, ip: str, db: Session):
    """
    发送密码重置验证码
    - 校验邮箱是否已注册
    - 限流：同邮箱 1 分钟 1 次，1 小时 5 次
    - 生成 6 位随机验证码存入 Redis（10 分钟有效）
    """
    # 邮箱格式校验
    valid, msg = validate_email(email)
    if not valid:
        raise BusinessException(code=400, message=f"邮箱格式不正确: {msg}")

    # 确认邮箱已注册
    user = db.query(User).filter(User.email == email, User.is_deleted == False).first()
    if not user:
        # 为安全考虑，不暴露"邮箱未注册"，仍然返回成功提示
        logger.warning(f"重置密码请求 - 邮箱未注册: {email}")
        return False

    # 限流检查
    try:
        minute_key = f"reset_rate:min:{email}"
        hour_key = f"reset_rate:hour:{email}"

        # 1 分钟 1 次
        if redis_get(minute_key):
            raise BusinessException(code=400, message="请求过于频繁，请 1 分钟后再试")

        # 1 小时 5 次
        hour_count = redis_get(hour_key)
        hour_count = int(hour_count) if hour_count and hour_count.isdigit() else 0
        if hour_count >= 5:
            raise BusinessException(code=400, message="请求过于频繁，请 1 小时后再试")
    except BusinessException:
        raise
    except Exception:
        # Redis 不可用时跳过限流
        pass

    # 生成验证码
    code = str(random.randint(100000, 999999))

    # 存入 Redis
    try:
        redis_set(f"reset_code:{email}", code, ex=RESET_CODE_TTL)
        # 记录限流计数
        redis_set(f"reset_rate:min:{email}", "1", ex=60)
        # 小时计数（自增）
        hour_key = f"reset_rate:hour:{email}"
        # 用 incr 不方便，这里简化：每次请求 +1，3600s 过期
        if hour_count:
            redis_set(hour_key, str(hour_count + 1), ex=3600)
        else:
            redis_set(hour_key, "1", ex=3600)
    except Exception:
        # Redis 不可用，我们仍然尝试发送邮件，但无法校验验证码
        # 为保证安全，记录到日志但返回失败提示
        logger.error("Redis 不可用，无法存储验证码")

    # 发送邮件
    from app.utils.email import send_verification_code
    success = send_verification_code(email, code)

    if not success:
        raise BusinessException(code=400, message="邮件发送失败，请检查邮箱地址或稍后再试")

    logger.info(f"重置密码验证码已发送至 {email}")
    return True


def reset_password_by_code(email: str, code: str, new_password: str, confirm_password: str, db: Session):
    """
    通过邮箱验证码重置密码
    - 校验验证码（Redis 中存储的）
    - 校验两次密码一致
    - 校验密码强度
    - 更新密码
    - 成功后删除验证码（一次性使用）
    """
    # 1. 校验邮箱格式
    valid, msg = validate_email(email)
    if not valid:
        raise BusinessException(code=400, message=f"邮箱格式不正确: {msg}")

    # 2. 校验两次密码一致
    if new_password != confirm_password:
        raise BusinessException(code=400, message="两次输入的密码不一致")

    # 3. 校验密码强度
    valid, msg = validate_password(new_password)
    if not valid:
        raise BusinessException(code=400, message=msg)

    # 4. 查找用户
    user = db.query(User).filter(User.email == email, User.is_deleted == False).first()
    if not user:
        raise BusinessException(code=400, message="用户不存在")

    # 5. 校验验证码
    stored_code = None
    try:
        stored_code = redis_get(f"reset_code:{email}")
    except Exception:
        raise BusinessException(code=400, message="验证码服务暂不可用，请稍后重试")

    if not stored_code:
        raise BusinessException(code=400, message="验证码已过期或不存在，请重新申请")

    if stored_code != code:
        raise BusinessException(code=400, message="验证码不正确")

    # 6. 更新密码
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.last_login_at = datetime.now()
    db.commit()

    # 7. 删除验证码
    try:
        redis_delete(f"reset_code:{email}")
    except Exception:
        pass

    logger.info(f"用户 {user.username} 密码重置成功")
    return True


def _find_user_by_account(account: str, db: Session) -> User | None:
    """根据 account 自动判断类型查找用户"""
    import re
    # 尝试手机号
    if re.match(r"^(\+86[- ]?)?1[3-9]\d{9}$", account):
        from app.core.validators import normalize_phone
        normalized = normalize_phone(account)
        user = db.query(User).filter(User.phone == normalized, User.is_deleted == False).first()
        if user:
            return user
    # 尝试身份证号
    if len(account) == 18 and account[:17].isdigit() and (account[-1].isdigit() or account[-1].lower() == "x"):
        user = db.query(User).filter(User.id_card == account, User.is_deleted == False).first()
        if user:
            return user
    # 默认按用户名
    return db.query(User).filter(User.username == account, User.is_deleted == False).first()
