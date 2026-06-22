"""
邮件系统 Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class EmailSendRequest(BaseModel):
    """发送邮件请求"""
    recipient_email: str = Field(..., description="收件人邮箱")
    subject: str = Field(..., min_length=1, max_length=500, description="邮件主题")
    body: str = Field(default="", description="邮件正文")


class EmailAttachmentOut(BaseModel):
    """附件信息输出"""
    id: int
    file_name: str
    file_size: int
    mime_type: Optional[str] = None

    model_config = {"from_attributes": True}


class EmailOut(BaseModel):
    """邮件列表/详情输出"""
    id: int
    subject: str
    body: Optional[str] = None
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    recipient_email: str
    recipient_user_id: Optional[int] = None
    is_external: bool
    status: str
    is_read: bool
    sent_at: str
    attachments: List[EmailAttachmentOut] = []

    model_config = {"from_attributes": True}


class UserSuggestion(BaseModel):
    """用户选择建议（写信时搜索收件人用）"""
    id: int
    username: str
    real_name: str
    email: str