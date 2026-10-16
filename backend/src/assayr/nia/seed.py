"""Load NIA v2.1 into the catalogue: IDs, domains, our summaries and the mapping to ISO controls.

No NCSA text is loaded here; customers import it from their own copy of the standard (assayr.nia.importer).
"""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, ControlRequirement, EvidenceSlot, Framework, Requirement
from assayr.identity.models import Scope

NIA_CODE = "nia-2.1"
DATA_PATH = Path(__file__).resolve().parents[1] / "catalogue" / "data" / "nia_v2_1.json"
NIA_CONTROLS = len(json.loads(DATA_PATH.read_text(encoding="utf-8"))["controls"])
# The checks a generic NIA evidence document gets (an approved, dated, current document that fits the control).
OWN_SLOT_RULES = ["V-FMT", "V-DATE", "V-APPROVAL", "V-VERSION", "V-OWNER", "V-REVIEW", "V-RELEVANCE"]


@dataclass
class NiaSeedResult:
    domains_created: int = 0
    controls_created: int = 0
    links_created: int = 0
    own_controls_created: int = 0


def own_control_code(ref: str) -> str:
    return f"NIA {ref}"


def seed_nia(db: Session, scope: Scope, path: Path = DATA_PATH) -> NiaSeedResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = NiaSeedResult()

    framework = db.scalar(select(Framework).where(Framework.code == NIA_CODE))
    if framework is None:
        framework = Framework(id=uuid.uuid4(), code=NIA_CODE, name="NIA", version="2.1")
        db.add(framework)
    requirements = {
        r.ref: r for r in db.scalars(select(Requirement).where(Requirement.framework_id == framework.id))
    }

    names = {d["code"]: d["name"] for d in data["domains"]}
    for d in data["domains"]:
        if d["code"] not in requirements:
            req = Requirement(
                id=uuid.uuid4(),
                framework_id=framework.id,
                ref=d["code"],
                title=d["name"],
                kind="domain",
                guidance=d["summary"],
                sort_order=d["order"],
                attributes={},
            )
            db.add(req)
            requirements[d["code"]] = req
            result.domains_created += 1
    for c in data["controls"]:
        if c["ref"] not in requirements:
            req = Requirement(
                id=uuid.uuid4(),
                framework_id=framework.id,
                ref=c["ref"],
                title=f"{c['ref']} · {names[c['domain']]}",
                kind="control",
                parent_id=requirements[c["domain"]].id,
                sort_order=1000 + c["order"],
                attributes={"mandatory": c["mandatory"], "domain": c["domain"]},
            )
            db.add(req)
            requirements[c["ref"]] = req
            result.controls_created += 1
    db.flush()

    controls = {c.code: c for c in db.scalars(select(Control).where(Control.scope_id == scope.id))}
    existing_links = set(
        db.execute(
            select(ControlRequirement.control_id, ControlRequirement.requirement_id)
            .join(Requirement, ControlRequirement.requirement_id == Requirement.id)
            .where(Requirement.framework_id == framework.id)
        ).all()
    )
    links: list[ControlRequirement] = []
    for m in data["mapping"]:
        req = requirements[m["ref"]]
        targets = [(controls[code], m["coverage"]) for code in m["iso"] if code in controls]
        if not m["iso"]:
            code = own_control_code(m["ref"])
            if code not in controls:
                domain = names[m["ref"].split()[0]]
                control = Control(
                    id=uuid.uuid4(),
                    scope_id=scope.id,
                    code=code,
                    title=req.title,
                    theme=domain,
                    description=requirements[m["ref"].split()[0]].guidance,
                    review_frequency="Annual",
                    sort_order=10_000 + len(controls),
                )
                control.slots.append(
                    EvidenceSlot(
                        id=uuid.uuid4(),
                        name="Evidence that this NIA control is implemented",
                        evidence_type="document",
                        required=True,
                        freshness_days=365,
                        rules=list(OWN_SLOT_RULES),
                        required_concepts=[],
                        sort_order=1,
                    )
                )
                db.add(control)
                controls[code] = control
                result.own_controls_created += 1
            targets = [(controls[code], "full")]
        for control, coverage in targets:
            if (control.id, req.id) not in existing_links:
                links.append(
                    ControlRequirement(control_id=control.id, requirement_id=req.id, coverage=coverage)
                )
                existing_links.add((control.id, req.id))
    db.flush()
    db.add_all(links)
    db.flush()
    result.links_created = len(links)
    return result
