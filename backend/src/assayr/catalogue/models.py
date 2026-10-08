from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin
from assayr.identity.models import User


class Framework(IdMixin, TimestampMixin, Base):
    __tablename__ = "framework"

    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(20))


class Requirement(IdMixin, Base):
    """Something a framework asks for: a clause, a clause group, an Annex A theme or an Annex A control."""

    __tablename__ = "requirement"
    __table_args__ = (UniqueConstraint("framework_id", "ref", name="uq_requirement_framework_ref"),)

    framework_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    guidance: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)


class ControlRequirement(Base):
    __tablename__ = "control_requirement"

    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("control.id", ondelete="CASCADE"), primary_key=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), primary_key=True
    )
    coverage: Mapped[str] = mapped_column(String(10), default="full")


class Control(IdMixin, TimestampMixin, Base):
    """What the organization does. Mapped to one or more requirements (ADR-006)."""

    __tablename__ = "control"
    __table_args__ = (
        UniqueConstraint("scope_id", "code", name="uq_control_scope_code"),
        Index("ix_control_scope_sort", "scope_id", "sort_order"),
    )

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    theme: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    default_owner_role: Mapped[str | None] = mapped_column(String(60))
    review_frequency: Mapped[str | None] = mapped_column(String(30))
    implementation_status: Mapped[str] = mapped_column(String(30), default="not_started")
    implementation_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="not_started")
    sort_order: Mapped[int] = mapped_column(default=0)
    score: Mapped[float | None] = mapped_column(Float)
    applicable: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    soa_sources: Mapped[list | None] = mapped_column(JSON)
    soa_justification: Mapped[str | None] = mapped_column(Text)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)

    owner: Mapped[User | None] = relationship(lazy="joined")
    slots: Mapped[list[EvidenceSlot]] = relationship(
        back_populates="control",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EvidenceSlot.sort_order",
    )
    requirements: Mapped[list[Requirement]] = relationship(
        secondary="control_requirement", lazy="selectin", viewonly=True, order_by="Requirement.sort_order"
    )


class EvidenceSlot(IdMixin, Base):
    """A named piece of evidence a control needs, with freshness and verification rules."""

    __tablename__ = "evidence_slot"

    control_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requirement.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    evidence_type: Mapped[str] = mapped_column(String(40))
    required: Mapped[bool] = mapped_column(default=True)
    freshness_days: Mapped[int | None] = mapped_column()
    min_confidence: Mapped[float | None] = mapped_column(Float)
    rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(default=0)

    control: Mapped[Control | None] = relationship(back_populates="slots")
