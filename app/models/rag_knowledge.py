from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class RagKnowledgeBase(SoftDeleteMixin, Base):
    """Persistent user knowledge base metadata."""

    __tablename__ = "rag_knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    name = Column(String(100), nullable=False, comment="Knowledge base name")
    description = Column(String(512), nullable=True, comment="Description")
    owner_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="Owner user id")
    scope_type = Column(String(20), nullable=False, default="personal", comment="personal/public/class/course")
    scope_id = Column(Integer, nullable=True, comment="Optional scope id")
    status = Column(SmallInteger, nullable=False, default=1, comment="1=enabled,0=disabled")
    document_count = Column(Integer, nullable=False, default=0, comment="Active document count")
    chunk_count = Column(Integer, nullable=False, default=0, comment="Active chunk count")
    chunk_strategy = Column(String(30), nullable=False, default="paragraph", comment="paragraph/fixed")
    chunk_size = Column(Integer, nullable=False, default=700, comment="Chunk size in chars")
    chunk_overlap = Column(Integer, nullable=False, default=100, comment="Chunk overlap in chars")
    embedding_model = Column(String(100), nullable=False, default="moka-ai/m3e-base", comment="Embedding model name")
    vector_store = Column(String(30), nullable=False, default="milvus", comment="Vector store")
    similarity_metric = Column(String(20), nullable=False, default="COSINE", comment="COSINE/IP/L2")
    retrieval_mode = Column(String(30), nullable=False, default="hybrid", comment="vector/keyword/hybrid")
    default_top_k = Column(Integer, nullable=False, default=5, comment="Default search top k")
    default_min_score = Column(Integer, nullable=False, default=45, comment="Default min score percent")
    vector_weight = Column(Integer, nullable=False, default=62, comment="Vector score weight percent")
    bm25_weight = Column(Integer, nullable=False, default=28, comment="BM25 score weight percent")
    title_weight = Column(Integer, nullable=False, default=10, comment="Title score weight percent")
    core_weight = Column(Integer, nullable=False, default=35, comment="Core term score extra weight percent")
    eval_score = Column(Integer, nullable=True, comment="Latest evaluation score 0-100")
    eval_recall = Column(Integer, nullable=True, comment="Latest Recall@K percent")
    eval_precision = Column(Integer, nullable=True, comment="Latest Precision@K percent")
    eval_f1 = Column(Integer, nullable=True, comment="Latest F1 percent")
    eval_hit = Column(Integer, nullable=True, comment="Latest Hit@1 percent")
    eval_mrr = Column(Integer, nullable=True, comment="Latest MRR percent")
    eval_sample_count = Column(Integer, nullable=False, default=0, comment="Latest evaluation sample count")
    evaluated_at = Column(DateTime, nullable=True, comment="Latest evaluation time")

    documents = relationship("RagDocument", back_populates="knowledge_base")

    __table_args__ = (
        Index("idx_rag_kb_owner_scope", "owner_id", "scope_type", "scope_id"),
    )


class RagDocument(SoftDeleteMixin, Base):
    """A source document imported into a knowledge base."""

    __tablename__ = "rag_document"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    kb_id = Column(Integer, ForeignKey("rag_knowledge_base.id"), nullable=False, index=True, comment="Knowledge base id")
    owner_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="Owner user id")
    title = Column(String(200), nullable=False, comment="Document title")
    source_type = Column(String(20), nullable=False, comment="text/upload/path")
    file_name = Column(String(255), nullable=True, comment="Original file name")
    file_path = Column(String(500), nullable=True, comment="Stored file path or allowed local path")
    file_ext = Column(String(20), nullable=True, comment="File extension")
    file_hash = Column(String(64), nullable=True, index=True, comment="SHA256 hash")
    status = Column(String(20), nullable=False, default="pending", index=True, comment="pending/processing/completed/failed/deleted")
    error_message = Column(Text, nullable=True, comment="Last processing error")
    chunk_count = Column(Integer, nullable=False, default=0, comment="Chunk count")
    char_count = Column(Integer, nullable=False, default=0, comment="Character count")

    knowledge_base = relationship("RagKnowledgeBase", back_populates="documents")
    chunks = relationship("RagDocumentChunk", back_populates="document")

    __table_args__ = (
        Index("idx_rag_doc_kb_status", "kb_id", "status"),
        Index("idx_rag_doc_owner_status", "owner_id", "status"),
    )


class RagDocumentChunk(TimestampMixin, Base):
    """Chunk text stored in MySQL and mirrored as vector in Milvus."""

    __tablename__ = "rag_document_chunk"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Primary key")
    kb_id = Column(Integer, ForeignKey("rag_knowledge_base.id"), nullable=False, index=True, comment="Knowledge base id")
    document_id = Column(Integer, ForeignKey("rag_document.id"), nullable=False, index=True, comment="Document id")
    owner_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True, comment="Owner user id")
    chunk_no = Column(Integer, nullable=False, comment="Chunk sequence number")
    content = Column(Text, nullable=False, comment="Chunk content")
    content_hash = Column(String(64), nullable=False, index=True, comment="SHA256 hash")
    char_count = Column(Integer, nullable=False, default=0, comment="Character count")
    token_count = Column(Integer, nullable=False, default=0, comment="Approx token count")
    status = Column(String(20), nullable=False, default="completed", index=True, comment="completed/deleted")
    is_deleted = Column(Boolean, default=False, nullable=False, comment="Soft delete flag")
    deleted_at = Column(DateTime, nullable=True, comment="Deleted at")

    document = relationship("RagDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_rag_chunk_kb_doc", "kb_id", "document_id"),
        Index("idx_rag_chunk_doc_no", "document_id", "chunk_no"),
    )
