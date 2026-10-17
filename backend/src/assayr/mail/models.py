"""Mail server settings (one row) and a log of every email Assayr tried to send."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from assayr.db import Base, IdMixin, UTCDateTime, utcnow

SECURITY = ("starttls", "ssl", "none")


class MailSettings(IdMixin, Base):
    __tablename__ = "mail_settings"

    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=587)
    security: Mapped[str] = mapped_column(String(10), default="starttls")
    username: Mapped[str | None] = mapped_column(String(255))
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    from_address: Mapped[str | None] = mapped_column(String(320))
    from_name: Mapped[str | None] = mapped_column(String(200))
    base_url: Mapped[str | None] = mapped_column(String(500))
    digest_hour: Mapped[int] = mapped_column(Integer, default=7)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class MailLog(IdMixin, Base):
    __tablename__ = "mail_log"
    __table_args__ = (UniqueConstraint("user_id", "kind", "day", name="uq_mail_log_user_kind_day"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    day: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))
    error: Mapped[str | None] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
