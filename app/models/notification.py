"""
Notification model for system messages and workflow reminders.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Notification(TimestampMixin, Base):
    """User notification."""
    __tablename__ = "notification"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="Recipient user ID")
    title = Column(String(200), nullable=False, comment="Title")
    content = Column(Text, nullable=True, comment="Content")
    category = Column(String(50), nullable=False, default="system", index=True, comment="Category")
    related_type = Column(String(50), nullable=True, comment="Related entity type")
    related_id = Column(Integer, nullable=True, comment="Related entity ID")
    is_read = Column(Boolean, nullable=False, default=False, index=True, comment="Read flag")
    read_at = Column(DateTime, nullable=True, comment="Read time")

    user = relationship("User")
