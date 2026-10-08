"""Load the default risk methodology and the threat, vulnerability and template libraries (only adds what is missing)."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.risk.methodology import DEFAULT_METHODOLOGY, active_methodology
from assayr.risk.models import MethodologyVersion, RiskTemplate, Threat, Vulnerability

LIBRARY_PATH = Path(__file__).resolve().parent / "data" / "library.json"


@dataclass
class LibraryResult:
    threats: int = 0
    vulnerabilities: int = 0
    templates: int = 0


def ensure_methodology(db: Session, now: datetime) -> MethodologyVersion:
    current = active_methodology(db)
    if current is not None:
        return current
    version = MethodologyVersion(
        version_no=1, name=DEFAULT_METHODOLOGY["name"], definition=DEFAULT_METHODOLOGY, effective_from=now
    )
    db.add(version)
    db.flush()
    return version


def ensure_risk_library(db: Session) -> LibraryResult:
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    result = LibraryResult()
    for model, key, counter in (
        (Threat, "threats", "threats"),
        (Vulnerability, "vulnerabilities", "vulnerabilities"),
    ):
        have = set(db.scalars(select(model.code)))
        for item in data[key]:
            if item["code"] not in have:
                db.add(
                    model(
                        code=item["code"],
                        name=item["name"],
                        category=item["category"],
                        description=item.get("description"),
                        is_custom=False,
                    )
                )
                setattr(result, counter, getattr(result, counter) + 1)
    have = set(db.scalars(select(RiskTemplate.code)))
    for item in data["templates"]:
        if item["code"] in have:
            continue
        db.add(
            RiskTemplate(
                code=item["code"],
                title=item["title"],
                scenario=item["scenario"],
                category=item["category"],
                threat_codes=item["threats"],
                vulnerability_codes=item["vulnerabilities"],
                control_codes=item["controls"],
                likelihood=item["likelihood"],
                consequence=item["consequence"],
            )
        )
        result.templates += 1
    db.flush()
    return result
