"""personal data on assets, record of processing activities

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

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


def downgrade() -> None:
    for column in ("pii_volume", "pii_sensitive", "pii_categories", "holds_pii"):
        op.drop_column("asset", column)
