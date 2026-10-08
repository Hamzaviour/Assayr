"""evidence, verification, scoring and job tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _user_fk(column: str, table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["user_account.id"], name=f"fk_{table}_{column}_user_account", ondelete="SET NULL"
    )


def upgrade() -> None:
    op.add_column("control", sa.Column("score", sa.Float(), nullable=True))
    op.create_table(
        "artefact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_artefact_scope_id_scope", ondelete="CASCADE"
        ),
        _user_fk("uploaded_by_id", "artefact"),
        sa.PrimaryKeyConstraint("id", name="pk_artefact"),
    )
    op.create_table(
        "artefact_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artefact_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=True),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extract_error", sa.String(length=300), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("doc_metadata", sa.JSON(), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artefact_id"],
            ["artefact.id"],
            name="fk_artefact_version_artefact_id_artefact",
            ondelete="CASCADE",
        ),
        _user_fk("uploaded_by_id", "artefact_version"),
        sa.PrimaryKeyConstraint("id", name="pk_artefact_version"),
        sa.UniqueConstraint("artefact_id", "version_no", name="uq_artefact_version_artefact_no"),
    )
    op.create_index("ix_artefact_version_sha256", "artefact_version", ["sha256"])
    op.create_table(
        "artefact_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["artefact_version.id"],
            name="fk_artefact_link_version_id_artefact_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["evidence_slot.id"],
            name="fk_artefact_link_slot_id_evidence_slot",
            ondelete="CASCADE",
        ),
        _user_fk("decided_by_id", "artefact_link"),
        sa.PrimaryKeyConstraint("id", name="pk_artefact_link"),
        sa.UniqueConstraint("version_id", "slot_id", name="uq_artefact_link_version_slot"),
    )
    op.create_index("ix_artefact_link_slot_id", "artefact_link", ["slot_id"])
    op.create_table(
        "verification_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rules_version", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(
            ["link_id"],
            ["artefact_link.id"],
            name="fk_verification_run_link_id_artefact_link",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_verification_run"),
    )
    op.create_index("ix_verification_run_link_id", "verification_run", ["link_id"])
    op.create_table(
        "rule_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("fix_hint", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["verification_run.id"],
            name="fk_rule_result_run_id_verification_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rule_result"),
    )
    op.create_index("ix_rule_result_run_id", "rule_result", ["run_id"])
    op.create_table(
        "attestation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_attestation_control_id_control", ondelete="CASCADE"
        ),
        _user_fk("user_id", "attestation"),
        sa.PrimaryKeyConstraint("id", name="pk_attestation"),
    )
    op.create_index("ix_attestation_control_id", "attestation", ["control_id"])
    op.create_table(
        "status_transition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("trigger", sa.String(length=300), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control.id"], name="fk_status_transition_control_id_control", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_status_transition"),
    )
    op.create_index("ix_status_transition_control_id", "status_transition", ["control_id"])
    op.create_table(
        "score_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness", sa.Float(), nullable=False),
        sa.Column("status_counts", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scope_id"], ["scope.id"], name="fk_score_snapshot_scope_id_scope", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_score_snapshot"),
    )
    op.create_index("ix_score_snapshot_scope_taken", "score_snapshot", ["scope_id", "taken_at"])
    op.create_table(
        "job",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job"),
    )
    op.create_index("ix_job_status_run_after", "job", ["status", "run_after"])


def downgrade() -> None:
    op.drop_index("ix_job_status_run_after", table_name="job")
    op.drop_table("job")
    op.drop_index("ix_score_snapshot_scope_taken", table_name="score_snapshot")
    op.drop_table("score_snapshot")
    op.drop_index("ix_status_transition_control_id", table_name="status_transition")
    op.drop_table("status_transition")
    op.drop_index("ix_attestation_control_id", table_name="attestation")
    op.drop_table("attestation")
    op.drop_index("ix_rule_result_run_id", table_name="rule_result")
    op.drop_table("rule_result")
    op.drop_index("ix_verification_run_link_id", table_name="verification_run")
    op.drop_table("verification_run")
    op.drop_index("ix_artefact_link_slot_id", table_name="artefact_link")
    op.drop_table("artefact_link")
    op.drop_index("ix_artefact_version_sha256", table_name="artefact_version")
    op.drop_table("artefact_version")
    op.drop_table("artefact")
    with op.batch_alter_table("control") as batch:
        batch.drop_column("score")
