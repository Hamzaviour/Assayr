from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Column, Date, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.assets.models import Asset
from assayr.catalogue.models import Control
from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow
from assayr.identity.models import User

risk_asset = Table(
    "risk_asset",
    Base.metadata,
    Column("risk_id", ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", ForeignKey("asset.id", ondelete="CASCADE"), primary_key=True),
)
risk_threat = Table(
    "risk_threat",
    Base.metadata,
    Column("risk_id", ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True),
    Column("threat_id", ForeignKey("threat.id", ondelete="CASCADE"), primary_key=True),
)
risk_vulnerability = Table(
    "risk_vulnerability",
    Base.metadata,
    Column("risk_id", ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True),
    Column("vulnerability_id", ForeignKey("vulnerability.id", ondelete="CASCADE"), primary_key=True),
)


class MethodologyVersion(IdMixin, Base):
    """A frozen risk methodology definition; assessments record which version rated them."""

    __tablename__ = "methodology_version"

    version_no: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(120))
    definition: Mapped[dict] = mapped_column(JSON)
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime)


class Threat(IdMixin, Base):
    __tablename__ = "threat"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)


class Vulnerability(IdMixin, Base):
    __tablename__ = "vulnerability"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)


class RiskTemplate(IdMixin, Base):
    """A ready-made risk scenario (Assayr-authored) so nobody starts from a blank page."""

    __tablename__ = "risk_template"

    code: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    scenario: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60))
    threat_codes: Mapped[list] = mapped_column(JSON)
    vulnerability_codes: Mapped[list] = mapped_column(JSON)
    control_codes: Mapped[list] = mapped_column(JSON)
    likelihood: Mapped[int] = mapped_column(Integer)
    consequence: Mapped[dict] = mapped_column(JSON)


class Risk(IdMixin, TimestampMixin, Base):
    __tablename__ = "risk"
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_risk_scope_code"),)

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    seq: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    approach: Mapped[str] = mapped_column(String(10), default="event")
    category: Mapped[str | None] = mapped_column(String(60))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    treatment_option: Mapped[str | None] = mapped_column(String(10))
    treatment_note: Mapped[str | None] = mapped_column(Text)
    treatment_budget: Mapped[str | None] = mapped_column(String(100))
    treatment_due: Mapped[date | None] = mapped_column(Date)
    review_due: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    close_reason: Mapped[str | None] = mapped_column(Text)
    template_code: Mapped[str | None] = mapped_column(String(20))

    owner: Mapped[User | None] = relationship(lazy="joined")
    control_links: Mapped[list[RiskControl]] = relationship(
        back_populates="risk", cascade="all, delete-orphan", lazy="selectin"
    )
    assets: Mapped[list[Asset]] = relationship(secondary=risk_asset, lazy="selectin", order_by=Asset.seq)
    threats: Mapped[list[Threat]] = relationship(secondary=risk_threat, lazy="selectin", order_by=Threat.code)
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        secondary=risk_vulnerability, lazy="selectin", order_by=Vulnerability.code
    )


class RiskControl(Base):
    """A control that mitigates a risk, and which axis (likelihood or consequence) it reduces."""

    __tablename__ = "risk_control"

    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk.id", ondelete="CASCADE"), primary_key=True)
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("control.id", ondelete="CASCADE"), primary_key=True
    )
    axis: Mapped[str] = mapped_column(String(12), default="likelihood")

    risk: Mapped[Risk] = relationship(back_populates="control_links")
    control: Mapped[Control] = relationship(lazy="joined")


class RiskAssessment(IdMixin, Base):
    """One rating of a risk. Open (finalized_at is null) while being worked on; frozen once finalized."""

    __tablename__ = "risk_assessment"

    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk.id", ondelete="CASCADE"), index=True)
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_version.id"))
    likelihood: Mapped[int | None] = mapped_column(Integer)
    consequence: Mapped[dict | None] = mapped_column(JSON)
    current_l: Mapped[int | None] = mapped_column(Integer)
    current_c: Mapped[int | None] = mapped_column(Integer)
    current_reason: Mapped[str | None] = mapped_column(Text)
    suggested: Mapped[dict | None] = mapped_column(JSON)
    target_l: Mapped[int | None] = mapped_column(Integer)
    target_c: Mapped[int | None] = mapped_column(Integer)
    rationale: Mapped[str | None] = mapped_column(Text)
    assessed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class RiskAcceptance(IdMixin, Base):
    __tablename__ = "risk_acceptance"

    risk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("risk_assessment.id", ondelete="CASCADE"))
    band: Mapped[str] = mapped_column(String(20))
    score: Mapped[int] = mapped_column(Integer)
    authority: Mapped[str] = mapped_column(String(20))
    statement: Mapped[str] = mapped_column(Text)
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class RiskSnapshot(IdMixin, Base):
    """A frozen copy of the register (clause 8.2 record)."""

    __tablename__ = "risk_snapshot"

    scope_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    taken_at: Mapped[datetime] = mapped_column(UTCDateTime)
    taken_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"))
    methodology_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("methodology_version.id"))
    rows: Mapped[list] = mapped_column(JSON)
