"""
公告模块模型：Announcement, AnnouncementRead
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Announcement(SoftDeleteMixin, Base):
    """公告表"""
    __tablename__ = "announcement"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    title = Column(String(200), nullable=False, comment="公告标题")
    content = Column(Text, nullable=False, comment="公告内容")
    type = Column(SmallInteger, nullable=False, comment="1=通知 2=活动 3=紧急")
    publisher_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="发布人")
    is_top = Column(Boolean, default=False, nullable=False, comment="是否置顶")
    status = Column(SmallInteger, default=1, nullable=False, comment="1=已发布 2=草稿 0=已撤回")
    published_at = Column(DateTime, nullable=True, comment="发布时间")

    # relationships
    publisher = relationship("User")
    reads = relationship("AnnouncementRead", back_populates="announcement", cascade="all, delete-orphan")


class AnnouncementRead(TimestampMixin, Base):
    """公告已读记录表"""
    __tablename__ = "announcement_read"
    __table_args__ = (UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    announcement_id = Column(Integer, ForeignKey("announcement.id"), nullable=False, comment="公告ID")
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, comment="阅读人")
    read_at = Column(DateTime, nullable=False, comment="阅读时间")

    announcement = relationship("Announcement", back_populates="reads")
