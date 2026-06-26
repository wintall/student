from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.models.base import Base


class Conversation(Base):
    """
    对话历史表
    """
    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)  # 支持匿名用户，可为空
    session_id = Column(String(64), index=True, nullable=False)  # 会话标识
    messages = Column(JSON, default=[])  # 存储对话历史消息
    book_codes = Column(JSON, default=[])  # 当前对话关注的书籍
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "messages": self.messages,
            "book_codes": self.book_codes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }