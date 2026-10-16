"""training and awareness: staff departments, temporary passwords, courses and assignments

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

from assayr.db import UTCDateTime

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _fk(table: str, column: str, target: str, ondelete: str = "CASCADE") -> sa.ForeignKeyConstraint:
    ref = target.split(".")[0]
    return sa.ForeignKeyConstraint([column], [target], name=f"fk_{table}_{column}_{ref}", ondelete=ondelete)


def _create_training_tables() -> None:
    op.create_table(
        "course",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recurrence_months", sa.Integer(), nullable=True),
        sa.Column("due_days", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        _fk("course", "scope_id", "scope.id"),
        _fk("course", "created_by_id", "user_account.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_course"),
    )
    op.create_table(
        "course_material",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("drive_file_id", sa.String(length=100), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("mime", sa.String(length=100), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        _fk("course_material", "course_id", "course.id"),
        sa.PrimaryKeyConstraint("id", name="pk_course_material"),
    )
    op.create_table(
        "course_rule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(length=150), nullable=False),
        _fk("course_rule", "course_id", "course.id"),
        sa.PrimaryKeyConstraint("id", name="pk_course_rule"),
        sa.UniqueConstraint("course_id", "target", name="uq_course_rule_course_target"),
    )
    op.create_table(
        "assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("pass_mark", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("shuffle", sa.Boolean(), nullable=False),
        _fk("assessment", "course_id", "course.id"),
        sa.PrimaryKeyConstraint("id", name="pk_assessment"),
        sa.UniqueConstraint("course_id", name="uq_assessment_course_id"),
    )
    op.create_table(
        "question",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        _fk("question", "assessment_id", "assessment.id"),
        sa.PrimaryKeyConstraint("id", name="pk_question"),
    )
    op.create_table(
        "question_option",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        _fk("question_option", "question_id", "question.id"),
        sa.PrimaryKeyConstraint("id", name="pk_question_option"),
    )
    op.create_table(
        "assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=150), nullable=False),
        sa.Column("assigned_at", UTCDateTime(), nullable=False),
        sa.Column("due_at", sa.Date(), nullable=False),
        sa.Column("completed_at", UTCDateTime(), nullable=True),
        sa.Column("extra_attempts", sa.Integer(), nullable=False),
        sa.Column("material_progress", sa.JSON(), nullable=False),
        sa.Column("renewed", sa.Boolean(), nullable=False),
        _fk("assignment", "course_id", "course.id"),
        _fk("assignment", "user_id", "user_account.id"),
        sa.PrimaryKeyConstraint("id", name="pk_assignment"),
    )
    op.create_table(
        "attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=False),
        sa.Column("submitted_at", UTCDateTime(), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        _fk("attempt", "assignment_id", "assignment.id"),
        sa.PrimaryKeyConstraint("id", name="pk_attempt"),
    )


def upgrade() -> None:
    op.add_column("user_account", sa.Column("department", sa.String(length=100), nullable=True))
    op.add_column(
        "user_account",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    _create_training_tables()


def downgrade() -> None:
    for table in (
        "attempt",
        "assignment",
        "question_option",
        "question",
        "assessment",
        "course_rule",
        "course_material",
        "course",
    ):
        op.drop_table(table)
    op.drop_column("user_account", "must_change_password")
    op.drop_column("user_account", "department")
