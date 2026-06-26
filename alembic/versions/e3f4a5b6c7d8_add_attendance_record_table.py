"""add attendance record table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-26 20:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("person_type", sa.String(length=20), nullable=False, comment="student/teacher"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="User ID"),
        sa.Column("student_id", sa.Integer(), nullable=True, comment="Student ID"),
        sa.Column("teacher_id", sa.Integer(), nullable=True, comment="Teacher ID"),
        sa.Column("clazz_id", sa.Integer(), nullable=True, comment="Class ID"),
        sa.Column("department_id", sa.Integer(), nullable=True, comment="Department ID"),
        sa.Column("attendance_date", sa.Date(), nullable=False, comment="Attendance date"),
        sa.Column("period_type", sa.String(length=30), nullable=False, comment="day/morning/afternoon/course/custom"),
        sa.Column("course_schedule_id", sa.Integer(), nullable=True, comment="Course schedule ID"),
        sa.Column("checkin_time", sa.DateTime(), nullable=True, comment="Check-in time"),
        sa.Column("checkout_time", sa.DateTime(), nullable=True, comment="Check-out time"),
        sa.Column("status", sa.String(length=30), nullable=False, comment="Attendance status"),
        sa.Column("source", sa.String(length=30), nullable=False, comment="manual/leave_sync/import/system"),
        sa.Column("leave_request_id", sa.Integer(), nullable=True, comment="Leave request ID"),
        sa.Column("remark", sa.String(length=500), nullable=True, comment="Remark"),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="Creator"),
        sa.Column("updated_by", sa.Integer(), nullable=True, comment="Updater"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Updated at"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.ForeignKeyConstraint(["clazz_id"], ["clazz.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.ForeignKeyConstraint(["course_schedule_id"], ["course_schedule.id"]),
        sa.ForeignKeyConstraint(["leave_request_id"], ["leave_request.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_att_person_type", "attendance_record", ["person_type"], unique=False)
    op.create_index("idx_att_user_id", "attendance_record", ["user_id"], unique=False)
    op.create_index("idx_att_student_id", "attendance_record", ["student_id"], unique=False)
    op.create_index("idx_att_teacher_id", "attendance_record", ["teacher_id"], unique=False)
    op.create_index("idx_att_clazz_id", "attendance_record", ["clazz_id"], unique=False)
    op.create_index("idx_att_department_id", "attendance_record", ["department_id"], unique=False)
    op.create_index("idx_att_date", "attendance_record", ["attendance_date"], unique=False)
    op.create_index("idx_att_status", "attendance_record", ["status"], unique=False)
    op.create_index("idx_att_source", "attendance_record", ["source"], unique=False)
    op.create_index("idx_att_schedule_id", "attendance_record", ["course_schedule_id"], unique=False)
    op.create_index("idx_att_leave_request_id", "attendance_record", ["leave_request_id"], unique=False)
    op.create_index("idx_att_person_date", "attendance_record", ["person_type", "user_id", "attendance_date"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_att_person_date", table_name="attendance_record")
    op.drop_index("idx_att_leave_request_id", table_name="attendance_record")
    op.drop_index("idx_att_schedule_id", table_name="attendance_record")
    op.drop_index("idx_att_source", table_name="attendance_record")
    op.drop_index("idx_att_status", table_name="attendance_record")
    op.drop_index("idx_att_date", table_name="attendance_record")
    op.drop_index("idx_att_department_id", table_name="attendance_record")
    op.drop_index("idx_att_clazz_id", table_name="attendance_record")
    op.drop_index("idx_att_teacher_id", table_name="attendance_record")
    op.drop_index("idx_att_student_id", table_name="attendance_record")
    op.drop_index("idx_att_user_id", table_name="attendance_record")
    op.drop_index("idx_att_person_type", table_name="attendance_record")
    op.drop_table("attendance_record")
