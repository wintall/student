"""
认证相关 Schema
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """登录请求"""
    account: str = Field(..., description="用户名/手机号/身份证号")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _validate_pwd(password: str) -> str:
    """统一密码强度校验:至少8位,必须同时包含数字和字母"""
    if password and len(password) < 8:
        raise ValueError("密码长度至少为8位")
    if password and not (any(c.isdigit() for c in password) and any(c.isalpha() for c in password)):
        raise ValueError("密码必须同时包含字母和数字")
    return password


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, description="新密码(至少8位,需包含字母和数字)")

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, v: str) -> str:
        return _validate_pwd(v)


class RefreshTokenRequest(BaseModel):
    """刷新 token 请求"""
    refresh_token: str = Field(..., description="refresh token")


class SendResetCodeRequest(BaseModel):
    """发送重置验证码请求"""
    email: str = Field(..., description="注册邮箱")


class ResetPasswordRequest(BaseModel):
    """重置密码请求（邮箱验证码方式）"""
    email: str = Field(..., description="注册邮箱")
    code: str = Field(..., min_length=6, max_length=6, description="6位验证码")
    new_password: str = Field(..., min_length=8, description="新密码(至少8位,需包含字母和数字)")
    confirm_password: str = Field(..., min_length=8, description="确认密码")

    @field_validator("new_password")
    @classmethod
    def _check_new_pwd(cls, v: str) -> str:
        return _validate_pwd(v)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, values: dict) -> str:
        # values.data 是 pydantic v2 的方式访问其他字段
        data = getattr(values, "data", None) or {}
        new_pwd = data.get("new_password") if isinstance(data, dict) else None
        if new_pwd and v != new_pwd:
            raise ValueError("两次输入的密码不一致")
        return v
