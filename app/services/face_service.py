"""
人脸识别服务
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
import numpy as np

from app.models.user import User
from app.models.face import FaceTemplate, FaceLoginLog
from app.core.security import create_access_token, create_refresh_token
from app.exceptions import AuthenticationError, BusinessException
from app.redis import redis_set, redis_get, redis_delete
from app.config import settings

logger = logging.getLogger("app")

FACE_MATCH_THRESHOLD = 0.6
FACE_LOGIN_RATE_LIMIT_KEY = "face_login_rate:{ip}"
FACE_LOGIN_RATE_LIMIT_COUNT = 5
FACE_LOGIN_RATE_LIMIT_TTL = 300


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算余弦相似度"""
    a = np.array(vec1)
    b = np.array(vec2)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


def face_login(feature_vector: List[float], device_info: str, ip: str, db: Session) -> dict:
    """人脸登录"""
    if len(feature_vector) != 128:
        raise BusinessException(code=400, message="特征向量维度不正确")

    rate_key = FACE_LOGIN_RATE_LIMIT_KEY.format(ip=ip)
    try:
        count = redis_get(rate_key)
        count = int(count) if count and count.isdigit() else 0
        if count >= FACE_LOGIN_RATE_LIMIT_COUNT:
            raise BusinessException(code=400, message="尝试次数过多，请5分钟后再试")
        redis_set(rate_key, str(count + 1), ex=FACE_LOGIN_RATE_LIMIT_TTL)
    except Exception:
        pass

    templates = db.query(FaceTemplate).filter(FaceTemplate.status == 1).all()

    if not templates:
        raise AuthenticationError("系统暂无已录入人脸，请使用密码登录")

    max_similarity = 0.0
    matched_user = None

    for template in templates:
        try:
            stored_vector = json.loads(template.feature_vector)
            if len(stored_vector) != 128:
                continue
            similarity = cosine_similarity(feature_vector, stored_vector)
            if similarity > max_similarity:
                max_similarity = similarity
                matched_user = template.user
        except Exception as e:
            logger.error(f"人脸比对失败: {e}")
            continue

    success = max_similarity >= FACE_MATCH_THRESHOLD
    message = ""

    if not success:
        message = f"人脸匹配失败，相似度: {max_similarity:.4f}"
        _log_face_login(None, max_similarity, False, message, ip, device_info, db)
        raise AuthenticationError(message)

    if matched_user.status != 1:
        message = "用户账号已被禁用"
        _log_face_login(matched_user.id, max_similarity, False, message, ip, device_info, db)
        raise AuthenticationError(message)

    matched_user.last_login_at = datetime.now()
    db.commit()

    access_token = create_access_token(matched_user.id)
    refresh_token = create_refresh_token(matched_user.id)

    try:
        refresh_key = f"refresh_token:{matched_user.id}"
        redis_set(refresh_key, refresh_token, ex=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    except Exception:
        pass

    from app.models.user import UserRole, Role
    user_roles = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == matched_user.id)
        .all()
    )
    role_list = [
        {"id": r.id, "code": r.code, "name": r.name}
        for r in user_roles
    ]
    is_admin = any(r.code == "admin" for r in user_roles)

    message = f"人脸登录成功，相似度: {max_similarity:.4f}"
    _log_face_login(matched_user.id, max_similarity, True, message, ip, device_info, db)

    logger.info(f"用户 {matched_user.username} 人脸识别登录成功")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": matched_user.id,
            "username": matched_user.username,
            "real_name": matched_user.real_name,
            "phone": matched_user.phone,
            "email": matched_user.email,
            "roles": role_list,
            "is_admin": is_admin,
        },
    }


def enroll_face(user: User, feature_vector: List[float], confidence: float, db: Session) -> FaceTemplate:
    """录入人脸模板"""
    if len(feature_vector) != 128:
        raise BusinessException(code=400, message="特征向量维度不正确")

    if confidence < 0.5:
        raise BusinessException(code=400, message="人脸图像质量过低，请重新拍摄")

    existing = db.query(FaceTemplate).filter(FaceTemplate.user_id == user.id).first()

    if existing:
        existing.feature_vector = json.dumps(feature_vector)
        existing.confidence = confidence
        existing.updated_at = datetime.now()
    else:
        existing = FaceTemplate(
            user_id=user.id,
            feature_vector=json.dumps(feature_vector),
            confidence=confidence,
            status=1,
        )
        db.add(existing)

    user.has_face_template = True
    db.commit()

    logger.info(f"用户 {user.username} 人脸录入成功")
    return existing


def delete_face(user: User, db: Session) -> None:
    """删除人脸模板"""
    template = db.query(FaceTemplate).filter(FaceTemplate.user_id == user.id).first()

    if template:
        db.delete(template)
        user.has_face_template = False
        db.commit()
        logger.info(f"用户 {user.username} 人脸模板已删除")


def get_face_template(user: User, db: Session) -> Optional[FaceTemplate]:
    """获取用户人脸模板"""
    return db.query(FaceTemplate).filter(FaceTemplate.user_id == user.id).first()


def get_face_login_logs(user_id: Optional[int] = None, db: Session = None,
                       page: int = 1, page_size: int = 20) -> Tuple[List[FaceLoginLog], int]:
    """获取人脸登录日志"""
    query = db.query(FaceLoginLog)
    if user_id:
        query = query.filter(FaceLoginLog.user_id == user_id)
    query = query.order_by(FaceLoginLog.created_at.desc())

    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    return logs, total


def _log_face_login(user_id: Optional[int], confidence: float, success: bool,
                    message: str, ip: str, device_info: str, db: Session) -> None:
    """记录人脸登录日志"""
    try:
        log = FaceLoginLog(
            user_id=user_id,
            confidence=confidence,
            success=success,
            message=message,
            ip_address=ip,
            device_info=device_info,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"记录人脸登录日志失败: {e}")