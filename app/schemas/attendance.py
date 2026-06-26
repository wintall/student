"""
Attendance module schemas.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


PERSON_TYPES = {"student", "teacher"}
PERIOD_TYPES = {"day", "morning", "afternoon", "course", "custom"}
ATTENDANCE_STATUSES = {"normal", "late", "early_leave", "absent", "leave", "official", "holiday", "manual"}


class AttendanceRecordCreate(BaseModel):
    person_type: str = Field(..., description="student/teacher")
    user_id: Optional[int] = Field(default=None, description="User ID; optional when student_id/teacher_id is supplied")
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    attendance_date: date
    period_type: str = Field(default="day")
    course_schedule_id: Optional[int] = None
    checkin_time: Optional[datetime] = None
    checkout_time: Optional[datetime] = None
    status: str = Field(default="normal")
    remark: Optional[str] = Field(default=None, max_length=500)

    @field_validator("person_type")
    @classmethod
    def validate_person_type(cls, value: str) -> str:
        if value not in PERSON_TYPES:
            raise ValueError("考勤人员类型不正确")
        return value

    @field_validator("period_type")
    @classmethod
    def validate_period_type(cls, value: str) -> str:
        if value not in PERIOD_TYPES:
            raise ValueError("考勤时段类型不正确")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in ATTENDANCE_STATUSES:
            raise ValueError("考勤状态不正确")
        return value


class AttendanceRecordUpdate(BaseModel):
    attendance_date: Optional[date] = None
    period_type: Optional[str] = None
    course_schedule_id: Optional[int] = None
    checkin_time: Optional[datetime] = None
    checkout_time: Optional[datetime] = None
    status: Optional[str] = None
    remark: Optional[str] = Field(default=None, max_length=500)

    @field_validator("period_type")
    @classmethod
    def validate_period_type(cls, value: Optional[str]) -> Optional[str]:
        if value and value not in PERIOD_TYPES:
            raise ValueError("考勤时段类型不正确")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value and value not in ATTENDANCE_STATUSES:
            raise ValueError("考勤状态不正确")
        return value


class AttendanceRecordOut(BaseModel):
    id: int
    person_type: str
    user_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    clazz_id: Optional[int] = None
    department_id: Optional[int] = None
    attendance_date: date
    period_type: str
    course_schedule_id: Optional[int] = None
    checkin_time: Optional[datetime] = None
    checkout_time: Optional[datetime] = None
    status: str
    source: str
    leave_request_id: Optional[int] = None
    remark: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
