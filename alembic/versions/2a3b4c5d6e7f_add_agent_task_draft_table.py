"""add agent task draft table

Revision ID: 2a3b4c5d6e7f
Revises: 9f1a2b3c4d5e
Create Date: 2026-06-27 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "2a3b4c5d6e7f"
down_revision = "9f1a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_task_draft",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="所属用户"),
        sa.Column("session_id", sa.String(length=64), nullable=True, comment="会话ID"),
        sa.Column("module_code", sa.String(length=50), nullable=False, server_default="campus_agent", comment="能力模块"),
        sa.Column("mode", sa.String(length=50), nullable=True, comment="助手模式"),
        sa.Column("tool_code", sa.String(length=80), nullable=False, comment="工具编码"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active", comment="状态"),
        sa.Column("args_json", sa.Text(), nullable=False, comment="已收集参数JSON"),
        sa.Column("missing_fields_json", sa.Text(), nullable=True, comment="缺失字段JSON"),
        sa.Column("candidates_json", sa.Text(), nullable=True, comment="候选项JSON"),
        sa.Column("message", sa.Text(), nullable=True, comment="最近一次追问或说明"),
        sa.Column("expires_at", sa.DateTime(), nullable=False, comment="过期时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_task_draft_user_id"), "agent_task_draft", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_task_draft_session_id"), "agent_task_draft", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_task_draft_module_code"), "agent_task_draft", ["module_code"], unique=False)
    op.create_index(op.f("ix_agent_task_draft_tool_code"), "agent_task_draft", ["tool_code"], unique=False)
    op.create_index(op.f("ix_agent_task_draft_status"), "agent_task_draft", ["status"], unique=False)
    op.create_index(op.f("ix_agent_task_draft_expires_at"), "agent_task_draft", ["expires_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_agent_task_draft_expires_at"), table_name="agent_task_draft")
    op.drop_index(op.f("ix_agent_task_draft_status"), table_name="agent_task_draft")
    op.drop_index(op.f("ix_agent_task_draft_tool_code"), table_name="agent_task_draft")
    op.drop_index(op.f("ix_agent_task_draft_module_code"), table_name="agent_task_draft")
    op.drop_index(op.f("ix_agent_task_draft_session_id"), table_name="agent_task_draft")
    op.drop_index(op.f("ix_agent_task_draft_user_id"), table_name="agent_task_draft")
    op.drop_table("agent_task_draft")
