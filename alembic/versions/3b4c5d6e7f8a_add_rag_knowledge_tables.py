"""add rag knowledge tables

Revision ID: 3b4c5d6e7f8a
Revises: 2a3b4c5d6e7f
Create Date: 2026-06-27 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "3b4c5d6e7f8a"
down_revision = "2a3b4c5d6e7f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rag_knowledge_base",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="Knowledge base name"),
        sa.Column("description", sa.String(length=512), nullable=True, comment="Description"),
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Owner user id"),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="personal", comment="personal/public/class/course"),
        sa.Column("scope_id", sa.Integer(), nullable=True, comment="Optional scope id"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1", comment="1=enabled,0=disabled"),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0", comment="Active document count"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0", comment="Active chunk count"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Updated at"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rag_knowledge_base_owner_id"), "rag_knowledge_base", ["owner_id"], unique=False)
    op.create_index("idx_rag_kb_owner_scope", "rag_knowledge_base", ["owner_id", "scope_type", "scope_id"], unique=False)

    op.create_table(
        "rag_document",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("kb_id", sa.Integer(), nullable=False, comment="Knowledge base id"),
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Owner user id"),
        sa.Column("title", sa.String(length=200), nullable=False, comment="Document title"),
        sa.Column("source_type", sa.String(length=20), nullable=False, comment="text/upload/path"),
        sa.Column("file_name", sa.String(length=255), nullable=True, comment="Original file name"),
        sa.Column("file_path", sa.String(length=500), nullable=True, comment="Stored file path or allowed local path"),
        sa.Column("file_ext", sa.String(length=20), nullable=True, comment="File extension"),
        sa.Column("file_hash", sa.String(length=64), nullable=True, comment="SHA256 hash"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending", comment="pending/processing/completed/failed/deleted"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Last processing error"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0", comment="Chunk count"),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0", comment="Character count"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Updated at"),
        sa.ForeignKeyConstraint(["kb_id"], ["rag_knowledge_base.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rag_document_kb_id"), "rag_document", ["kb_id"], unique=False)
    op.create_index(op.f("ix_rag_document_owner_id"), "rag_document", ["owner_id"], unique=False)
    op.create_index(op.f("ix_rag_document_file_hash"), "rag_document", ["file_hash"], unique=False)
    op.create_index(op.f("ix_rag_document_status"), "rag_document", ["status"], unique=False)
    op.create_index("idx_rag_doc_kb_status", "rag_document", ["kb_id", "status"], unique=False)
    op.create_index("idx_rag_doc_owner_status", "rag_document", ["owner_id", "status"], unique=False)

    op.create_table(
        "rag_document_chunk",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="Primary key"),
        sa.Column("kb_id", sa.Integer(), nullable=False, comment="Knowledge base id"),
        sa.Column("document_id", sa.Integer(), nullable=False, comment="Document id"),
        sa.Column("owner_id", sa.Integer(), nullable=False, comment="Owner user id"),
        sa.Column("chunk_no", sa.Integer(), nullable=False, comment="Chunk sequence number"),
        sa.Column("content", sa.Text(), nullable=False, comment="Chunk content"),
        sa.Column("content_hash", sa.String(length=64), nullable=False, comment="SHA256 hash"),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0", comment="Character count"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0", comment="Approx token count"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed", comment="completed/deleted"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="Soft delete flag"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Deleted at"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="Updated at"),
        sa.ForeignKeyConstraint(["kb_id"], ["rag_knowledge_base.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["rag_document.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rag_document_chunk_kb_id"), "rag_document_chunk", ["kb_id"], unique=False)
    op.create_index(op.f("ix_rag_document_chunk_document_id"), "rag_document_chunk", ["document_id"], unique=False)
    op.create_index(op.f("ix_rag_document_chunk_owner_id"), "rag_document_chunk", ["owner_id"], unique=False)
    op.create_index(op.f("ix_rag_document_chunk_content_hash"), "rag_document_chunk", ["content_hash"], unique=False)
    op.create_index(op.f("ix_rag_document_chunk_status"), "rag_document_chunk", ["status"], unique=False)
    op.create_index("idx_rag_chunk_kb_doc", "rag_document_chunk", ["kb_id", "document_id"], unique=False)
    op.create_index("idx_rag_chunk_doc_no", "rag_document_chunk", ["document_id", "chunk_no"], unique=False)


def downgrade():
    op.drop_index("idx_rag_chunk_doc_no", table_name="rag_document_chunk")
    op.drop_index("idx_rag_chunk_kb_doc", table_name="rag_document_chunk")
    op.drop_index(op.f("ix_rag_document_chunk_status"), table_name="rag_document_chunk")
    op.drop_index(op.f("ix_rag_document_chunk_content_hash"), table_name="rag_document_chunk")
    op.drop_index(op.f("ix_rag_document_chunk_owner_id"), table_name="rag_document_chunk")
    op.drop_index(op.f("ix_rag_document_chunk_document_id"), table_name="rag_document_chunk")
    op.drop_index(op.f("ix_rag_document_chunk_kb_id"), table_name="rag_document_chunk")
    op.drop_table("rag_document_chunk")

    op.drop_index("idx_rag_doc_owner_status", table_name="rag_document")
    op.drop_index("idx_rag_doc_kb_status", table_name="rag_document")
    op.drop_index(op.f("ix_rag_document_status"), table_name="rag_document")
    op.drop_index(op.f("ix_rag_document_file_hash"), table_name="rag_document")
    op.drop_index(op.f("ix_rag_document_owner_id"), table_name="rag_document")
    op.drop_index(op.f("ix_rag_document_kb_id"), table_name="rag_document")
    op.drop_table("rag_document")

    op.drop_index("idx_rag_kb_owner_scope", table_name="rag_knowledge_base")
    op.drop_index(op.f("ix_rag_knowledge_base_owner_id"), table_name="rag_knowledge_base")
    op.drop_table("rag_knowledge_base")
