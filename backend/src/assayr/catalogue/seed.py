"""Load the ISO/IEC 27001:2022 catalogue. Safe to run on every start: it only adds what is missing."""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.iso27001_clauses import CLAUSES
from assayr.catalogue.models import Control, ControlRequirement, EvidenceSlot, Framework, Requirement
from assayr.identity.models import Organization, Scope

SEED_PATH = Path(__file__).resolve().parent / "data" / "iso27001_2022_annex_a.json"
FRAMEWORK_CODE = "ISO27001:2022"
THEME_REF = {"Organizational": "A.5", "People": "A.6", "Physical": "A.7", "Technological": "A.8"}
THEME_TITLE = {
    "A.5": "Organizational controls",
    "A.6": "People controls",
    "A.7": "Physical controls",
    "A.8": "Technological controls",
}
FREQ_DAYS = {
    "Annual": 365,
    "Semi-annual": 182,
    "Quarterly": 90,
    "Monthly": 31,
    "Continuous": 31,
    "Per release": 90,
    "Per event": 365,
    "Per hire": 365,
    "Per contract": 365,
    "Per project": 365,
    "Per audit": 365,
}


@dataclass
class SeedResult:
    framework_created: bool = False
    requirements_created: int = 0
    controls_created: int = 0
    slots_created: int = 0


def ensure_default_scope(db: Session, org_name: str) -> Scope:
    scope = db.scalar(select(Scope).where(Scope.is_default.is_(True)))
    if scope is not None:
        return scope
    org = db.scalar(select(Organization))
    if org is None:
        org = Organization(id=uuid.uuid4(), name=org_name, aliases=[])
        db.add(org)
    scope = Scope(id=uuid.uuid4(), organization_id=org.id, name="Default ISMS scope", is_default=True)
    db.add(scope)
    db.flush()
    return scope


def seed_iso27001(db: Session, scope: Scope, path: Path = SEED_PATH) -> SeedResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = SeedResult()

    framework = db.scalar(select(Framework).where(Framework.code == FRAMEWORK_CODE))
    if framework is None:
        framework = Framework(id=uuid.uuid4(), code=FRAMEWORK_CODE, name="ISO/IEC 27001", version="2022")
        db.add(framework)
        result.framework_created = True

    requirements = {
        r.ref: r for r in db.scalars(select(Requirement).where(Requirement.framework_id == framework.id))
    }
    order = 0

    def ensure(
        ref: str, title: str, kind: str, parent_ref: str | None, attributes=None, guidance=None
    ) -> Requirement:
        nonlocal order
        order += 1
        if ref in requirements:
            return requirements[ref]
        req = Requirement(
            id=uuid.uuid4(),
            framework_id=framework.id,
            ref=ref,
            title=title,
            kind=kind,
            parent_id=requirements[parent_ref].id if parent_ref else None,
            attributes=attributes or {},
            guidance=guidance,
            sort_order=order,
        )
        db.add(req)
        requirements[ref] = req
        result.requirements_created += 1
        return req

    for ref, title, parent in CLAUSES:
        ensure(ref, title, "clause" if parent else "clause_group", parent)
    for theme_ref, theme_title in THEME_TITLE.items():
        ensure(theme_ref, theme_title, "theme", None)

    existing = set(db.scalars(select(Control.code).where(Control.scope_id == scope.id)))
    links: list[ControlRequirement] = []
    for index, item in enumerate(data["controls"], start=1):
        req = ensure(
            item["ref"],
            item["title"],
            "annex_control",
            THEME_REF[item["theme"]],
            attributes={
                "control_type": item["control_type"],
                "security_properties": item["security_properties"],
                "cybersecurity_concepts": item["cybersecurity_concepts"],
                "new_in_2022": item["new_in_2022"],
            },
            guidance=item["intent"],
        )
        if item["ref"] in existing:
            continue
        control = Control(
            id=uuid.uuid4(),
            scope_id=scope.id,
            code=item["ref"],
            title=item["title"],
            theme=item["theme"],
            description=item["intent"],
            default_owner_role=item["default_owner_role"],
            review_frequency=item["review_frequency"],
            sort_order=index,
        )
        for slot_index, evidence in enumerate(item["evidence_requirements"], start=1):
            control.slots.append(
                EvidenceSlot(
                    id=uuid.uuid4(),
                    name=evidence["example"],
                    evidence_type=evidence["type"],
                    required=True,
                    freshness_days=FREQ_DAYS.get(item["review_frequency"]),
                    rules=list(item["verification"]["rules"]),
                    required_concepts=list(item["verification"]["required_concepts"]),
                    sort_order=slot_index,
                )
            )
            result.slots_created += 1
        db.add(control)
        links.append(ControlRequirement(control_id=control.id, requirement_id=req.id))
        result.controls_created += 1

    # Link rows have no ORM relationship, so the parents must be inserted first.
    db.flush()
    db.add_all(links)
    db.flush()
    return result
