"""
RAG 问答对模型
- 存储高频问题-标准答案对，用于快速回答（节省LLM调用）
- 支持关键词匹配 + 向量检索混合召回
"""
from sqlalchemy import Column, Integer, String, SmallInteger, Text, Index
from app.models.base import Base, TimestampMixin


class RagQaPair(TimestampMixin, Base):
    """RAG 问答对表"""
    __tablename__ = "rag_qa_pair"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    category = Column(String(32), nullable=True, index=True, comment="分类，如 xiyouji/sanguo/通用")
    question = Column(String(255), nullable=False, comment="标准问题（主问题）")
    question_variants = Column(String(1024), nullable=True, comment="问题变体（用分号;分隔，支持多种问法）")
    answer = Column(Text, nullable=False, comment="标准答案/回答内容")
    keywords = Column(String(255), nullable=True, comment="关键词标签，用逗号分隔")
    source = Column(String(128), nullable=True, comment="来源/出处，如 西游记第27回")
    hit_count = Column(Integer, default=0, comment="命中次数统计")
    status = Column(SmallInteger, default=1, comment="1=正常, 0=禁用")

    __table_args__ = (
        Index("idx_rag_qa_category_status", "category", "status"),
    )

    def to_dict(self):
        """返回字典格式"""
        return {
            "id": self.id,
            "category": self.category or "",
            "question": self.question,
            "question_variants": self.question_variants or "",
            "answer": self.answer,
            "keywords": self.keywords or "",
            "source": self.source or "",
            "hit_count": self.hit_count or 0,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
        }
