"""AI systems register (ISO/IEC 42001 A.4, A.6) and AI system impact assessments (6.1.4, 8.4, A.5)."""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime
from assayr.identity.models import User

SOURCES = ("in_house", "third_party", "open_source")
LIFECYCLES = ("planned", "development", "validation", "deployed", "retired")
SYSTEM_STATUSES = ("active", "retired")
# The ten parts of an AI system impact assessment, in the order they are filled in.
SECTIONS = (
    "intended_use",
    "affected",
    "individual_impacts",
    "societal_impacts",
    "fairness",
    "transparency",
    "oversight",
    "safety",
    "data_quality",
    "conclusion",
)
SECTION_LABELS = {
    "intended_use": "intended use and foreseeable misuse",
    "affected": "affected individuals and groups",
    "individual_impacts": "impacts on individuals",
    "societal_impacts": "societal impacts",
    "fairness": "fairness and bias",
    "transparency": "transparency and explainability",
    "oversight": "human oversight",
    "safety": "safety and reliability",
    "data_quality": "data quality and provenance",
    "conclusion": "conclusion",
}


class AiSystem(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_system"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_ai_system_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(200))
    model_type: Mapped[str | None] = mapped_column(String(100))
    lifecycle: Mapped[str] = mapped_column(String(20))
    risk_level: Mapped[int] = mapped_column(Integer)
    uses_personal_data: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_categories: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    asset_ids: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    human_oversight: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")

    owner: Mapped[User | None] = relationship(lazy="joined")
    assessment: Mapped["AiImpactAssessment | None"] = relationship(
        back_populates="system", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class AiImpactAssessment(IdMixin, TimestampMixin, Base):
    """The impact assessment of one AI system; same lifecycle as a DPIA (draft, in review, approved)."""

    __tablename__ = "ai_impact_assessment"

    ai_system_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_system.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="draft")
    intended_use: Mapped[str | None] = mapped_column(Text)
    affected: Mapped[str | None] = mapped_column(Text)
    individual_impacts: Mapped[str | None] = mapped_column(Text)
    societal_impacts: Mapped[str | None] = mapped_column(Text)
    fairness: Mapped[str | None] = mapped_column(Text)
    transparency: Mapped[str | None] = mapped_column(Text)
    oversight: Mapped[str | None] = mapped_column(Text)
    safety: Mapped[str | None] = mapped_column(Text)
    data_quality: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_due: Mapped[date | None] = mapped_column(Date)

    system: Mapped[AiSystem] = relationship(back_populates="assessment")
    approved_by: Mapped[User | None] = relationship(lazy="joined")
    impacts: Mapped[list["AiImpact"]] = relationship(
        back_populates="assessment",
        order_by="AiImpact.created_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AiImpact(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_impact"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_impact_assessment.id", ondelete="CASCADE")
    )
    area: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(500))
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    mitigation: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    risk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("risk.id", ondelete="SET NULL"))

    assessment: Mapped[AiImpactAssessment] = relationship(back_populates="impacts")
    owner: Mapped[User | None] = relationship(lazy="joined")
