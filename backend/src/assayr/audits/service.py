"""Which controls an audit can cover, and adding them to an audit."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audits.models import RESULTS, SOC2_RESULTS, Audit, AuditItem
from assayr.catalogue.frameworks import display_ref, load_soc2
from assayr.catalogue.models import Control, iso_controls
from assayr.catalogue.soc2 import criterion_of
from assayr.nia.service import nia_views

_NIA_REF = re.compile(r"([A-Z]{2})\s?(\d{1,3})")


@dataclass(frozen=True)
class CatalogueRow:
    ref: str
    domain_code: str
    domain: str
    requirement: str | None
    sub_domain: str | None = None
    assessment_area: str | None = None


def results_for(framework: str) -> tuple[str, ...]:
    return SOC2_RESULTS if framework == "soc2" else RESULTS


def normalise_ref(text: str) -> str:
    """ "su5", " SU 5 " -> "SU 5"; "a.5.1" -> "A.5.1"."""
    compact = " ".join(str(text).split()).upper()
    match = _NIA_REF.fullmatch(compact)
    return f"{match[1]} {int(match[2])}" if match else compact


def catalogue_rows(db: Session, scope_id: uuid.UUID, framework: str) -> list[CatalogueRow]:
    if framework == "iso27001":
        controls = db.scalars(
            select(Control).where(Control.scope_id == scope_id, iso_controls()).order_by(Control.sort_order)
        )
        return [CatalogueRow(c.code, c.theme or "Clauses", c.theme or "Clauses", None) for c in controls]
    if framework == "iso42001":
        controls = db.scalars(
            select(Control)
            .where(Control.scope_id == scope_id, Control.framework == "iso42001")
            .order_by(Control.sort_order)
        )
        return [CatalogueRow(display_ref(c.code), c.theme or "", c.theme or "", None) for c in controls]
    if framework == "soc2":
        return soc2_rows(db, scope_id)
    return [
        CatalogueRow(v.ref, v.domain, v.domain_name, "M" if v.mandatory else "A")
        for v in nia_views(db, scope_id)
    ]


def soc2_rows(db: Session, scope_id: uuid.UUID) -> list[CatalogueRow]:
    """Control activities, plus the criteria that have no activities yet, in criterion order."""
    controls = list(
        db.scalars(
            select(Control)
            .where(Control.scope_id == scope_id, Control.framework == "soc2")
            .order_by(Control.sort_order)
        ).unique()
    )
    with_activities = {criterion_of(c.code) for c in controls if c.code.count(".") == 2}
    series = {s["ref"]: s["title"] for s in load_soc2()["series"]}
    rows = []
    for c in controls:
        if c.code.count(".") == 1 and c.code in with_activities:
            continue
        criterion = criterion_of(c.code)
        title = series.get(criterion.split(".")[0], c.theme or "")
        rows.append(CatalogueRow(c.code, criterion.split(".")[0], title, None, criterion, c.test_procedure))
    return rows


def add_items(db: Session, audit: Audit, rows: list[CatalogueRow]) -> int:
    """Adds the controls not already in the audit, after the existing ones. Returns how many were added."""
    existing = {i.ref for i in audit.items}
    order = max((i.sort_order for i in audit.items), default=0)
    added = 0
    for row in rows:
        if row.ref in existing:
            continue
        order += 1
        audit.items.append(
            AuditItem(
                ref=row.ref,
                sort_order=order,
                domain=row.domain,
                sub_domain=row.sub_domain or row.domain,
                requirement=row.requirement,
                assessment_area=row.assessment_area,
            )
        )
        existing.add(row.ref)
        added += 1
    db.flush()
    return added


def counts(audit: Audit) -> dict[str, int]:
    results = [i.result for i in audit.items]
    return {
        "total": len(results),
        "tested": sum(1 for r in results if r),
        "pass": results.count("pass"),
        "partial": results.count("partial"),
        "fail": results.count("fail"),
        "na": results.count("na"),
        "no_exception": results.count("no_exception"),
        "exception": results.count("exception"),
        "not_tested": results.count("not_tested"),
    }
