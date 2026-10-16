"""document register: policies, procedures, guidelines and their linked controls

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version_label", sa.String(length=20), nullable=False),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", UTCDateTime(), nullable=True),
        sa.Column("review_due", sa.Date(), nullable=True),
        sa.Column("current_sha256", sa.String(length=64), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("mime", sa.String(length=100), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("approved_version", sa.String(length=20), nullable=True),
        sa.Column("approved_sha256", sa.String(length=64), nullable=True),
        sa.Column("approved_filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_document_scope_id_scope", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["user_account.id"], name="fk_document_owner_id_user_account", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"],
            ["user_account.id"],
            name="fk_document_approved_by_id_user_account",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document"),
        sa.UniqueConstraint("scope_id", "code", name="uq_document_scope_code"),
    )
    op.create_table(
        "document_control",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name="fk_document_control_document_id_document",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_document_control_control_id_control", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id", "control_id", name="pk_document_control"),
    )


def downgrade() -> None:
    op.drop_table("document_control")
    op.drop_table("document")
