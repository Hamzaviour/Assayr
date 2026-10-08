from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.catalogue.models import EvidenceSlot
from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow


class Artefact(IdMixin, TimestampMixin, Base):
    """A piece of evidence (a document or file) with one or more immutable versions."""

    __tablename__ = "artefact"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )

    versions: Mapped[list[ArtefactVersion]] = relationship(
        back_populates="artefact", cascade="all, delete-orphan", order_by="ArtefactVersion.version_no"
    )


class ArtefactVersion(IdMixin, Base):
    __tablename__ = "artefact_version"
    __table_args__ = (
        UniqueConstraint("artefact_id", "version_no", name="uq_artefact_version_artefact_no"),
        Index("ix_artefact_version_sha256", "sha256"),
    )

    artefact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artefact.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str | None] = mapped_column(String(100))
    evidence_date: Mapped[date | None] = mapped_column(Date)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extract_error: Mapped[str | None] = mapped_column(String(300))
    page_count: Mapped[int | None] = mapped_column(Integer)
    doc_metadata: Mapped[dict | None] = mapped_column(JSON)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    artefact: Mapped[Artefact] = relationship(back_populates="versions")


class ArtefactLink(IdMixin, Base):
    """One version of an artefact offered as evidence for one slot, with its verification outcome."""

    __tablename__ = "artefact_link"
    __table_args__ = (UniqueConstraint("version_id", "slot_id", name="uq_artefact_link_version_slot"),)

    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artefact_version.id", ondelete="CASCADE"))
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence_slot.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="verifying")
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_date: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    version: Mapped[ArtefactVersion] = relationship(lazy="joined")
    slot: Mapped[EvidenceSlot] = relationship(lazy="joined")


class VerificationRun(IdMixin, Base):
    __tablename__ = "verification_run"

    link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artefact_link.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    rules_version: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float | None] = mapped_column(Float)
    verdict: Mapped[str | None] = mapped_column(String(10))

    results: Mapped[list[RuleResult]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="RuleResult.seq"
    )


class RuleResult(IdMixin, Base):
    __tablename__ = "rule_result"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_run.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10))
    weight: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    fix_hint: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text)
