"""
请假模块 Schema
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


LEAVE_TYPES = {"sick", "personal", "official", "funeral", "marriage", "maternity", "other"}
APPLICANT_TYPES = {"student", "teacher"}


class LeaveRequestCreate(BaseModel):
    applicant_type: Optional[str] = Field(default=None, description="student/teacher，可不传由后端推断")
    leave_type: str = Field(..., description="请假类型")
    start_time: datetime
    end_time: datetime
    reason: str = Field(..., min_length=1, max_length=1000)
    destination: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    emergency_contact: Optional[str] = Field(default=None, max_length=100)
    attachment_url: Optional[str] = Field(default=None, max_length=500)
    remark: Optional[str] = Field(default=None, max_length=255)

    @field_validator("leave_type")
    @classmethod
    def validate_leave_type(cls, value: str) -> str:
        if value not in LEAVE_TYPES:
            raise ValueError("请假类型不正确")
        return value

    @field_validator("applicant_type")
    @classmethod
    def validate_applicant_type(cls, value: Optional[str]) -> Optional[str]:
        if value and value not in APPLICANT_TYPES:
            raise ValueError("申请人类型不正确")
        return value


class LeaveRequestReview(BaseModel):
    review_comment: Optional[str] = Field(default=None, max_length=500)


class LeaveRequestQuery(BaseModel):
    status: Optional[str] = None
    applicant_type: Optional[str] = None
    leave_type: Optional[str] = None
    keyword: Optional[str] = None


class LeaveRequestOut(BaseModel):
    id: int
    applicant_user_id: int
    applicant_type: str
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    clazz_id: Optional[int] = None
    department_id: Optional[int] = None
    leave_type: str
    start_time: datetime
    end_time: datetime
    duration_hours: float
    reason: str
    destination: Optional[str] = None
    contact_phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    attachment_url: Optional[str] = None
    remark: Optional[str] = None
    status: str
    reviewer_id: Optional[int] = None
    reviewer_role: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
