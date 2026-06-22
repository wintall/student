"""
内部邮件系统模型
- EmailMessage: 邮件主表（收件箱/已发送统一存储
- EmailAttachment: 邮件附件
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class EmailMessage(Base):
    """邮件消息表"""
    __tablename__ = "email_message"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")

    # 发件人
    sender_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="发件人用户ID")
    sender_name = Column(String(100), nullable=True, comment="发件人显示名")
    sender_email = Column(String(200), nullable=True, comment="发件人邮箱")

    # 收件人
    recipient_email = Column(String(200), nullable=False, index=True, comment="收件人邮箱")
    recipient_user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True, comment="收件人用户ID（仅内部邮件）")

    # 内容
    subject = Column(String(500), nullable=False, comment="邮件主题")
    body = Column(Text, nullable=True, comment="邮件正文")

    # 状态
    is_external = Column(Boolean, default=False, nullable=False, comment="是否为外部邮件")
    status = Column(String(20), default="sent", nullable=False, comment="状态: draft/sent/failed/read")
    is_read = Column(Boolean, default=False, nullable=False, comment="是否已读")
    is_deleted_by_sender = Column(Boolean, default=False, nullable=False, comment="发件人删除")
    is_deleted_by_recipient = Column(Boolean, default=False, nullable=False, comment="收件人删除")

    # 元信息
    sent_at = Column(DateTime, default=datetime.now, nullable=False, comment="发送时间")

    # 关系
    attachments = relationship("EmailAttachment", back_populates="message", cascade="all, delete-orphan")


class EmailAttachment(Base):
    """邮件附件表"""
    __tablename__ = "email_attachment"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    message_id = Column(Integer, ForeignKey("email_message.id"), nullable=False, index=True, comment="邮件ID")

    file_name = Column(String(255), nullable=False, comment="显示文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_size = Column(Integer, default=0, nullable=False, comment="文件大小(字节)")
    mime_type = Column(String(100), nullable=True, comment="MIME 类型")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="上传时间")

    # 关系
    message = relationship("EmailMessage", back_populates="attachments")
