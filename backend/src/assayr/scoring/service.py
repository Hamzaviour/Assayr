"""Derive slot states, control status and score, scope readiness (vault: Compliance Scoring Model)."""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, EvidenceSlot
from assayr.catalogue.seed import FREQ_DAYS
from assayr.config import Settings
from assayr.evidence.models import ArtefactLink
from assayr.scoring.models import Attestation, ScoreSnapshot, StatusTransition

SLOT_SCORE = {
    "verified": 1.0,
    "expiring": 0.8,
    "pending": 0.5,
    "expired_grace": 0.4,
    "rejected": 0.0,
    "missing": 0.0,
    "expired": 0.0,
}
NON_COMPLIANT_CAP = 40.0
UNATTESTED_FACTOR = 0.9


@dataclass(frozen=True)
class SlotView:
    slot_id: uuid.UUID | None
    required: bool
    state: str
    link: ArtefactLink | None


class ControlScore(NamedTuple):
    status: str
    score: float
    views: list[SlotView]
    attested: bool


def freshness_state(expires_on: date | None, today: date, warning_days: int, grace_days: int) -> str:
    if expires_on is None or today < expires_on - timedelta(days=warning_days):
        return "verified"
    if today < expires_on:
        return "expiring"
    if today < expires_on + timedelta(days=grace_days):
        return "expired_grace"
    return "expired"


def slot_view(slot: EvidenceSlot, links: list[ArtefactLink], today: date, settings: Settings) -> SlotView:
    live = [link for link in links if link.state != "superseded"]
    accepted = [link for link in live if link.state == "accepted"]
    if accepted:
        best = max(accepted, key=lambda link: (link.evidence_date or date.min, link.created_at))
        warning = settings.expiry_warning_days
        if slot.freshness_days:
            # A fixed 30-day warning would mark monthly evidence "expiring" the day after upload.
            warning = min(warning, slot.freshness_days // 4)
        state = freshness_state(best.expires_on, today, warning, settings.evidence_grace_days)
        return SlotView(slot.id, slot.required, state, best)
    for states, view_state in ((("verifying", "in_review"), "pending"), (("rejected",), "rejected")):
        matching = [link for link in live if link.state in states]
        if matching:
            return SlotView(
                slot.id, slot.required, view_state, max(matching, key=lambda link: link.created_at)
            )
    return SlotView(slot.id, slot.required, "missing", None)


def slot_views(db: Session, control: Control, today: date, settings: Settings) -> list[SlotView]:
    links = db.scalars(
        select(ArtefactLink)
        .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .where(EvidenceSlot.control_id == control.id)
    ).unique()
    by_slot: dict[uuid.UUID, list[ArtefactLink]] = {}
    for link in links:
        by_slot.setdefault(link.slot_id, []).append(link)
    return [slot_view(slot, by_slot.get(slot.id, []), today, settings) for slot in control.slots]


def latest_attestation(db: Session, control: Control) -> Attestation | None:
    return db.scalar(
        select(Attestation)
        .where(Attestation.control_id == control.id)
        .order_by(Attestation.attested_at.desc())
        .limit(1)
    )


def attestation_days(control: Control) -> int:
    return FREQ_DAYS.get(control.review_frequency or "", 365)


def evaluate(
    implementation_status: str, views: list[SlotView], attested: bool, has_any_link: bool
) -> ControlScore:
    required = [v for v in views if v.required]
    states = [v.state for v in required]
    if any(s == "expired" for s in states):
        status = "non_compliant"
    elif not has_any_link and implementation_status == "not_started":
        status = "not_started"
    elif any(s in ("missing", "rejected") for s in states):
        status = "in_progress"
    elif any(s == "pending" for s in states):
        status = "in_review"
    elif any(s in ("expiring", "expired_grace") for s in states) or not attested:
        status = "at_risk"
    else:
        status = "compliant"
    base = sum(SLOT_SCORE[s] for s in states) / len(states) * 100 if states else 100.0
    score = base * (1.0 if attested else UNATTESTED_FACTOR)
    if status == "non_compliant":
        score = min(score, NON_COMPLIANT_CAP)
    elif status == "not_started":
        score = 0.0  # a control nobody has touched never counts toward readiness, even without required slots
    return ControlScore(status=status, score=round(score, 1), views=views, attested=attested)


def recompute_control(
    db: Session, control: Control, now: datetime, settings: Settings, trigger: str
) -> ControlScore:
    views = slot_views(db, control, now.date(), settings)
    attestation = latest_attestation(db, control)
    attested = attestation is not None and attestation.valid_until > now
    has_any_link = any(v.link is not None for v in views)
    result = evaluate(control.implementation_status, views, attested, has_any_link)
    if result.status != control.status:
        db.add(
            StatusTransition(
                control_id=control.id,
                from_status=control.status,
                to_status=result.status,
                trigger=trigger[:300],
                at=now,
            )
        )
        control.status = result.status
    control.score = result.score
    return result


def weighted_readiness(controls: list[Control]) -> float | None:
    counted = [c for c in controls if c.status != "excluded"]
    if not counted:
        return None
    return round(sum(c.score or 0.0 for c in counted) / len(counted), 1)


def scope_has_evidence(db: Session, scope_id: uuid.UUID) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(ArtefactLink)
        .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .join(Control, EvidenceSlot.control_id == Control.id)
        .where(Control.scope_id == scope_id)
    )
    return bool(count)


def take_snapshot(db: Session, scope_id: uuid.UUID, now: datetime) -> ScoreSnapshot | None:
    """One snapshot per scope per day, plus one whenever readiness changes during the day."""
    controls = list(db.scalars(select(Control).where(Control.scope_id == scope_id)))
    readiness = weighted_readiness(controls)
    if readiness is None:
        return None
    last = db.scalar(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.scope_id == scope_id)
        .order_by(ScoreSnapshot.taken_at.desc())
        .limit(1)
    )
    if last is not None and last.taken_at.date() == now.date() and last.readiness == readiness:
        return None
    snapshot = ScoreSnapshot(
        scope_id=scope_id,
        taken_at=now,
        readiness=readiness,
        status_counts=dict(Counter(c.status for c in controls)),
    )
    db.add(snapshot)
    return snapshot


def recompute_scope(
    db: Session, scope_id: uuid.UUID, now: datetime, settings: Settings, trigger: str = "Scheduled check"
) -> None:
    for control in db.scalars(select(Control).where(Control.scope_id == scope_id)):
        recompute_control(db, control, now, settings, trigger)
    db.flush()
    take_snapshot(db, scope_id, now)
