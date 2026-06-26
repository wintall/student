"""add schedule tables

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-06-26 12:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "term",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="Term name"),
        sa.Column("academic_year", sa.String(length=20), nullable=False, comment="Academic year"),
        sa.Column("semester", sa.SmallInteger(), nullable=False, comment="Semester number"),
        sa.Column("start_date", sa.Date(), nullable=False, comment="Start date"),
        sa.Column("end_date", sa.Date(), nullable=False, comment="End date"),
        sa.Column("week_count", sa.Integer(), nullable=False, comment="Teaching week count"),
        sa.Column("is_current", sa.Boolean(), nullable=False, comment="Current term"),
        sa.Column("status", sa.SmallInteger(), nullable=False, comment="1=enabled 0=disabled"),
        sa.Column("remark", sa.Text(), nullable=True, comment="Remark"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Updated at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("academic_year", "semester", name="uq_term_year_semester"),
    )
    op.create_index("idx_term_current", "term", ["is_current"], unique=False)
    op.create_index("idx_term_status", "term", ["status"], unique=False)

    op.create_table(
        "term_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("term_id", sa.Integer(), nullable=False, comment="Term ID"),
        sa.Column("event_type", sa.String(length=30), nullable=False, comment="Event type"),
        sa.Column("title", sa.String(length=100), nullable=False, comment="Event title"),
        sa.Column("start_date", sa.Date(), nullable=False, comment="Start date"),
        sa.Column("end_date", sa.Date(), nullable=False, comment="End date"),
        sa.Column("is_teaching_day", sa.Boolean(), nullable=False, comment="Teaching day"),
        sa.Column("description", sa.Text(), nullable=True, comment="Description"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Updated at"),
        sa.ForeignKeyConstraint(["term_id"], ["term.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_term_event_term", "term_event", ["term_id"], unique=False)

    op.create_table(
        "classroom",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="Classroom name"),
        sa.Column("building", sa.String(length=100), nullable=True, comment="Building"),
        sa.Column("room_no", sa.String(length=50), nullable=True, comment="Room number"),
        sa.Column("campus", sa.String(length=100), nullable=True, comment="Campus"),
        sa.Column("capacity", sa.Integer(), nullable=False, comment="Capacity"),
        sa.Column("room_type", sa.String(length=30), nullable=False, comment="Room type"),
        sa.Column("status", sa.SmallInteger(), nullable=False, comment="1=available 0=disabled 2=maintenance"),
        sa.Column("remark", sa.Text(), nullable=True, comment="Remark"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Updated at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_classroom_name"),
    )
    op.create_index("idx_classroom_status", "classroom", ["status"], unique=False)
    op.create_index("idx_classroom_type", "classroom", ["room_type"], unique=False)

    op.create_table(
        "course_schedule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("term_id", sa.Integer(), nullable=False, comment="Term ID"),
        sa.Column("course_id", sa.Integer(), nullable=False, comment="Course ID"),
        sa.Column("clazz_id", sa.Integer(), nullable=False, comment="Class ID"),
        sa.Column("teacher_id", sa.Integer(), nullable=False, comment="Teacher ID"),
        sa.Column("classroom_id", sa.Integer(), nullable=True, comment="Classroom ID"),
        sa.Column("weekday", sa.SmallInteger(), nullable=False, comment="Weekday 1-7"),
        sa.Column("start_section", sa.SmallInteger(), nullable=False, comment="Start section"),
        sa.Column("end_section", sa.SmallInteger(), nullable=False, comment="End section"),
        sa.Column("start_week", sa.SmallInteger(), nullable=False, comment="Start week"),
        sa.Column("end_week", sa.SmallInteger(), nullable=False, comment="End week"),
        sa.Column("week_type", sa.String(length=10), nullable=False, comment="all/odd/even"),
        sa.Column("schedule_type", sa.String(length=20), nullable=False, comment="normal/makeup/temporary"),
        sa.Column("status", sa.SmallInteger(), nullable=False, comment="1=normal 0=disabled"),
        sa.Column("remark", sa.Text(), nullable=True, comment="Remark"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Updated at"),
        sa.ForeignKeyConstraint(["classroom_id"], ["classroom.id"]),
        sa.ForeignKeyConstraint(["clazz_id"], ["clazz.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.ForeignKeyConstraint(["term_id"], ["term.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_schedule_classroom", "course_schedule", ["classroom_id"], unique=False)
    op.create_index("idx_schedule_clazz", "course_schedule", ["clazz_id"], unique=False)
    op.create_index("idx_schedule_course", "course_schedule", ["course_id"], unique=False)
    op.create_index("idx_schedule_teacher", "course_schedule", ["teacher_id"], unique=False)
    op.create_index("idx_schedule_term", "course_schedule", ["term_id"], unique=False)
    op.create_index(
        "idx_schedule_time",
        "course_schedule",
        ["term_id", "weekday", "start_section", "end_section", "start_week", "end_week"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_schedule_time", table_name="course_schedule")
    op.drop_index("idx_schedule_term", table_name="course_schedule")
    op.drop_index("idx_schedule_teacher", table_name="course_schedule")
    op.drop_index("idx_schedule_course", table_name="course_schedule")
    op.drop_index("idx_schedule_clazz", table_name="course_schedule")
    op.drop_index("idx_schedule_classroom", table_name="course_schedule")
    op.drop_table("course_schedule")

    op.drop_index("idx_classroom_type", table_name="classroom")
    op.drop_index("idx_classroom_status", table_name="classroom")
    op.drop_table("classroom")

    op.drop_index("idx_term_event_term", table_name="term_event")
    op.drop_table("term_event")

    op.drop_index("idx_term_status", table_name="term")
    op.drop_index("idx_term_current", table_name="term")
    op.drop_table("term")
