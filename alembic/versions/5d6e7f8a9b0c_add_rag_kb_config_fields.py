"""add rag knowledge base config fields

Revision ID: 5d6e7f8a9b0c
Revises: 4c5d6e7f8a9b
Create Date: 2026-06-30 16:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "5d6e7f8a9b0c"
down_revision = "4c5d6e7f8a9b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rag_knowledge_base", sa.Column("chunk_strategy", sa.String(length=30), nullable=False, server_default="paragraph", comment="paragraph/fixed"))
    op.add_column("rag_knowledge_base", sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="700", comment="Chunk size in chars"))
    op.add_column("rag_knowledge_base", sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="100", comment="Chunk overlap in chars"))
    op.add_column("rag_knowledge_base", sa.Column("embedding_model", sa.String(length=100), nullable=False, server_default="moka-ai/m3e-base", comment="Embedding model name"))
    op.add_column("rag_knowledge_base", sa.Column("vector_store", sa.String(length=30), nullable=False, server_default="milvus", comment="Vector store"))
    op.add_column("rag_knowledge_base", sa.Column("similarity_metric", sa.String(length=20), nullable=False, server_default="COSINE", comment="COSINE/IP/L2"))
    op.add_column("rag_knowledge_base", sa.Column("retrieval_mode", sa.String(length=30), nullable=False, server_default="hybrid", comment="vector/keyword/hybrid"))
    op.add_column("rag_knowledge_base", sa.Column("default_top_k", sa.Integer(), nullable=False, server_default="5", comment="Default search top k"))
    op.add_column("rag_knowledge_base", sa.Column("default_min_score", sa.Integer(), nullable=False, server_default="45", comment="Default min score percent"))
    op.add_column("rag_knowledge_base", sa.Column("vector_weight", sa.Integer(), nullable=False, server_default="62", comment="Vector score weight percent"))
    op.add_column("rag_knowledge_base", sa.Column("bm25_weight", sa.Integer(), nullable=False, server_default="28", comment="BM25 score weight percent"))
    op.add_column("rag_knowledge_base", sa.Column("title_weight", sa.Integer(), nullable=False, server_default="10", comment="Title score weight percent"))
    op.add_column("rag_knowledge_base", sa.Column("core_weight", sa.Integer(), nullable=False, server_default="35", comment="Core term score extra weight percent"))


def downgrade():
    op.drop_column("rag_knowledge_base", "core_weight")
    op.drop_column("rag_knowledge_base", "title_weight")
    op.drop_column("rag_knowledge_base", "bm25_weight")
    op.drop_column("rag_knowledge_base", "vector_weight")
    op.drop_column("rag_knowledge_base", "default_min_score")
    op.drop_column("rag_knowledge_base", "default_top_k")
    op.drop_column("rag_knowledge_base", "retrieval_mode")
    op.drop_column("rag_knowledge_base", "similarity_metric")
    op.drop_column("rag_knowledge_base", "vector_store")
    op.drop_column("rag_knowledge_base", "embedding_model")
    op.drop_column("rag_knowledge_base", "chunk_overlap")
    op.drop_column("rag_knowledge_base", "chunk_size")
    op.drop_column("rag_knowledge_base", "chunk_strategy")
