"""personal data on assets, record of processing activities

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("holds_pii", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("asset", sa.Column("pii_categories", sa.JSON(), nullable=True))
    op.add_column(
        "asset", sa.Column("pii_sensitive", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column("asset", sa.Column("pii_volume", sa.String(length=10), nullable=True))
    op.create_table(
        "processing_activity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("data_subjects", sa.JSON(), nullable=True),
        sa.Column("data_categories", sa.JSON(), nullable=True),
        sa.Column("lawful_basis", sa.String(length=30), nullable=False),
        sa.Column("recipients", sa.Text(), nullable=True),
        sa.Column("cross_border", sa.Boolean(), nullable=False),
        sa.Column("transfer_countries", sa.String(length=300), nullable=True),
        sa.Column("retention", sa.String(length=300), nullable=True),
        sa.Column("security_measures", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("review_due", sa.Date(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_processing_activity_scope_id_scope", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name="fk_processing_activity_owner_id_user_account",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processing_activity"),
        sa.UniqueConstraint("scope_id", "code", name="uq_processing_activity_scope_code"),
    )
    op.create_table(
        "processing_asset",
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["processing_activity.id"],
            name="fk_processing_asset_activity_id_processing_activity",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name="fk_processing_asset_asset_id_asset", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("activity_id", "asset_id", name="pk_processing_asset"),
    )


def downgrade() -> None:
    op.drop_table("processing_asset")
    op.drop_table("processing_activity")
    for column in ("pii_volume", "pii_sensitive", "pii_categories", "holds_pii"):
        op.drop_column("asset", column)
