"""add leave request table

Revision ID: b8c9d0e1f2a3
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26 11:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "leave_request",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("applicant_user_id", sa.Integer(), nullable=False, comment="申请人用户ID"),
        sa.Column("applicant_type", sa.String(length=20), nullable=False, comment="申请人类型"),
        sa.Column("student_id", sa.Integer(), nullable=True, comment="学生ID"),
        sa.Column("teacher_id", sa.Integer(), nullable=True, comment="教职工ID"),
        sa.Column("clazz_id", sa.Integer(), nullable=True, comment="班级ID"),
        sa.Column("department_id", sa.Integer(), nullable=True, comment="院系ID"),
        sa.Column("leave_type", sa.String(length=30), nullable=False, comment="请假类型"),
        sa.Column("start_time", sa.DateTime(), nullable=False, comment="开始时间"),
        sa.Column("end_time", sa.DateTime(), nullable=False, comment="结束时间"),
        sa.Column("duration_hours", sa.Numeric(precision=8, scale=2), nullable=False, comment="请假时长(小时)"),
        sa.Column("reason", sa.Text(), nullable=False, comment="请假原因"),
        sa.Column("destination", sa.String(length=200), nullable=True, comment="去向/地点"),
        sa.Column("contact_phone", sa.String(length=20), nullable=True, comment="联系电话"),
        sa.Column("emergency_contact", sa.String(length=100), nullable=True, comment="紧急联系人"),
        sa.Column("attachment_url", sa.String(length=500), nullable=True, comment="证明材料"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="状态"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True, comment="审批人"),
        sa.Column("reviewer_role", sa.String(length=50), nullable=True, comment="审批身份"),
        sa.Column("review_comment", sa.String(length=500), nullable=True, comment="审批意见"),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="审批时间"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="软删除标记"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["applicant_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.ForeignKeyConstraint(["clazz_id"], ["clazz.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_leave_applicant_user_id", "leave_request", ["applicant_user_id"], unique=False)
    op.create_index("idx_leave_applicant_type", "leave_request", ["applicant_type"], unique=False)
    op.create_index("idx_leave_student_id", "leave_request", ["student_id"], unique=False)
    op.create_index("idx_leave_teacher_id", "leave_request", ["teacher_id"], unique=False)
    op.create_index("idx_leave_clazz_id", "leave_request", ["clazz_id"], unique=False)
    op.create_index("idx_leave_department_id", "leave_request", ["department_id"], unique=False)
    op.create_index("idx_leave_status", "leave_request", ["status"], unique=False)
    op.create_index("idx_leave_start_time", "leave_request", ["start_time"], unique=False)
    op.create_index("idx_leave_end_time", "leave_request", ["end_time"], unique=False)
    op.create_index("idx_leave_reviewer_id", "leave_request", ["reviewer_id"], unique=False)


def downgrade():
    op.drop_index("idx_leave_reviewer_id", table_name="leave_request")
    op.drop_index("idx_leave_end_time", table_name="leave_request")
    op.drop_index("idx_leave_start_time", table_name="leave_request")
    op.drop_index("idx_leave_status", table_name="leave_request")
    op.drop_index("idx_leave_department_id", table_name="leave_request")
    op.drop_index("idx_leave_clazz_id", table_name="leave_request")
    op.drop_index("idx_leave_teacher_id", table_name="leave_request")
    op.drop_index("idx_leave_student_id", table_name="leave_request")
    op.drop_index("idx_leave_applicant_type", table_name="leave_request")
    op.drop_index("idx_leave_applicant_user_id", table_name="leave_request")
    op.drop_table("leave_request")
