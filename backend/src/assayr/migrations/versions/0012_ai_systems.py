"""AI systems register and AI system impact assessments (ISO/IEC 42001)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

SECTIONS = (
    "intended_use",
    "affected",
    "individual_impacts",
    "societal_impacts",
    "fairness",
    "transparency",
    "oversight",
    "safety",
    "data_quality",
    "conclusion",
)


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "ai_system",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=200), nullable=True),
        sa.Column("model_type", sa.String(length=100), nullable=True),
        sa.Column("lifecycle", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.Integer(), nullable=False),
        sa.Column("uses_personal_data", sa.Boolean(), nullable=False),
        sa.Column("pii_categories", sa.JSON(), nullable=True),
        sa.Column("asset_ids", sa.JSON(), nullable=True),
        sa.Column("human_oversight", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(["scope_id"], ["scope.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_id", "code", name="uq_ai_system_scope_code"),
    )
    op.create_table(
        "ai_impact_assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_system_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *[sa.Column(name, sa.Text(), nullable=True) for name in SECTIONS],
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", UTCDateTime(), nullable=True),
        sa.Column("review_due", sa.Date(), nullable=True),
        *_stamps(),
        sa.ForeignKeyConstraint(["ai_system_id"], ["ai_system.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ai_system_id"),
    )
    op.create_table(
        "ai_impact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("area", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("risk_id", sa.Uuid(), nullable=True),
        *_stamps(),
        sa.ForeignKeyConstraint(["assessment_id"], ["ai_impact_assessment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for name in ("ai_impact", "ai_impact_assessment", "ai_system"):
        op.drop_table(name)
