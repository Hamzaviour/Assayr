import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, IdMixin, UTCDateTime


class SoaVersion(IdMixin, Base):
    """A submitted Statement of Applicability. Entries are frozen when it is submitted."""

    __tablename__ = "soa_version"
    __table_args__ = (UniqueConstraint("scope_id", "version_no", name="uq_soa_version_scope_no"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    entries: Mapped[list] = mapped_column(JSON)
    prepared_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    prepared_at: Mapped[datetime] = mapped_column(UTCDateTime)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decision_note: Mapped[str | None] = mapped_column(Text)
