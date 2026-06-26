"""Add face recognition tables

Revision ID: f7c8d9e0a1b2
Revises: 0d2e3af91e64
Create Date: 2026-06-25 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7c8d9e0a1b2'
down_revision = '0d2e3af91e64'
branch_labels = None
depends_on = None


def upgrade():
    # 创建人脸模板表
    op.create_table(
        'face_template',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('feature_vector', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_face_user')
    )
    op.create_index(op.f('ix_face_template_user_id'), 'face_template', ['user_id'], unique=False)
    
    # 创建人脸登录日志表
    op.create_table(
        'face_login_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('device_info', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_face_login_log_user_id'), 'face_login_log', ['user_id'], unique=False)
    op.create_index(op.f('ix_face_login_log_created_at'), 'face_login_log', ['created_at'], unique=False)
    
    # 给 user 表添加 has_face_template 字段
    op.add_column('user', sa.Column('has_face_template', sa.Boolean(), nullable=True))
    op.execute("UPDATE user SET has_face_template = FALSE WHERE has_face_template IS NULL")
    op.alter_column('user', 'has_face_template', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())


def downgrade():
    # 删除字段
    op.drop_column('user', 'has_face_template')
    # 删除表
    op.drop_table('face_login_log')
    op.drop_table('face_template')