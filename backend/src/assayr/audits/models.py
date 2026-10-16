import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime
from assayr.identity.models import User

FRAMEWORKS = ("iso27001", "nia-2.1")
RESULTS = ("pass", "fail", "partial", "na")
TEST_TYPES = ("DA", "OEA", "Both")


class Audit(IdMixin, TimestampMixin, Base):
    """An internal audit (ISO/IEC 27001 clause 9.2, or a Qatar NIA internal audit)."""

    __tablename__ = "audit"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    framework: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    auditor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    scope_note: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )

    auditor: Mapped[User | None] = relationship(foreign_keys=[auditor_id], lazy="joined")
    completed_by: Mapped[User | None] = relationship(foreign_keys=[completed_by_id], lazy="joined")
    items: Mapped[list["AuditItem"]] = relationship(
        back_populates="audit", order_by="AuditItem.sort_order", cascade="all, delete-orphan"
    )


class AuditItem(IdMixin, Base):
    """One audited control: how it was tested and the result (the auditor's own wording)."""

    __tablename__ = "audit_item"
    __table_args__ = (UniqueConstraint("audit_id", "ref", name="uq_audit_item_audit_ref"),)

    audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(Integer)
    domain: Mapped[str] = mapped_column(String(200))
    sub_domain: Mapped[str] = mapped_column(String(200))
    assessment_area: Mapped[str | None] = mapped_column(Text)
    test_type: Mapped[str | None] = mapped_column(String(10))
    requirement: Mapped[str | None] = mapped_column(String(1))
    result: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)

    audit: Mapped[Audit] = relationship(back_populates="items")
