import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.evidence.models import ArtefactLink, VerificationRun
from assayr.identity.models import User
from assayr.verification.rules import run_order

TEXT_PREVIEW_CHARS = 4000


class RuleResultOut(BaseModel):
    seq: int
    code: str
    name: str
    status: str
    reason: str
    fix_hint: str | None
    excerpt: str | None


class LinkOut(BaseModel):
    id: uuid.UUID
    state: str
    confidence: float | None
    evidence_date: date | None
    expires_on: date | None
    slot_id: uuid.UUID
    slot_name: str
    control_code: str
    control_title: str
    artefact_id: uuid.UUID
    version_id: uuid.UUID
    version_no: int
    filename: str
    size: int
    mime: str | None
    uploaded_at: datetime
    uploaded_by: str | None
    decided_by: str | None
    decision_reason: str | None
    rules_planned: int
    rules: list[RuleResultOut]
    text_preview: str | None


class ReviewItemOut(BaseModel):
    link_id: uuid.UUID
    control_code: str
    control_title: str
    slot_name: str
    filename: str
    confidence: float | None
    uploaded_by: str | None
    uploaded_at: datetime


class DecisionIn(BaseModel):
    decision: Literal["accept", "reject"]
    reason: str | None = Field(default=None, max_length=2000)


def latest_run(db: Session, link: ArtefactLink) -> VerificationRun | None:
    return db.scalar(
        select(VerificationRun)
        .where(VerificationRun.link_id == link.id)
        .order_by(VerificationRun.started_at.desc())
        .limit(1)
    )


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    user = db.get(User, user_id) if user_id else None
    return user.full_name if user else None


def link_out(db: Session, link: ArtefactLink) -> LinkOut:
    version, slot = link.version, link.slot
    run = latest_run(db, link)
    text = version.extracted_text
    return LinkOut(
        id=link.id,
        state=link.state,
        confidence=link.confidence,
        evidence_date=link.evidence_date,
        expires_on=link.expires_on,
        slot_id=slot.id,
        slot_name=slot.name,
        control_code=slot.control.code,
        control_title=slot.control.title,
        artefact_id=version.artefact_id,
        version_id=version.id,
        version_no=version.version_no,
        filename=version.filename,
        size=version.size,
        mime=version.mime,
        uploaded_at=version.created_at,
        uploaded_by=_name(db, version.uploaded_by_id),
        decided_by=_name(db, link.decided_by_id),
        decision_reason=link.decision_reason,
        rules_planned=len(run_order(list(slot.rules or []))),
        rules=[RuleResultOut.model_validate(r, from_attributes=True) for r in (run.results if run else [])],
        text_preview=text[:TEXT_PREVIEW_CHARS] if text else None,
    )


def review_item(db: Session, link: ArtefactLink) -> ReviewItemOut:
    return ReviewItemOut(
        link_id=link.id,
        control_code=link.slot.control.code,
        control_title=link.slot.control.title,
        slot_name=link.slot.name,
        filename=link.version.filename,
        confidence=link.confidence,
        uploaded_by=_name(db, link.version.uploaded_by_id),
        uploaded_at=link.version.created_at,
    )
