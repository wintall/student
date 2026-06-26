"""add rag_qa_pair table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-22
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0d2e3af91e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rag_qa_pair',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('category', sa.String(length=32), nullable=True, comment='分类'),
        sa.Column('question', sa.String(length=255), nullable=False, comment='标准问题'),
        sa.Column('question_variants', sa.String(length=1024), nullable=True, comment='问题变体（分号分隔）'),
        sa.Column('answer', sa.Text(), nullable=False, comment='答案'),
        sa.Column('keywords', sa.String(length=255), nullable=True, comment='关键词'),
        sa.Column('source', sa.String(length=128), nullable=True, comment='来源/出处'),
        sa.Column('hit_count', sa.Integer(), server_default='0', nullable=False, comment='命中次数'),
        sa.Column('status', sa.SmallInteger(), server_default='1', nullable=False, comment='1=正常,0=禁用'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rag_qa_pair_id', 'rag_qa_pair', ['id'], unique=False)
    op.create_index('idx_rag_qa_category_status', 'rag_qa_pair', ['category', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_rag_qa_category_status', table_name='rag_qa_pair')
    op.drop_index('ix_rag_qa_pair_id', table_name='rag_qa_pair')
    op.drop_table('rag_qa_pair')
