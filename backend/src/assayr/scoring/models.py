import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, IdMixin, UTCDateTime


class Attestation(IdMixin, Base):
    """The owner's periodic confirmation that a control operates as described."""

    __tablename__ = "attestation"

    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    statement: Mapped[str] = mapped_column(Text)
    attested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime)


class StatusTransition(IdMixin, Base):
    __tablename__ = "status_transition"

    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    trigger: Mapped[str] = mapped_column(String(300))
    at: Mapped[datetime] = mapped_column(UTCDateTime)


class ScoreSnapshot(IdMixin, Base):
    __tablename__ = "score_snapshot"
    __table_args__ = (Index("ix_score_snapshot_scope_taken", "scope_id", "taken_at"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    taken_at: Mapped[datetime] = mapped_column(UTCDateTime)
    readiness: Mapped[float] = mapped_column(Float)
    status_counts: Mapped[dict] = mapped_column(JSON)
