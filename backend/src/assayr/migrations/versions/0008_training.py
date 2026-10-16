"""training and awareness: staff departments, temporary passwords, courses and assignments

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_account", sa.Column("department", sa.String(length=100), nullable=True))
    op.add_column(
        "user_account",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_account", "must_change_password")
    op.drop_column("user_account", "department")
