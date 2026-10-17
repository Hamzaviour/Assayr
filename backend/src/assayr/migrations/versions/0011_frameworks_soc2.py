"""frameworks: control.framework and test procedure; SOC 2 fields on audit items

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("control") as batch:
        batch.add_column(
            sa.Column("framework", sa.String(length=20), nullable=False, server_default="iso27001")
        )
        batch.add_column(sa.Column("test_procedure", sa.Text(), nullable=True))
    op.execute("UPDATE control SET framework = 'nia' WHERE code LIKE 'NIA %'")
    op.create_index("ix_control_scope_framework", "control", ["scope_id", "framework"])
    with op.batch_alter_table("audit_item") as batch:
        batch.alter_column("result", type_=sa.String(length=20), existing_type=sa.String(length=10))
        batch.add_column(sa.Column("population", sa.Text(), nullable=True))
        batch.add_column(sa.Column("sample_size", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("samples_tested", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("exception_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("audit_item") as batch:
        for name in ("exception_note", "samples_tested", "sample_size", "population"):
            batch.drop_column(name)
        batch.alter_column("result", type_=sa.String(length=10), existing_type=sa.String(length=20))
    op.drop_index("ix_control_scope_framework", table_name="control")
    with op.batch_alter_table("control") as batch:
        batch.drop_column("test_procedure")
        batch.drop_column("framework")
