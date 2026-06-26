"""add notification table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-26 15:20:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="Recipient user ID"),
        sa.Column("title", sa.String(length=200), nullable=False, comment="Title"),
        sa.Column("content", sa.Text(), nullable=True, comment="Content"),
        sa.Column("category", sa.String(length=50), nullable=False, comment="Category"),
        sa.Column("related_type", sa.String(length=50), nullable=True, comment="Related entity type"),
        sa.Column("related_id", sa.Integer(), nullable=True, comment="Related entity ID"),
        sa.Column("is_read", sa.Boolean(), nullable=False, comment="Read flag"),
        sa.Column("read_at", sa.DateTime(), nullable=True, comment="Read time"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Updated at"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notification_user", "notification", ["user_id"], unique=False)
    op.create_index("idx_notification_category", "notification", ["category"], unique=False)
    op.create_index("idx_notification_read", "notification", ["is_read"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_notification_read", table_name="notification")
    op.drop_index("idx_notification_category", table_name="notification")
    op.drop_index("idx_notification_user", table_name="notification")
    op.drop_table("notification")
