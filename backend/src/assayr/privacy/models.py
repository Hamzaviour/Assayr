import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.assets.models import Asset
from assayr.db import Base, IdMixin, TimestampMixin
from assayr.identity.models import User

LAWFUL_BASES = (
    "consent",
    "contract",
    "legal_obligation",
    "vital_interest",
    "public_interest",
    "legitimate_interest",
)
DATA_SUBJECTS = (
    "employees",
    "customers",
    "suppliers",
    "visitors",
    "children",
    "patients",
    "students",
    "public",
    "other",
)
ACTIVITY_STATUSES = ("draft", "active", "retired")


class ProcessingActivity(IdMixin, TimestampMixin, Base):
    """One entry in the record of processing activities (Qatar PDPPL; ISO 27001 A.5.34)."""

    __tablename__ = "processing_activity"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_processing_activity_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str | None] = mapped_column(Text)
    data_subjects: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    data_categories: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    lawful_basis: Mapped[str] = mapped_column(String(30))
    recipients: Mapped[str | None] = mapped_column(Text)
    cross_border: Mapped[bool] = mapped_column(Boolean, default=False)
    transfer_countries: Mapped[str | None] = mapped_column(String(300))
    retention: Mapped[str | None] = mapped_column(String(300))
    security_measures: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    review_due: Mapped[date | None] = mapped_column(Date)

    owner: Mapped[User | None] = relationship(lazy="joined")
    assets: Mapped[list[Asset]] = relationship(secondary="processing_asset", order_by=Asset.seq)
    processors: Mapped[list["Processor"]] = relationship(
        secondary="activity_processor", back_populates="activities", order_by="Processor.name"
    )


class ProcessingAsset(Base):
    """Where an activity's personal data is stored or processed."""

    __tablename__ = "processing_asset"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_activity.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("asset.id", ondelete="CASCADE"), primary_key=True)


SECURITY_RESULTS = ("satisfactory", "concerns", "unsatisfactory")


class Processor(IdMixin, TimestampMixin, Base):
    """A processor or vendor that handles personal data for the organisation (PDPPL processor duties)."""

    __tablename__ = "processor"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    service: Mapped[str | None] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(100))
    data_categories: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    dpa_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    dpa_date: Mapped[date | None] = mapped_column(Date)
    dpa_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document.id", ondelete="SET NULL"))
    subprocessors: Mapped[str | None] = mapped_column(Text)
    security_review_on: Mapped[date | None] = mapped_column(Date)
    security_result: Mapped[str | None] = mapped_column(String(20))
    risk_level: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(20), default="active")

    activities: Mapped[list[ProcessingActivity]] = relationship(
        secondary="activity_processor", back_populates="processors", order_by=ProcessingActivity.seq
    )


class ActivityProcessor(Base):
    __tablename__ = "activity_processor"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_activity.id", ondelete="CASCADE"), primary_key=True
    )
    processor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processor.id", ondelete="CASCADE"), primary_key=True
    )
