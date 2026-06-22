"""
RAG 相关模型：知识库书籍 + 片段
- 书籍表（元数据管理），片段表（每段原文 + 元数据，可在MySQL存原始文本）
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin


class RagBook(TimestampMixin, Base):
    """RAG 知识库书籍表"""
    __tablename__ = "rag_book"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    code = Column(String(32), unique=True, nullable=False, comment="书籍代码 (如 xiyouji")
    name = Column(String(64), nullable=False, comment="书籍名称")
    author = Column(String(64), nullable=True, comment="作者")
    dynasty = Column(String(32), nullable=True, comment="朝代")
    summary = Column(String(512), nullable=True, comment="书籍简介")
    total_chapters = Column(Integer, default=0, comment="总回数/章节")
    total_sections = Column(Integer, default=0, comment="已入库的段落数")
    status = Column(SmallInteger, default=1, comment="1=正常, 0=禁用")


class RagSection(TimestampMixin, Base):
    """RAG 片段表（每段原文）"""
    __tablename__ = "rag_section"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    book_id = Column(Integer, ForeignKey("rag_book.id"), nullable=False, comment="所属书籍ID")
    chapter_no = Column(Integer, nullable=True, comment="第几回/章")
    chapter_title = Column(String(128), nullable=True, comment="回目/章标题")
    section_no = Column(Integer, default=0, comment="段落编号")
    text = Column(Text, nullable=False, comment="段落原文")
    keywords = Column(String(512), nullable=True, comment="关键词/人物、事件标签")
    status = Column(SmallInteger, default=1, comment="1=正常 0=禁用")

    book = relationship("RagBook")

    __table_args__ = (
        Index("idx_rag_section_book_chapter", "book_id", "chapter_no"),
    )
