"""
角色与权限 Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    """创建角色"""
    code: str = Field(..., max_length=50, description="角色代码")
    name: str = Field(..., max_length=50, description="角色名称")
    description: Optional[str] = Field(default=None, max_length=255)
    menu_ids: List[int] = Field(default=[], description="菜单ID列表")


class RoleUpdate(BaseModel):
    """更新角色"""
    name: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=255)
    menu_ids: Optional[List[int]] = None


class RoleOut(BaseModel):
    """角色信息响应"""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    menu_ids: List[int] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MenuCreate(BaseModel):
    """创建菜单"""
    parent_id: Optional[int] = Field(default=None, description="父菜单ID")
    name: str = Field(..., max_length=50, description="菜单名称")
    code: str = Field(..., max_length=100, description="权限标识")
    type: int = Field(..., description="1=目录 2=菜单 3=按钮")
    path: Optional[str] = Field(default=None, max_length=200)
    icon: Optional[str] = Field(default=None, max_length=50)
    sort_order: int = Field(default=0)
    status: int = Field(default=1)


class MenuUpdate(BaseModel):
    """更新菜单"""
    parent_id: Optional[int] = None
    name: Optional[str] = Field(default=None, max_length=50)
    code: Optional[str] = Field(default=None, max_length=100)
    type: Optional[int] = None
    path: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[int] = None


class MenuOut(BaseModel):
    """菜单信息响应"""
    id: int
    parent_id: Optional[int] = None
    name: str
    code: str
    type: int
    path: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int
    status: int
    created_at: datetime
    children: List["MenuOut"] = []

    model_config = {"from_attributes": True}
