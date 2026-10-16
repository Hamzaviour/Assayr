"""NIA status, derived from the ISO controls each NIA control is mapped to."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, ControlRequirement, Framework, Requirement
from assayr.nia.seed import NIA_CODE

# How far along a control is; an NIA control is only as far along as its least advanced mapped control.
RANK = {"not_started": 0, "in_progress": 1, "in_review": 2, "at_risk": 3, "compliant": 4}


def derive_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_started"
    if "non_compliant" in statuses:
        return "non_compliant"
    return min(statuses, key=lambda s: RANK.get(s, 0))


@dataclass
class NiaControlView:
    ref: str
    domain: str
    domain_name: str
    title: str
    status: str
    score: float | None
    applicable: bool
    mandatory: bool
    mapped: list[Control] = field(default_factory=list)
    requirement: Requirement | None = None


def framework(db: Session) -> Framework | None:
    return db.scalar(select(Framework).where(Framework.code == NIA_CODE))


def _exclusion(req: Requirement, scope_id: uuid.UUID) -> dict | None:
    return (req.attributes or {}).get("exclusions", {}).get(str(scope_id))


def nia_views(db: Session, scope_id: uuid.UUID) -> list[NiaControlView]:
    fw = framework(db)
    if fw is None:
        return []
    reqs = list(
        db.scalars(
            select(Requirement).where(Requirement.framework_id == fw.id).order_by(Requirement.sort_order)
        )
    )
    domains = {r.ref: r for r in reqs if r.kind == "domain"}
    mapped: dict[uuid.UUID, list[Control]] = {}
    rows = db.execute(
        select(ControlRequirement.requirement_id, Control)
        .join(Control, ControlRequirement.control_id == Control.id)
        .join(Requirement, ControlRequirement.requirement_id == Requirement.id)
        .where(Requirement.framework_id == fw.id, Control.scope_id == scope_id)
    ).all()
    for requirement_id, control in rows:
        mapped.setdefault(requirement_id, []).append(control)
    views = []
    for req in (r for r in reqs if r.kind == "control"):
        domain = (req.attributes or {}).get("domain") or req.ref.split()[0]
        controls = sorted(mapped.get(req.id, []), key=lambda c: c.sort_order)
        counted = [c for c in controls if c.status != "excluded"]
        scores = [c.score or 0.0 for c in counted]
        views.append(
            NiaControlView(
                ref=req.ref,
                domain=domain,
                domain_name=domains[domain].title if domain in domains else domain,
                title=req.title,
                status=derive_status([c.status for c in counted]),
                score=round(sum(scores) / len(scores), 1) if scores else None,
                applicable=_exclusion(req, scope_id) is None,
                mandatory=bool((req.attributes or {}).get("mandatory")),
                mapped=controls,
                requirement=req,
            )
        )
    return views


def set_applicability(
    db: Session, scope_id: uuid.UUID, ref: str, *, applicable: bool, reason: str | None, by: str
) -> Requirement:
    fw = framework(db)
    req = db.scalar(select(Requirement).where(Requirement.framework_id == fw.id, Requirement.ref == ref))
    attributes = dict(req.attributes or {})
    exclusions = dict(attributes.get("exclusions", {}))
    if applicable:
        exclusions.pop(str(scope_id), None)
    else:
        exclusions[str(scope_id)] = {"reason": reason, "by": by, "at": datetime.now(UTC).isoformat()}
    attributes["exclusions"] = exclusions
    req.attributes = attributes  # reassign so the JSON change is saved
    return req


def _readiness(views: list[NiaControlView]) -> float | None:
    if not views:
        return None
    return round(sum(v.score or 0.0 for v in views) / len(views), 1)


def nia_framework_row(db: Session, scope_id: uuid.UUID, has_evidence: bool) -> dict:
    """The dashboard/compliance row for NIA, shaped like the ISO row (groups are the 26 domains)."""
    views = nia_views(db, scope_id)
    counted = [v for v in views if v.applicable]
    counts: dict[str, int] = {}
    for v in counted:
        counts[v.status] = counts.get(v.status, 0) + 1
    groups: dict[str, list[NiaControlView]] = {}
    for v in counted:
        groups.setdefault(v.domain_name, []).append(v)
    fw = framework(db)
    return {
        "code": NIA_CODE,
        "name": fw.name if fw else "NIA",
        "version": fw.version if fw else "2.1",
        "total": len(counted),
        "compliant": counts.get("compliant", 0),
        "readiness": _readiness(counted) if has_evidence else None,
        "status_counts": counts,
        "excluded": len(views) - len(counted),
        "groups": [
            {
                "name": name,
                "total": len(group),
                "compliant": sum(1 for v in group if v.status == "compliant"),
                "readiness": _readiness(group) if has_evidence else None,
            }
            for name, group in groups.items()
        ],
    }
