"""audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_PG_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END
$$;
"""
_PG_TRIGGER = """
CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column(
            "seq", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("diff", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("seq", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_PG_FUNCTION)
        op.execute(_PG_TRIGGER)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_table("audit_log")
