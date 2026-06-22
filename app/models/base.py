"""
ORM 基类和通用 Mixin
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明基类"""
    pass


class TimestampMixin:
    """时间戳 Mixin：created_at + updated_at"""
    created_at = Column(DateTime, default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")


class SoftDeleteMixin(TimestampMixin):
    """软删除 Mixin：is_deleted + deleted_at + created_at + updated_at"""
    is_deleted = Column(Boolean, default=False, nullable=False, comment="软删除标记")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.now()
