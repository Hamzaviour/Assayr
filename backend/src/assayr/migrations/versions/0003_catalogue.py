"""catalogue: frameworks, requirements, controls, evidence slots

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "framework",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_framework"),
        sa.UniqueConstraint("code", name="uq_framework_code"),
    )
    op.create_table(
        "requirement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["framework_id"],
            ["framework.id"],
            name="fk_requirement_framework_id_framework",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["requirement.id"], name="fk_requirement_parent_id_requirement", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirement"),
        sa.UniqueConstraint("framework_id", "ref", name="uq_requirement_framework_ref"),
    )
    op.create_table(
        "control",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("theme", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("default_owner_role", sa.String(length=60), nullable=True),
        sa.Column("review_frequency", sa.String(length=30), nullable=True),
        sa.Column("implementation_status", sa.String(length=30), nullable=False),
        sa.Column("implementation_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_control_scope_id_scope", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["user_account.id"], name="fk_control_owner_id_user_account", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_control"),
        sa.UniqueConstraint("scope_id", "code", name="uq_control_scope_code"),
    )
    op.create_index("ix_control_scope_sort", "control", ["scope_id", "sort_order"])
    op.create_table(
        "control_requirement",
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("coverage", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["control.id"],
            name="fk_control_requirement_control_id_control",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name="fk_control_requirement_requirement_id_requirement",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("control_id", "requirement_id", name="pk_control_requirement"),
    )
    op.create_table(
        "evidence_slot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("freshness_days", sa.Integer(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("required_concepts", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_evidence_slot_control_id_control", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["requirement.id"],
            name="fk_evidence_slot_requirement_id_requirement",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence_slot"),
    )


def downgrade() -> None:
    op.drop_table("evidence_slot")
    op.drop_table("control_requirement")
    op.drop_index("ix_control_scope_sort", table_name="control")
    op.drop_table("control")
    op.drop_table("requirement")
    op.drop_table("framework")
