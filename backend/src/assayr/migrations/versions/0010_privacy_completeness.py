"""privacy completeness: processors, DPIAs, subject requests, breaches, consent and retention

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

TABLES = ["activity_processor", "processor"]


def upgrade() -> None:
    op.create_table(
        "processor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("service", sa.String(length=300), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("data_categories", sa.JSON(), nullable=True),
        sa.Column("dpa_signed", sa.Boolean(), nullable=False),
        sa.Column("dpa_date", sa.Date(), nullable=True),
        sa.Column("dpa_document_id", sa.Uuid(), nullable=True),
        sa.Column("subprocessors", sa.Text(), nullable=True),
        sa.Column("security_review_on", sa.Date(), nullable=True),
        sa.Column("security_result", sa.String(length=20), nullable=True),
        sa.Column("risk_level", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_processor_scope_id_scope", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dpa_document_id"],
            ["document.id"],
            name="fk_processor_dpa_document_id_document",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processor"),
    )
    op.create_table(
        "activity_processor",
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("processor_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["processing_activity.id"],
            name="fk_activity_processor_activity_id_processing_activity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["processor_id"],
            ["processor.id"],
            name="fk_activity_processor_processor_id_processor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("activity_id", "processor_id", name="pk_activity_processor"),
    )


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
