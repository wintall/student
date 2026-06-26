"""
Schemas for terms, classrooms and course schedules.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TermCreate(BaseModel):
    name: str = Field(..., max_length=100)
    academic_year: str = Field(..., max_length=20)
    semester: int = Field(..., ge=1, le=3)
    start_date: date
    end_date: date
    week_count: int = Field(..., ge=1, le=60)
    is_current: bool = False
    status: int = Field(default=1)
    remark: Optional[str] = None


class TermUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    academic_year: Optional[str] = Field(default=None, max_length=20)
    semester: Optional[int] = Field(default=None, ge=1, le=3)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    week_count: Optional[int] = Field(default=None, ge=1, le=60)
    is_current: Optional[bool] = None
    status: Optional[int] = None
    remark: Optional[str] = None


class TermOut(BaseModel):
    id: int
    name: str
    academic_year: str
    semester: int
    start_date: date
    end_date: date
    week_count: int
    is_current: bool
    status: int
    remark: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassroomCreate(BaseModel):
    name: str = Field(..., max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    room_no: Optional[str] = Field(default=None, max_length=50)
    campus: Optional[str] = Field(default=None, max_length=100)
    capacity: int = Field(default=0, ge=0)
    room_type: str = Field(default="normal", max_length=30)
    status: int = Field(default=1)
    remark: Optional[str] = None


class ClassroomUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    room_no: Optional[str] = Field(default=None, max_length=50)
    campus: Optional[str] = Field(default=None, max_length=100)
    capacity: Optional[int] = Field(default=None, ge=0)
    room_type: Optional[str] = Field(default=None, max_length=30)
    status: Optional[int] = None
    remark: Optional[str] = None


class ClassroomOut(BaseModel):
    id: int
    name: str
    building: Optional[str] = None
    room_no: Optional[str] = None
    campus: Optional[str] = None
    capacity: int
    room_type: str
    status: int
    remark: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseScheduleCreate(BaseModel):
    term_id: int
    course_id: int
    clazz_id: int
    teacher_id: int
    classroom_id: Optional[int] = None
    weekday: int = Field(..., ge=1, le=7)
    start_section: int = Field(..., ge=1, le=20)
    end_section: int = Field(..., ge=1, le=20)
    start_week: int = Field(..., ge=1, le=60)
    end_week: int = Field(..., ge=1, le=60)
    week_type: str = Field(default="all", max_length=10)
    schedule_type: str = Field(default="normal", max_length=20)
    status: int = Field(default=1)
    remark: Optional[str] = None


class CourseScheduleUpdate(BaseModel):
    term_id: Optional[int] = None
    course_id: Optional[int] = None
    clazz_id: Optional[int] = None
    teacher_id: Optional[int] = None
    classroom_id: Optional[int] = None
    weekday: Optional[int] = Field(default=None, ge=1, le=7)
    start_section: Optional[int] = Field(default=None, ge=1, le=20)
    end_section: Optional[int] = Field(default=None, ge=1, le=20)
    start_week: Optional[int] = Field(default=None, ge=1, le=60)
    end_week: Optional[int] = Field(default=None, ge=1, le=60)
    week_type: Optional[str] = Field(default=None, max_length=10)
    schedule_type: Optional[str] = Field(default=None, max_length=20)
    status: Optional[int] = None
    remark: Optional[str] = None


class CourseScheduleOut(BaseModel):
    id: int
    term_id: int
    course_id: int
    clazz_id: int
    teacher_id: int
    classroom_id: Optional[int] = None
    weekday: int
    start_section: int
    end_section: int
    start_week: int
    end_week: int
    week_type: str
    schedule_type: str
    status: int
    remark: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
