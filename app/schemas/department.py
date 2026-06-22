"""
院系 Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., max_length=100, description="院系名称")
    code: str = Field(..., max_length=50, description="院系代码")
    description: Optional[str] = None
    status: int = Field(default=1)


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    code: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    status: Optional[int] = None


class DepartmentOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    status: int
    created_at: datetime

    model_config = {"from_attributes": True}
