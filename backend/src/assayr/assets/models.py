import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin
from assayr.identity.models import User

ASSET_TYPES = (
    "information",
    "application",
    "server",
    "endpoint",
    "network_device",
    "cloud_service",
    "facility",
    "people",
    "supplier_service",
)
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
LIFECYCLES = ("planned", "in_use", "retired")


class Asset(IdMixin, TimestampMixin, Base):
    """An information or associated asset (A.5.9) used in asset-based risk assessment."""

    __tablename__ = "asset"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_asset_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    classification: Mapped[str] = mapped_column(String(20), default="internal")
    confidentiality: Mapped[int] = mapped_column(Integer, default=3)
    integrity: Mapped[int] = mapped_column(Integer, default=3)
    availability: Mapped[int] = mapped_column(Integer, default=3)
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(String(20), default="in_use")
    holds_pii: Mapped[bool] = mapped_column(default=False, server_default=false())
    pii_categories: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    pii_sensitive: Mapped[bool] = mapped_column(default=False, server_default=false())
    pii_volume: Mapped[str | None] = mapped_column(String(10))

    owner: Mapped[User | None] = relationship(lazy="joined")
