"""internal audits and their audited controls

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("framework", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("auditor_id", sa.Uuid(), nullable=True),
        sa.Column("scope_note", sa.Text(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("completed_at", UTCDateTime(), nullable=True),
        sa.Column("completed_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_audit_scope_id_scope", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["auditor_id"], ["user_account.id"], name="fk_audit_auditor_id_user_account", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_id"],
            ["user_account.id"],
            name="fk_audit_completed_by_id_user_account",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit"),
    )
    op.create_table(
        "audit_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=200), nullable=False),
        sa.Column("sub_domain", sa.String(length=200), nullable=False),
        sa.Column("assessment_area", sa.Text(), nullable=True),
        sa.Column("test_type", sa.String(length=10), nullable=True),
        sa.Column("requirement", sa.String(length=1), nullable=True),
        sa.Column("result", sa.String(length=10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["audit_id"], ["audit.id"], name="fk_audit_item_audit_id_audit", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_item"),
        sa.UniqueConstraint("audit_id", "ref", name="uq_audit_item_audit_ref"),
    )


def downgrade() -> None:
    op.drop_table("audit_item")
    op.drop_table("audit")
