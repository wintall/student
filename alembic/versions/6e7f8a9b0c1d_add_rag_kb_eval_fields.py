"""add rag knowledge base evaluation fields

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-06-30 16:55:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "6e7f8a9b0c1d"
down_revision = "5d6e7f8a9b0c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rag_knowledge_base", sa.Column("eval_score", sa.Integer(), nullable=True, comment="Latest evaluation score 0-100"))
    op.add_column("rag_knowledge_base", sa.Column("eval_recall", sa.Integer(), nullable=True, comment="Latest Recall@K percent"))
    op.add_column("rag_knowledge_base", sa.Column("eval_precision", sa.Integer(), nullable=True, comment="Latest Precision@K percent"))
    op.add_column("rag_knowledge_base", sa.Column("eval_f1", sa.Integer(), nullable=True, comment="Latest F1 percent"))
    op.add_column("rag_knowledge_base", sa.Column("eval_hit", sa.Integer(), nullable=True, comment="Latest Hit@1 percent"))
    op.add_column("rag_knowledge_base", sa.Column("eval_mrr", sa.Integer(), nullable=True, comment="Latest MRR percent"))
    op.add_column("rag_knowledge_base", sa.Column("eval_sample_count", sa.Integer(), nullable=False, server_default="0", comment="Latest evaluation sample count"))
    op.add_column("rag_knowledge_base", sa.Column("evaluated_at", sa.DateTime(), nullable=True, comment="Latest evaluation time"))


def downgrade():
    op.drop_column("rag_knowledge_base", "evaluated_at")
    op.drop_column("rag_knowledge_base", "eval_sample_count")
    op.drop_column("rag_knowledge_base", "eval_mrr")
    op.drop_column("rag_knowledge_base", "eval_hit")
    op.drop_column("rag_knowledge_base", "eval_f1")
    op.drop_column("rag_knowledge_base", "eval_precision")
    op.drop_column("rag_knowledge_base", "eval_recall")
    op.drop_column("rag_knowledge_base", "eval_score")
