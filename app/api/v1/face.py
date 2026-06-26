"""
人脸识别相关路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.face import FaceLoginRequest, FaceEnrollRequest
from app.services import face_service
from app.utils.response import success
from app.utils.pagination import paginate

router = APIRouter(prefix="/face", tags=["人脸识别"])


@router.post("/login")
def face_login(
    body: FaceLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """人脸登录"""
    ip = request.client.host if request.client else "unknown"
    result = face_service.face_login(body.feature_vector, body.device_info, ip, db)
    return success(data=result, message="人脸识别登录成功")


@router.post("/enroll")
def enroll_face(
    body: FaceEnrollRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """录入人脸模板"""
    template = face_service.enroll_face(user, body.feature_vector, body.confidence, db)
    return success(data={
        "id": template.id,
        "confidence": template.confidence,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }, message="人脸录入成功")


@router.delete("/template")
def delete_face(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除人脸模板"""
    face_service.delete_face(user, db)
    return success(message="人脸模板已删除")


@router.get("/template")
def get_face_template(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的人脸模板信息"""
    template = face_service.get_face_template(user, db)
    if not template:
        return success(data=None, message="未录入人脸")
    return success(data={
        "id": template.id,
        "confidence": template.confidence,
        "status": template.status,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    })


@router.get("/logs")
def get_face_login_logs(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取人脸登录日志"""
    from app.models.user import UserRole, Role
    is_admin = db.query(Role).join(UserRole).filter(
        UserRole.user_id == user.id,
        Role.code == "admin"
    ).first() is not None

    if not is_admin:
        user_id = user.id

    logs, total = face_service.get_face_login_logs(user_id, db, page, page_size)
    return success(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": log.id,
            "user_id": log.user_id,
            "confidence": log.confidence,
            "success": log.success,
            "message": log.message,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log in logs],
    })