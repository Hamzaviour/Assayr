"""One call with every number the dashboard shows."""

import uuid
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.access import has_perm
from assayr.catalogue.frameworks import ISO42001_CODE, SOC2_CODE
from assayr.catalogue.models import Control, EvidenceSlot, Framework
from assayr.catalogue.router import resolve_scope
from assayr.catalogue.seed import FRAMEWORK_CODE
from assayr.db import get_session, utcnow
from assayr.evidence.models import ArtefactLink
from assayr.findings.schemas import SummaryOut
from assayr.findings.service import summarize
from assayr.identity.deps import current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.nia.service import framework as nia_framework
from assayr.nia.service import nia_framework_row
from assayr.privacy.pdppl import framework_row as pdppl_framework_row
from assayr.risk.models import Risk
from assayr.risk.service import risk_row
from assayr.scoring.models import ScoreSnapshot
from assayr.scoring.service import scope_has_evidence, weighted_readiness
from assayr.training.report_router import training_card

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
    code: str | None = None


class FrameworkRow(BaseModel):
    code: str
    name: str
    version: str
    total: int
    compliant: int
    readiness: float | None
    status_counts: dict[str, int]
    excluded: int
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
    training: dict[str, int] | None = None
    findings: SummaryOut | None = None


def _in_scope(controls: list[Control]) -> list[Control]:
    """Controls excluded in the SoA need no evidence, owner or progress."""
    return [c for c in controls if c.status != "excluded"]


def _framework_row(
    framework: Framework | None,
    controls: list[Control],
    has_evidence: bool,
    fallback: tuple[str, str, str] = ("iso27001", "ISO/IEC 27001", "2022"),
    catalogue_order: bool = False,
) -> FrameworkRow:
    counted = _in_scope(controls)
    counts = Counter(c.status for c in counted)
    return FrameworkRow(
        code=framework.code if framework else fallback[0],
        name=framework.name if framework else fallback[1],
        version=framework.version if framework else fallback[2],
        total=len(counted),
        compliant=counts.get("compliant", 0),
        readiness=weighted_readiness(controls) if has_evidence else None,
        status_counts=dict(counts),
        excluded=len(controls) - len(counted),
        groups=_groups(counted, has_evidence, catalogue_order),
    )


def _code_key(code: str) -> list[tuple[int, int | str]]:
    return [(0, int(p)) if p.isdigit() else (1, p) for p in code.split(".")]


def _groups(controls: list[Control], has_evidence: bool, catalogue_order: bool = False) -> list[GroupRow]:
    """Per Annex A theme (or ISO 42001 objective, SOC 2 series), in catalogue order."""
    by_theme: dict[str, list[Control]] = {}
    key = (lambda c: c.sort_order) if catalogue_order else (lambda c: _code_key(c.code))
    for control in sorted(controls, key=key):
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


def _evidence_card(db: Session, scope_id: uuid.UUID, today: date, warning_days: int) -> EvidenceCard:
    """Needs attention: awaiting review, rejected, or accepted but expired or expiring soon."""
    rows = db.execute(
        select(ArtefactLink.state, ArtefactLink.expires_on)
        .join(EvidenceSlot, ArtefactLink.slot_id == EvidenceSlot.id)
        .join(Control, EvidenceSlot.control_id == Control.id)
        .where(Control.scope_id == scope_id, ArtefactLink.state != "superseded")
    ).all()
    soon = today + timedelta(days=warning_days)
    attention = ok = 0
    for state, expires_on in rows:
        if state in ("in_review", "rejected") or (
            state == "accepted" and expires_on is not None and expires_on <= soon
        ):
            attention += 1
        elif state == "accepted":
            ok += 1
    return EvidenceCard(needs_attention=attention, ok=ok, total=len(rows))


def _daily(snapshots) -> list[TrendPoint]:
    """The last snapshot of each day: readiness can be recorded many times a day."""
    by_day: dict[date, float] = {}
    for s in snapshots:
        by_day[s.taken_at.date()] = s.readiness
    return [TrendPoint(date=d, readiness=r) for d, r in by_day.items()]


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


def _frameworks(db: Session, scope_id: uuid.UUID, controls: list[Control]) -> list[FrameworkRow]:
    has_evidence = scope_has_evidence(db, scope_id)
    by_framework: dict[str, list[Control]] = {}
    for c in controls:
        by_framework.setdefault(c.framework, []).append(c)
    frameworks = {f.code: f for f in db.scalars(select(Framework))}
    rows = [_framework_row(frameworks.get(FRAMEWORK_CODE), by_framework.get("iso27001", []), has_evidence)]
    if nia_framework(db) is not None:
        rows.append(FrameworkRow(**nia_framework_row(db, scope_id, has_evidence)))
    if by_framework.get("iso42001"):
        rows.append(
            _framework_row(
                frameworks.get(ISO42001_CODE),
                by_framework["iso42001"],
                has_evidence,
                (ISO42001_CODE, "ISO/IEC 42001", "2023"),
                catalogue_order=True,
            )
        )
    if by_framework.get("soc2"):
        # Control activities roll up into their criterion, so the row counts criteria only.
        criteria = [c for c in by_framework["soc2"] if c.code.count(".") == 1]
        rows.append(
            _framework_row(
                frameworks.get(SOC2_CODE),
                criteria,
                has_evidence,
                (SOC2_CODE, "SOC 2", "Security"),
                catalogue_order=True,
            )
        )
    rows.append(FrameworkRow(**pdppl_framework_row(db, scope_id, utcnow())))
    return rows


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
    now = get_clock(request)()
    since = now - timedelta(days=TREND_DAYS)
    snapshots = db.scalars(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.scope_id == scope.id, ScoreSnapshot.taken_at >= since)
        .order_by(ScoreSnapshot.taken_at)
    )
    return DashboardOut(
        frameworks=_frameworks(db, scope.id, controls),
        evidence=_evidence_card(db, scope.id, now.date(), request.app.state.settings.expiry_warning_days),
        risks=_risk_card(db, scope.id) if has_perm(user, scope.id, Perm.RISKS_READ) else None,
        unowned_controls=sum(
            1 for c in _in_scope(controls) if c.owner_id is None and c.framework == "iso27001"
        ),
        trend=_daily(snapshots),
        training=training_card(db, scope.id, now.date())
        if has_perm(user, scope.id, Perm.TRAINING_MANAGE)
        else None,
        findings=SummaryOut(**summarize(db, scope.id, now.date())),
    )
