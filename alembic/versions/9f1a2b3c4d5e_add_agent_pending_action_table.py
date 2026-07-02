"""add agent pending action table

Revision ID: 9f1a2b3c4d5e
Revises: e3f4a5b6c7d8, f7c8d9e0a1b2
Create Date: 2026-06-27 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "9f1a2b3c4d5e"
down_revision = ("e3f4a5b6c7d8", "f7c8d9e0a1b2")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_pending_action",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="发起用户"),
        sa.Column("session_id", sa.String(length=64), nullable=True, comment="会话ID"),
        sa.Column("tool_code", sa.String(length=80), nullable=False, comment="工具编码"),
        sa.Column("risk", sa.String(length=20), nullable=False, server_default="medium", comment="风险等级"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending", comment="状态"),
        sa.Column("args_json", sa.Text(), nullable=False, comment="工具参数JSON"),
        sa.Column("summary", sa.Text(), nullable=True, comment="确认摘要"),
        sa.Column("result_json", sa.Text(), nullable=True, comment="执行结果JSON"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("expires_at", sa.DateTime(), nullable=False, comment="过期时间"),
        sa.Column("executed_at", sa.DateTime(), nullable=True, comment="执行时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_pending_action_user_id"), "agent_pending_action", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_pending_action_session_id"), "agent_pending_action", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_pending_action_tool_code"), "agent_pending_action", ["tool_code"], unique=False)
    op.create_index(op.f("ix_agent_pending_action_status"), "agent_pending_action", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_agent_pending_action_status"), table_name="agent_pending_action")
    op.drop_index(op.f("ix_agent_pending_action_tool_code"), table_name="agent_pending_action")
    op.drop_index(op.f("ix_agent_pending_action_session_id"), table_name="agent_pending_action")
    op.drop_index(op.f("ix_agent_pending_action_user_id"), table_name="agent_pending_action")
    op.drop_table("agent_pending_action")
