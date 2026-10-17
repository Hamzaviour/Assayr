"""Audit findings with corrective actions; mail settings, mail log and the digest opt-out

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def _user(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([name], ["user_account.id"], ondelete="SET NULL")


def upgrade() -> None:
    op.create_table(
        "finding",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=True),
        sa.Column("audit_item_id", sa.Uuid(), nullable=True),
        sa.Column("framework", sa.String(length=20), nullable=True),
        sa.Column("ref", sa.String(length=20), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("raised_by_id", sa.Uuid(), nullable=True),
        sa.Column("raised_at", UTCDateTime(), nullable=False),
        sa.Column("closed_at", UTCDateTime(), nullable=True),
        sa.Column("risk_id", sa.Uuid(), nullable=True),
        *_stamps(),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["audit_id"], ["audit.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["audit_item_id"], ["audit_item.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"], ondelete="SET NULL"),
        _user("owner_id"),
        _user("raised_by_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_id", "code", name="uq_finding_scope_code"),
        sa.UniqueConstraint("audit_item_id", name="uq_finding_audit_item"),
    )
    op.create_table(
        "corrective_action",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("done_at", UTCDateTime(), nullable=True),
        sa.Column("done_note", sa.Text(), nullable=True),
        *_stamps(),
        sa.ForeignKeyConstraint(["finding_id"], ["finding.id"], ondelete="CASCADE"),
        _user("owner_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", "seq", name="uq_corrective_action_finding_seq"),
    )
    op.create_table(
        "corrective_action_file",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["corrective_action.id"], ondelete="CASCADE"),
        _user("uploaded_by_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "finding_verification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("verifier_id", sa.Uuid(), nullable=True),
        sa.Column("effective", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("verified_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["finding.id"], ondelete="CASCADE"),
        _user("verifier_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mail_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(length=10), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("from_address", sa.String(length=320), nullable=True),
        sa.Column("from_name", sa.String(length=200), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("digest_hour", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", UTCDateTime(), nullable=True),
        _user("updated_by_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mail_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "kind", "day", name="uq_mail_log_user_kind_day"),
    )
    with op.batch_alter_table("user_account") as batch:
        batch.add_column(sa.Column("digest_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("user_account") as batch:
        batch.drop_column("digest_opt_out")
    for table in (
        "mail_log",
        "mail_settings",
        "finding_verification",
        "corrective_action_file",
        "corrective_action",
        "finding",
    ):
        op.drop_table(table)
