"""Audit findings and their corrective actions (CAPA): root cause, actions with evidence, verification."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow
from assayr.identity.models import User

GRADES = ("major", "minor", "observation", "ofi")
NONCONFORMITIES = ("major", "minor")
STATUSES = ("open", "action_planned", "awaiting_verification", "closed")
SOURCES = ("internal_audit",)


class Finding(IdMixin, TimestampMixin, Base):
    __tablename__ = "finding"
    __table_args__ = (
        UniqueConstraint("scope_id", "code", name="uq_finding_scope_code"),
        UniqueConstraint("audit_item_id", name="uq_finding_audit_item"),
    )

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(30), default="internal_audit")
    audit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audit.id", ondelete="SET NULL"))
    audit_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("audit_item.id", ondelete="SET NULL"))
    framework: Mapped[str | None] = mapped_column(String(20))
    ref: Mapped[str | None] = mapped_column(String(20))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="open")
    root_cause: Mapped[str | None] = mapped_column(Text)
    correction: Mapped[str | None] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    raised_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    raised_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    risk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("risk.id", ondelete="SET NULL"))

    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id], lazy="joined")
    raised_by: Mapped[User | None] = relationship(foreign_keys=[raised_by_id], lazy="joined")
    actions: Mapped[list["CorrectiveAction"]] = relationship(
        back_populates="finding",
        order_by="CorrectiveAction.seq",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    verifications: Mapped[list["FindingVerification"]] = relationship(
        order_by="FindingVerification.verified_at", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_nonconformity(self) -> bool:
        return self.grade in NONCONFORMITIES


class CorrectiveAction(IdMixin, TimestampMixin, Base):
    __tablename__ = "corrective_action"
    __table_args__ = (UniqueConstraint("finding_id", "seq", name="uq_corrective_action_finding_seq"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("finding.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")
    done_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    done_note: Mapped[str | None] = mapped_column(Text)

    finding: Mapped[Finding] = relationship(back_populates="actions")
    owner: Mapped[User | None] = relationship(lazy="joined")
    files: Mapped[list["CorrectiveActionFile"]] = relationship(
        order_by="CorrectiveActionFile.uploaded_at", cascade="all, delete-orphan", lazy="selectin"
    )


class CorrectiveActionFile(IdMixin, Base):
    __tablename__ = "corrective_action_file"

    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("corrective_action.id", ondelete="CASCADE"))
    sha256: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str | None] = mapped_column(String(100))
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    uploaded_by: Mapped[User | None] = relationship(lazy="joined")


class FindingVerification(IdMixin, Base):
    """One verification of effectiveness: effective closes the finding, not effective sends it back."""

    __tablename__ = "finding_verification"

    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("finding.id", ondelete="CASCADE"))
    verifier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    effective: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    verifier: Mapped[User | None] = relationship(lazy="joined")
