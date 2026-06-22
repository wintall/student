"""
课程 Schema
"""
from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(..., max_length=100, description="课程名称")
    code: str = Field(..., max_length=50, description="课程代码")
    credit: Decimal = Field(..., description="学分")
    hours: int = Field(..., description="学时")
    course_type: int = Field(..., description="1=必修 2=选修 3=公共课")
    department_id: int = Field(..., description="开设院系ID")
    teacher_id: Optional[int] = Field(default=None, description="授课教师ID")
    description: Optional[str] = None
    status: int = Field(default=1)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    code: Optional[str] = Field(default=None, max_length=50)
    credit: Optional[Decimal] = None
    hours: Optional[int] = None
    course_type: Optional[int] = None
    department_id: Optional[int] = None
    teacher_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = None


class CourseOut(BaseModel):
    id: int
    name: str
    code: str
    credit: Decimal
    hours: int
    course_type: int
    department_id: int
    teacher_id: Optional[int] = None
    description: Optional[str] = None
    status: int
    created_at: datetime
    department_name: Optional[str] = None
    teacher_name: Optional[str] = None

    model_config = {"from_attributes": True}
