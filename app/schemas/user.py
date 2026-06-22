"""
用户管理 Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


def _check_password(value: Optional[str]) -> Optional[str]:
    """统一的密码强度校验"""
    if not value:
        return value
    if len(value) < 8:
        raise ValueError("密码长度至少为8位")
    has_digit = any(c.isdigit() for c in value)
    has_alpha = any(c.isalpha() for c in value)
    if not (has_digit and has_alpha):
        raise ValueError("密码必须同时包含字母和数字")
    return value


class UserCreate(BaseModel):
    """创建用户"""
    username: str = Field(..., max_length=50, description="登录用户名")
    password: Optional[str] = Field(default=None, description="密码(至少8位,需包含字母和数字)")
    real_name: str = Field(..., max_length=50, description="真实姓名")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    email: Optional[str] = Field(default=None, max_length=100, description="邮箱")
    id_card: Optional[str] = Field(default=None, max_length=18, description="身份证号")
    status: int = Field(default=1, description="1=正常 0=禁用")
    role_ids: List[int] = Field(default=[], description="角色ID列表")

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: Optional[str]) -> Optional[str]:
        return _check_password(v)


class UserUpdate(BaseModel):
    """更新用户"""
    real_name: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=100)
    id_card: Optional[str] = Field(default=None, max_length=18)
    avatar: Optional[str] = Field(default=None, max_length=255)
    status: Optional[int] = None
    role_ids: Optional[List[int]] = None
    password: Optional[str] = Field(default=None, description="管理员重置密码(至少8位,需包含字母和数字)")

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: Optional[str]) -> Optional[str]:
        return _check_password(v)


class UserOut(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    real_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    id_card: Optional[str] = None
    avatar: Optional[str] = None
    status: int
    must_change_password: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    role_ids: List[int] = []
    role_names: List[str] = []

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    """用户简要信息（列表展示）"""
    id: int
    username: str
    real_name: str
    phone: Optional[str] = None
    status: int
    role_names: List[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}
