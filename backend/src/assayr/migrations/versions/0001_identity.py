"""identity tables

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_organization"),
    )
    op.create_table(
        "scope",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_scope_organization_id_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scope"),
    )
    op.create_table(
        "user_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_user_account"),
        sa.UniqueConstraint("email", name="uq_user_account_email"),
    )
    op.create_table(
        "role_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name="fk_role_assignment_user_id_user_account",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_role_assignment_scope_id_scope", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_assignment"),
        sa.UniqueConstraint("user_id", "role", "scope_id", name="uq_role_assignment_user_role_scope"),
    )
    op.create_table(
        "user_session",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_account.id"], name="fk_user_session_user_id_user_account", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_session"),
    )
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_session_user_id", table_name="user_session")
    op.drop_table("user_session")
    op.drop_table("role_assignment")
    op.drop_table("user_account")
    op.drop_table("scope")
    op.drop_table("organization")
