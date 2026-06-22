"""
班级 Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ClazzCreate(BaseModel):
    name: str = Field(..., max_length=50, description="班级名称")
    code: str = Field(..., max_length=50, description="班级代码")
    department_id: int = Field(..., description="所属院系ID")
    grade: str = Field(..., max_length=10, description="年级")
    counselor_id: Optional[int] = Field(default=None, description="辅导员ID")
    status: int = Field(default=1)


class ClazzUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    code: Optional[str] = Field(default=None, max_length=50)
    department_id: Optional[int] = None
    grade: Optional[str] = Field(default=None, max_length=10)
    counselor_id: Optional[int] = None
    status: Optional[int] = None


class ClazzOut(BaseModel):
    id: int
    name: str
    code: str
    department_id: int
    grade: str
    counselor_id: Optional[int] = None
    status: int
    created_at: datetime
    department_name: Optional[str] = None
    counselor_name: Optional[str] = None

    model_config = {"from_attributes": True}
