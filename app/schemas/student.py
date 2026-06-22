"""
学生 Schema
"""
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    user_id: int = Field(..., description="关联用户ID")
    student_no: str = Field(..., max_length=30, description="学号")
    name: str = Field(..., max_length=50, description="姓名")
    gender: int = Field(..., description="1=男 2=女")
    id_card: str = Field(..., max_length=18, description="身份证号")
    clazz_id: int = Field(..., description="所属班级ID")
    enrollment_date: Optional[date] = Field(default=None, description="入学日期")
    status: int = Field(default=1)


class StudentUpdate(BaseModel):
    student_no: Optional[str] = Field(default=None, max_length=30)
    name: Optional[str] = Field(default=None, max_length=50)
    gender: Optional[int] = None
    id_card: Optional[str] = Field(default=None, max_length=18)
    clazz_id: Optional[int] = None
    enrollment_date: Optional[date] = None
    status: Optional[int] = None


class StudentOut(BaseModel):
    id: int
    user_id: int
    student_no: str
    name: str
    gender: int
    id_card: str
    clazz_id: int
    enrollment_date: Optional[date] = None
    status: int
    created_at: datetime
    clazz_name: Optional[str] = None
    department_name: Optional[str] = None
    username: Optional[str] = None

    model_config = {"from_attributes": True}
