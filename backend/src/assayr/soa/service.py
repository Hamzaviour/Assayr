"""The working Statement of Applicability: applicability, justification sources and traceability checks."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, iso_controls
from assayr.config import Settings
from assayr.risk.methodology import band_for
from assayr.risk.models import Risk, RiskControl
from assayr.risk.service import definition_of, latest_assessment
from assayr.scoring.service import slot_views
from assayr.soa.schemas import (
    MANUAL_SOURCES,
    ExcludedMitigatingOut,
    SoaChecksOut,
    SoaItemOut,
    SoaOut,
    SourceOut,
)


def active_risk_links(db: Session, scope_id: uuid.UUID) -> dict[uuid.UUID, list[str]]:
    """Control id → codes of the open risks that list it as a mitigating control."""
    rows = db.execute(
        select(RiskControl.control_id, Risk.code)
        .join(Risk, RiskControl.risk_id == Risk.id)
        .where(Risk.scope_id == scope_id, Risk.closed_at.is_(None))
        .order_by(Risk.seq)
    )
    links: dict[uuid.UUID, list[str]] = {}
    for control_id, code in rows:
        links.setdefault(control_id, []).append(code)
    return links


def untreated_risks(db: Session, scope_id: uuid.UUID) -> list[str]:
    """Open risks whose current level is above appetite and that have no treatment decision."""
    codes = []
    for risk in db.scalars(
        select(Risk).where(Risk.scope_id == scope_id, Risk.closed_at.is_(None)).order_by(Risk.seq)
    ).unique():
        latest = latest_assessment(db, risk)
        if latest is None or risk.treatment_option is not None:
            continue
        if band_for(definition_of(db, latest), latest.current_l, latest.current_c)["above_appetite"]:
            codes.append(risk.code)
    return codes


def soa_items(db: Session, scope_id: uuid.UUID, settings: Settings, today: date) -> list[SoaItemOut]:
    links = active_risk_links(db, scope_id)
    items = []
    for control in db.scalars(
        select(Control).where(Control.scope_id == scope_id, iso_controls()).order_by(Control.sort_order)
    ).unique():
        sources = [
            SourceOut(kind="risk", label=f"Risk {code}", ref=code) for code in links.get(control.id, [])
        ]
        sources += [
            SourceOut(kind=kind, label=MANUAL_SOURCES[kind])
            for kind in (control.soa_sources or [])
            if kind in MANUAL_SOURCES
        ]
        required = [v for v in slot_views(db, control, today, settings) if v.required]
        items.append(
            SoaItemOut(
                code=control.code,
                title=control.title,
                theme=control.theme,
                applicable=control.applicable,
                sources=sources,
                justification=control.soa_justification,
                exclusion_reason=control.exclusion_reason,
                implementation_status=control.implementation_status,
                status=control.status,
                evidence_verified=sum(v.state in ("verified", "expiring") for v in required),
                evidence_required=len(required),
                owner=control.owner.full_name if control.owner else None,
            )
        )
    return items


def soa_checks(items: list[SoaItemOut], untreated: list[str]) -> SoaChecksOut:
    orphans = [i.code for i in items if i.applicable and not i.sources]
    excluded = [
        ExcludedMitigatingOut(code=i.code, risks=[s.ref for s in i.sources if s.kind == "risk"])
        for i in items
        if not i.applicable and any(s.kind == "risk" for s in i.sources)
    ]
    return SoaChecksOut(
        orphans=orphans,
        excluded_mitigating=excluded,
        untreated_risks=untreated,
        ok=not orphans and not excluded and not untreated,
    )


def soa_view(db: Session, scope_id: uuid.UUID, settings: Settings, today: date) -> SoaOut:
    items = soa_items(db, scope_id, settings, today)
    return SoaOut(items=items, checks=soa_checks(items, untreated_risks(db, scope_id)))
