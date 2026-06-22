"""
成绩 Schema
"""
from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class ScoreCreate(BaseModel):
    student_id: int = Field(..., description="学生ID")
    exam_id: int = Field(..., description="考试ID")
    course_id: int = Field(..., description="课程ID")
    score: Optional[Decimal] = Field(default=None, description="分数")
    remark: Optional[str] = Field(default=None, max_length=255)
    scorer_id: Optional[int] = Field(default=None, description="录入人ID")


class ScoreUpdate(BaseModel):
    score: Optional[Decimal] = None
    remark: Optional[str] = Field(default=None, max_length=255)


class ScoreOut(BaseModel):
    id: int
    student_id: int
    exam_id: int
    course_id: int
    score: Optional[Decimal] = None
    grade: Optional[str] = None
    rank_in_class: Optional[int] = None
    remark: Optional[str] = None
    scorer_id: Optional[int] = None
    created_at: datetime
    student_name: Optional[str] = None
    student_no: Optional[str] = None
    course_name: Optional[str] = None
    exam_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ScoreBatchCreate(BaseModel):
    """批量录入成绩"""
    exam_id: int
    course_id: int
    scores: list[ScoreCreate]
