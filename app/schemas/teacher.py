"""
教职工 Schema
"""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field


class TeacherCreate(BaseModel):
    user_id: int = Field(..., description="关联用户ID")
    employee_no: str = Field(..., max_length=30, description="工号")
    name: str = Field(..., max_length=50, description="姓名")
    gender: int = Field(..., description="1=男 2=女")
    id_card: str = Field(..., max_length=18, description="身份证号")
    position: str = Field(..., max_length=50, description="岗位")
    title: Optional[str] = Field(default=None, max_length=50, description="职称")
    department_id: Optional[int] = Field(default=None, description="所属院系ID")
    entry_date: Optional[date] = Field(default=None, description="入职日期")
    status: int = Field(default=1)


class TeacherUpdate(BaseModel):
    employee_no: Optional[str] = Field(default=None, max_length=30)
    name: Optional[str] = Field(default=None, max_length=50)
    gender: Optional[int] = None
    id_card: Optional[str] = Field(default=None, max_length=18)
    position: Optional[str] = Field(default=None, max_length=50)
    title: Optional[str] = Field(default=None, max_length=50)
    department_id: Optional[int] = None
    entry_date: Optional[date] = None
    status: Optional[int] = None


class TeacherOut(BaseModel):
    id: int
    user_id: int
    employee_no: str
    name: str
    gender: int
    id_card: str
    position: str
    title: Optional[str] = None
    department_id: Optional[int] = None
    entry_date: Optional[date] = None
    status: int
    created_at: datetime
    department_name: Optional[str] = None
    username: Optional[str] = None

    model_config = {"from_attributes": True}
