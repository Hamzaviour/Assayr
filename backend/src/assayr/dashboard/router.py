"""One call with every number the dashboard shows."""

import uuid
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control, EvidenceSlot, Framework
from assayr.catalogue.router import resolve_scope
from assayr.db import get_session
from assayr.evidence.models import ArtefactLink
from assayr.identity.deps import current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.risk.models import Risk
from assayr.risk.service import risk_row
from assayr.scoring.models import ScoreSnapshot
from assayr.scoring.service import scope_has_evidence, weighted_readiness

router = APIRouter(tags=["dashboard"])
TREND_DAYS = 90
# How the risk statuses the backend computes are grouped on the dashboard.
OPEN = ("draft", "assessed", "review_due", "reassessing")
IN_PROGRESS = ("treatment_planned", "in_treatment")
CLOSED = ("treated", "accepted", "closed")


class GroupRow(BaseModel):
    name: str
    total: int
    compliant: int
    readiness: float | None


class FrameworkRow(BaseModel):
    code: str
    name: str
    version: str
    total: int
    compliant: int
    readiness: float | None
    status_counts: dict[str, int]
    groups: list[GroupRow]


class EvidenceCard(BaseModel):
    needs_attention: int
    ok: int
    total: int


class RiskCard(BaseModel):
    open: int
    in_progress: int
    closed: int
    total: int
    by_level: dict[str, int]


class TrendPoint(BaseModel):
    date: date
    readiness: float


class DashboardOut(BaseModel):
    frameworks: list[FrameworkRow]
    evidence: EvidenceCard
    risks: RiskCard | None
    unowned_controls: int
    trend: list[TrendPoint]


def _framework_row(db: Session, controls: list[Control], has_evidence: bool) -> FrameworkRow:
    counts = Counter(c.status for c in controls)
    framework = db.scalar(select(Framework).order_by(Framework.created_at))
    return FrameworkRow(
        code=framework.code if framework else "iso27001",
        name=framework.name if framework else "ISO/IEC 27001",
        version=framework.version if framework else "2022",
        total=len(controls),
        compliant=counts.get("compliant", 0),
        readiness=weighted_readiness(controls) if has_evidence else None,
        status_counts=dict(counts),
        groups=_groups(controls, has_evidence),
    )


def _groups(controls: list[Control], has_evidence: bool) -> list[GroupRow]:
    """Per Annex A theme, in catalogue order."""
    by_theme: dict[str, list[Control]] = {}
    for control in sorted(controls, key=lambda c: [int(p) if p.isdigit() else p for p in c.code.split(".")]):
        by_theme.setdefault(control.theme or "Other", []).append(control)
    return [
        GroupRow(
            name=theme,
            total=len(group),
            compliant=sum(1 for c in group if c.status == "compliant"),
            readiness=weighted_readiness(group) if has_evidence else None,
        )
        for theme, group in by_theme.items()
    ]


def _evidence_card(db: Session, scope_id: uuid.UUID) -> EvidenceCard:
    states = Counter(
        db.scalars(
            select(ArtefactLink.state)
            .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
            .join(Control, EvidenceSlot.control_id == Control.id)
            .where(Control.scope_id == scope_id, ArtefactLink.state != "superseded")
        )
    )
    return EvidenceCard(
        needs_attention=states.get("in_review", 0) + states.get("rejected", 0),
        ok=states.get("accepted", 0),
        total=sum(states.values()),
    )


def _risk_card(db: Session, scope_id: uuid.UUID) -> RiskCard:
    rows = [risk_row(db, r) for r in db.scalars(select(Risk).where(Risk.scope_id == scope_id)).unique()]
    statuses = Counter(r.status for r in rows)
    levels = Counter((r.current or r.inherent).band for r in rows if (r.current or r.inherent) is not None)
    return RiskCard(
        open=sum(statuses[s] for s in OPEN),
        in_progress=sum(statuses[s] for s in IN_PROGRESS),
        closed=sum(statuses[s] for s in CLOSED),
        total=len(rows),
        by_level=dict(levels),
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> DashboardOut:
    scope = resolve_scope(db, scope_id, grant)
    controls = list(db.scalars(select(Control).where(Control.scope_id == scope.id)))
    since = get_clock(request)() - timedelta(days=TREND_DAYS)
    snapshots = db.scalars(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.scope_id == scope.id, ScoreSnapshot.taken_at >= since)
        .order_by(ScoreSnapshot.taken_at)
    )
    return DashboardOut(
        frameworks=[_framework_row(db, controls, scope_has_evidence(db, scope.id))],
        evidence=_evidence_card(db, scope.id),
        risks=_risk_card(db, scope.id) if has_perm(user, scope.id, Perm.RISKS_READ) else None,
        unowned_controls=sum(1 for c in controls if c.owner_id is None),
        trend=[TrendPoint(date=s.taken_at.date(), readiness=s.readiness) for s in snapshots],
    )
