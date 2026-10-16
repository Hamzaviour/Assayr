"""Which controls an audit can cover, and adding them to an audit."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audits.models import Audit, AuditItem
from assayr.catalogue.models import Control, iso_controls
from assayr.nia.service import nia_views

_NIA_REF = re.compile(r"([A-Z]{2})\s?(\d{1,3})")


@dataclass(frozen=True)
class CatalogueRow:
    ref: str
    domain_code: str
    domain: str
    requirement: str | None


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
    return [
        CatalogueRow(v.ref, v.domain, v.domain_name, "M" if v.mandatory else "A")
        for v in nia_views(db, scope_id)
    ]


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
                sub_domain=row.domain,
                requirement=row.requirement,
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
    }
