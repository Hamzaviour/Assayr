"""ISO/IEC 42001 and SOC 2 catalogues: loading and seeding. Safe on every start: adds only what is missing."""

import json
import uuid
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, ControlRequirement, EvidenceSlot, Framework, Requirement
from assayr.identity.models import Scope

DATA = Path(__file__).resolve().parent / "data"
ISO42001_CODE = "ISO42001:2023"
SOC2_CODE = "SOC2:2017"
AI_PREFIX = "AI "


@dataclass
class FrameworkSeed:
    requirements_created: int = 0
    controls_created: int = 0


@cache
def load_iso42001() -> dict:
    return json.loads((DATA / "iso42001_2023.json").read_text(encoding="utf-8"))


@cache
def load_soc2() -> dict:
    return json.loads((DATA / "soc2_tsc_security.json").read_text(encoding="utf-8"))


def control_code(framework: str, ref: str) -> str:
    """ISO 42001 refs collide with ISO 27001 refs, so their controls are coded "AI <ref>" (as NIA uses "NIA ")."""
    return AI_PREFIX + ref if framework == "iso42001" else ref


def display_ref(code: str) -> str:
    return code.removeprefix(AI_PREFIX)


@cache
def iso_map() -> dict[str, list[str]]:
    """Control code of an ISO 42001 or SOC 2 control -> the ISO/IEC 27001 refs it shares evidence with."""
    a, s = load_iso42001(), load_soc2()
    out = {control_code("iso42001", c["ref"]): c["iso27001"] for c in a["controls"]}
    out |= {control_code("iso42001", c["ref"]): c["iso27001"] for c in a["clauses"] if c.get("summary")}
    out |= {c["ref"]: c["iso27001"] for c in s["criteria"]}
    return out


def _framework(db: Session, code: str, name: str, version: str) -> Framework:
    fw = db.scalar(select(Framework).where(Framework.code == code))
    if fw is None:
        fw = Framework(id=uuid.uuid4(), code=code, name=name, version=version)
        db.add(fw)
        db.flush()
    return fw


def _seed(
    db: Session, scope: Scope, framework: str, fw: Framework, groups: list[tuple], leaves: list[dict]
) -> FrameworkSeed:
    """groups: (ref, title, parent_ref, kind); leaves: dicts with ref, title, kind, group, theme, summary..."""
    result = FrameworkSeed()
    reqs = {r.ref: r for r in db.scalars(select(Requirement).where(Requirement.framework_id == fw.id))}
    order = 0

    def ensure(ref, title, kind, parent, guidance=None, attributes=None) -> Requirement:
        nonlocal order
        order += 1
        if ref not in reqs:
            reqs[ref] = Requirement(
                id=uuid.uuid4(),
                framework_id=fw.id,
                ref=ref,
                title=title,
                kind=kind,
                parent_id=reqs[parent].id if parent else None,
                guidance=guidance,
                attributes=attributes or {},
                sort_order=order,
            )
            db.add(reqs[ref])
            result.requirements_created += 1
        return reqs[ref]

    for ref, title, parent, kind in groups:
        ensure(ref, title, kind, parent)
    existing = set(db.scalars(select(Control.code).where(Control.scope_id == scope.id)))
    links: list[ControlRequirement] = []
    for index, leaf in enumerate(leaves, start=1):
        req = ensure(
            leaf["ref"],
            leaf["title"],
            leaf["kind"],
            leaf["group"],
            leaf["summary"],
            {"evidence_hint": leaf["evidence_hint"], "iso27001": leaf["iso27001"], "auto": leaf.get("auto")},
        )
        code = control_code(framework, leaf["ref"])
        if code in existing:
            continue
        control = Control(
            id=uuid.uuid4(),
            scope_id=scope.id,
            framework=framework,
            code=code,
            title=leaf["title"],
            theme=leaf["theme"],
            description=leaf["summary"],
            review_frequency="Annual",
            sort_order=index * 1000,
        )
        control.slots.append(
            EvidenceSlot(
                id=uuid.uuid4(),
                name=leaf["evidence_hint"][:300],
                evidence_type="document",
                required=True,
                freshness_days=365,
                rules=[],
                required_concepts=[],
                sort_order=1,
            )
        )
        db.add(control)
        links.append(ControlRequirement(control_id=control.id, requirement_id=req.id))
        result.controls_created += 1
    # Link rows have no ORM relationship, so the parents must be inserted first.
    db.flush()
    db.add_all(links)
    db.flush()
    return result


def seed_iso42001(db: Session, scope: Scope) -> FrameworkSeed:
    data = load_iso42001()
    fw = _framework(db, ISO42001_CODE, data["name"], data["version"])
    titles = {c["ref"]: c["title"] for c in data["clauses"]}
    groups = [
        (c["ref"], c["title"], c["parent"], "clause_group") for c in data["clauses"] if not c.get("summary")
    ]
    groups += [(o["ref"], o["title"], None, "theme") for o in data["objectives"]]
    objective = {o["ref"]: o["title"] for o in data["objectives"]}
    leaves = [
        {**c, "kind": "clause", "group": c["parent"], "theme": titles[c["ref"].split(".")[0]]}
        for c in data["clauses"]
        if c.get("summary")
    ]
    leaves += [
        {**c, "kind": "annex_control", "group": c["objective"], "theme": objective[c["objective"]]}
        for c in data["controls"]
    ]
    return _seed(db, scope, "iso42001", fw, groups, leaves)


def seed_soc2(db: Session, scope: Scope) -> FrameworkSeed:
    data = load_soc2()
    fw = _framework(db, SOC2_CODE, data["name"], data["version"])
    series = {s["ref"]: s["title"] for s in data["series"]}
    groups = [(ref, title, None, "theme") for ref, title in series.items()]
    leaves = [
        {**c, "kind": "criterion", "group": c["series"], "theme": series[c["series"]]}
        for c in data["criteria"]
    ]
    return _seed(db, scope, "soc2", fw, groups, leaves)
