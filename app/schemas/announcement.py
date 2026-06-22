"""
公告 Schema
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=200, description="公告标题")
    content: str = Field(..., description="公告内容")
    type: int = Field(..., description="1=通知 2=活动 3=紧急")
    is_top: bool = Field(default=False, description="是否置顶")
    status: int = Field(default=1, description="1=已发布 2=草稿 0=已撤回")


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    type: Optional[int] = None
    is_top: Optional[bool] = None
    status: Optional[int] = None


class AnnouncementOut(BaseModel):
    id: int
    title: str
    content: str
    type: int
    publisher_id: int
    is_top: bool
    status: int
    published_at: Optional[datetime] = None
    created_at: datetime
    publisher_name: Optional[str] = None
    is_read: Optional[bool] = None
    read_count: Optional[int] = None

    model_config = {"from_attributes": True}
