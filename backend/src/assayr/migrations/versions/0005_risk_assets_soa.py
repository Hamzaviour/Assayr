"""assets, risk register, tasks and statement of applicability

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _user_fk(column: str, table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["user_account.id"], name=f"fk_{table}_{column}_user_account", ondelete="SET NULL"
    )


def _scope_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["scope_id"], ["scope.id"], name=f"fk_{table}_scope_id_scope", ondelete="CASCADE"
    )


def _library_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{name}"),
        sa.UniqueConstraint("code", name=f"uq_{name}_code"),
    )


def _link_table(name: str, other: str) -> None:
    op.create_table(
        name,
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column(f"{other}_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["risk_id"], ["risk.id"], name=f"fk_{name}_risk_id_risk", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            [f"{other}_id"], [f"{other}.id"], name=f"fk_{name}_{other}_id_{other}", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("risk_id", f"{other}_id", name=f"pk_{name}"),
    )


def upgrade() -> None:
    op.add_column("control", sa.Column("applicable", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("control", sa.Column("soa_sources", sa.JSON(), nullable=True))
    op.add_column("control", sa.Column("soa_justification", sa.Text(), nullable=True))
    op.add_column("control", sa.Column("exclusion_reason", sa.Text(), nullable=True))

    op.create_table(
        "asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("confidentiality", sa.Integer(), nullable=False),
        sa.Column("integrity", sa.Integer(), nullable=False),
        sa.Column("availability", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lifecycle", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _scope_fk("asset"),
        _user_fk("owner_id", "asset"),
        sa.PrimaryKeyConstraint("id", name="pk_asset"),
        sa.UniqueConstraint("scope_id", "code", name="uq_asset_scope_code"),
    )
    op.create_table(
        "methodology_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_methodology_version"),
        sa.UniqueConstraint("version_no", name="uq_methodology_version_version_no"),
    )
    _library_table("threat")
    _library_table("vulnerability")
    op.create_table(
        "risk_template",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("threat_codes", sa.JSON(), nullable=False),
        sa.Column("vulnerability_codes", sa.JSON(), nullable=False),
        sa.Column("control_codes", sa.JSON(), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=False),
        sa.Column("consequence", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_risk_template"),
        sa.UniqueConstraint("code", name="uq_risk_template_code"),
    )
    op.create_table(
        "risk",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("approach", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("treatment_option", sa.String(length=10), nullable=True),
        sa.Column("treatment_note", sa.Text(), nullable=True),
        sa.Column("treatment_budget", sa.String(length=100), nullable=True),
        sa.Column("treatment_due", sa.Date(), nullable=True),
        sa.Column("review_due", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("template_code", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _scope_fk("risk"),
        _user_fk("owner_id", "risk"),
        sa.PrimaryKeyConstraint("id", name="pk_risk"),
        sa.UniqueConstraint("scope_id", "code", name="uq_risk_scope_code"),
    )
    _link_table("risk_asset", "asset")
    _link_table("risk_threat", "threat")
    _link_table("risk_vulnerability", "vulnerability")
    op.create_table(
        "risk_control",
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("axis", sa.String(length=12), nullable=False),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name="fk_risk_control_risk_id_risk", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_risk_control_control_id_control", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("risk_id", "control_id", name="pk_risk_control"),
    )
    op.create_table(
        "risk_assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column("methodology_version_id", sa.Uuid(), nullable=False),
        sa.Column("likelihood", sa.Integer(), nullable=True),
        sa.Column("consequence", sa.JSON(), nullable=True),
        sa.Column("current_l", sa.Integer(), nullable=True),
        sa.Column("current_c", sa.Integer(), nullable=True),
        sa.Column("current_reason", sa.Text(), nullable=True),
        sa.Column("suggested", sa.JSON(), nullable=True),
        sa.Column("target_l", sa.Integer(), nullable=True),
        sa.Column("target_c", sa.Integer(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("assessed_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name="fk_risk_assessment_risk_id_risk", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["methodology_version_id"],
            ["methodology_version.id"],
            name="fk_risk_assessment_methodology_version_id_methodology_version",
        ),
        _user_fk("assessed_by_id", "risk_assessment"),
        sa.PrimaryKeyConstraint("id", name="pk_risk_assessment"),
    )
    op.create_index("ix_risk_assessment_risk_id", "risk_assessment", ["risk_id"])
    op.create_table(
        "risk_acceptance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("risk_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("band", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("authority", sa.String(length=20), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("accepted_by_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["risk_id"], ["risk.id"], name="fk_risk_acceptance_risk_id_risk", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["risk_assessment.id"],
            name="fk_risk_acceptance_assessment_id_risk_assessment",
            ondelete="CASCADE",
        ),
        _user_fk("accepted_by_id", "risk_acceptance"),
        sa.PrimaryKeyConstraint("id", name="pk_risk_acceptance"),
    )
    op.create_index("ix_risk_acceptance_risk_id", "risk_acceptance", ["risk_id"])
    op.create_table(
        "risk_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("taken_by_id", sa.Uuid(), nullable=True),
        sa.Column("methodology_version_id", sa.Uuid(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        _scope_fk("risk_snapshot"),
        _user_fk("taken_by_id", "risk_snapshot"),
        sa.ForeignKeyConstraint(
            ["methodology_version_id"],
            ["methodology_version.id"],
            name="fk_risk_snapshot_methodology_version_id_methodology_version",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_snapshot"),
    )
    op.create_index("ix_risk_snapshot_scope_id", "risk_snapshot", ["scope_id"])
    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("due", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _scope_fk("task"),
        _user_fk("assignee_id", "task"),
        _user_fk("created_by_id", "task"),
        sa.PrimaryKeyConstraint("id", name="pk_task"),
    )
    op.create_index("ix_task_entity", "task", ["entity_type", "entity_id"])
    op.create_table(
        "soa_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("entries", sa.JSON(), nullable=False),
        sa.Column("prepared_by_id", sa.Uuid(), nullable=True),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        _scope_fk("soa_version"),
        _user_fk("prepared_by_id", "soa_version"),
        _user_fk("decided_by_id", "soa_version"),
        sa.PrimaryKeyConstraint("id", name="pk_soa_version"),
        sa.UniqueConstraint("scope_id", "version_no", name="uq_soa_version_scope_no"),
    )


def downgrade() -> None:
    op.drop_table("soa_version")
    op.drop_index("ix_task_entity", table_name="task")
    op.drop_table("task")
    op.drop_index("ix_risk_snapshot_scope_id", table_name="risk_snapshot")
    op.drop_table("risk_snapshot")
    op.drop_index("ix_risk_acceptance_risk_id", table_name="risk_acceptance")
    op.drop_table("risk_acceptance")
    op.drop_index("ix_risk_assessment_risk_id", table_name="risk_assessment")
    op.drop_table("risk_assessment")
    op.drop_table("risk_control")
    op.drop_table("risk_vulnerability")
    op.drop_table("risk_threat")
    op.drop_table("risk_asset")
    op.drop_table("risk")
    op.drop_table("risk_template")
    op.drop_table("vulnerability")
    op.drop_table("threat")
    op.drop_table("methodology_version")
    op.drop_table("asset")
    with op.batch_alter_table("control") as batch:
        batch.drop_column("exclusion_reason")
        batch.drop_column("soa_justification")
        batch.drop_column("soa_sources")
        batch.drop_column("applicable")
