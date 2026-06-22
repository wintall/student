"""
考试 Schema
"""
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field


class ExamCreate(BaseModel):
    name: str = Field(..., max_length=100, description="考试名称")
    course_id: int = Field(..., description="课程ID")
    exam_type: int = Field(..., description="1=期中 2=期末 3=补考 4=测验")
    exam_date: date = Field(..., description="考试日期")
    exam_time: Optional[str] = Field(default=None, max_length=50, description="时间段")
    location: Optional[str] = Field(default=None, max_length=100)
    clazz_id: Optional[int] = Field(default=None, description="班级ID(NULL=全院)")
    description: Optional[str] = None
    status: int = Field(default=1)


class ExamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    course_id: Optional[int] = None
    exam_type: Optional[int] = None
    exam_date: Optional[date] = None
    exam_time: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=100)
    clazz_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = None


class ExamOut(BaseModel):
    id: int
    name: str
    course_id: int
    exam_type: int
    exam_date: date
    exam_time: Optional[str] = None
    location: Optional[str] = None
    clazz_id: Optional[int] = None
    description: Optional[str] = None
    status: int
    created_at: datetime
    course_name: Optional[str] = None
    clazz_name: Optional[str] = None

    model_config = {"from_attributes": True}
