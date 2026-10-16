import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime
from assayr.identity.models import User

DOC_TYPES = ("policy", "procedure", "guideline")
DOC_STATUSES = ("draft", "approved", "retired")


class Document(IdMixin, TimestampMixin, Base):
    """A policy, procedure or guideline in the document register (A.5.1, A.5.37)."""

    __tablename__ = "document"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_document_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    doc_type: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    version_label: Mapped[str] = mapped_column(String(20), default="1.0")
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_due: Mapped[date | None] = mapped_column(Date)
    current_sha256: Mapped[str | None] = mapped_column(String(64))
    filename: Mapped[str | None] = mapped_column(String(255))
    mime: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[int | None] = mapped_column(BigInteger)

    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id], lazy="joined")
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id], lazy="joined")


class DocumentControl(Base):
    """Links a document to a control it supports (ISO or NIA-only)."""

    __tablename__ = "document_control"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), primary_key=True
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("control.id", ondelete="CASCADE"), primary_key=True
    )
