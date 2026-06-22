"""
认证路由
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, TokenResponse, ChangePasswordRequest, RefreshTokenRequest,
    SendResetCodeRequest, ResetPasswordRequest,
)
from app.services import auth_service
from app.core.permissions import get_user_menu_tree
from app.utils.response import success

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    result = auth_service.login(body.account, body.password, ip, db)
    return success(data=result, message="登录成功")


@router.post("/refresh")
def refresh(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    result = auth_service.refresh_token(body.refresh_token, db)
    return success(data=result, message="刷新成功")


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    auth_service.logout(user.id)
    return success(message="注销成功")


@router.put("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service.change_password(user, body.old_password, body.new_password, db)
    return success(message="密码修改成功")


@router.get("/me")
def get_current_user_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的个人信息与角色"""
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
    return success(data={
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "phone": user.phone,
        "email": user.email,
        "roles": role_list,
        "is_admin": is_admin,
    })


@router.get("/menus")
def get_menus(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    menus = get_user_menu_tree(user, db)
    return success(data=menus)


# ======== 密码重置：邮箱验证码 ========

@router.post("/password-reset/send-code")
def send_reset_code(
    body: SendResetCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """向邮箱发送 6 位验证码（10 分钟有效）"""
    ip = request.client.host if request.client else "unknown"
    auth_service.send_reset_code(body.email, ip, db)
    return success(message="验证码已发送，请注意查收邮件")


@router.post("/password-reset/confirm")
def confirm_reset(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """使用验证码重置密码"""
    auth_service.reset_password_by_code(
        body.email, body.code, body.new_password, body.confirm_password, db
    )
    return success(message="密码重置成功，请使用新密码登录")
