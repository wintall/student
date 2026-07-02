"""add agent long term memory table

Revision ID: 4c5d6e7f8a9b
Revises: 3b4c5d6e7f8a
Create Date: 2026-06-29 21:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "4c5d6e7f8a9b"
down_revision = "3b4c5d6e7f8a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_long_term_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="所属用户"),
        sa.Column("module_code", sa.String(length=50), nullable=False, server_default="campus_agent", comment="能力模块"),
        sa.Column("memory_type", sa.String(length=50), nullable=False, server_default="event", comment="记忆类型"),
        sa.Column("content", sa.Text(), nullable=False, comment="记忆内容"),
        sa.Column("payload_json", sa.Text(), nullable=True, comment="结构化内容JSON"),
        sa.Column("importance", sa.SmallInteger(), nullable=False, server_default="1", comment="重要程度1-5"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active", comment="状态"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True, comment="最近召回时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_long_term_memory_user_id"), "agent_long_term_memory", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_long_term_memory_module_code"), "agent_long_term_memory", ["module_code"], unique=False)
    op.create_index(op.f("ix_agent_long_term_memory_memory_type"), "agent_long_term_memory", ["memory_type"], unique=False)
    op.create_index(op.f("ix_agent_long_term_memory_status"), "agent_long_term_memory", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_agent_long_term_memory_status"), table_name="agent_long_term_memory")
    op.drop_index(op.f("ix_agent_long_term_memory_memory_type"), table_name="agent_long_term_memory")
    op.drop_index(op.f("ix_agent_long_term_memory_module_code"), table_name="agent_long_term_memory")
    op.drop_index(op.f("ix_agent_long_term_memory_user_id"), table_name="agent_long_term_memory")
    op.drop_table("agent_long_term_memory")
