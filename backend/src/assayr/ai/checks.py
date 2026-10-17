"""Automatic ISO/IEC 42001 checks from the AI systems register: shown on controls, never overriding their status."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.ai.models import AiSystem

HIGH_SCORE = 15
FRESH_DAYS = 365


@dataclass(frozen=True)
class CheckResult:
    met: bool
    reason: str


def _names(codes: list[str]) -> str:
    shown = ", ".join(codes[:5])
    return shown + (f" and {len(codes) - 5} more" if len(codes) > 5 else "")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def evaluate(db: Session, scope_id: uuid.UUID, today: date) -> dict[str, CheckResult]:
    systems = list(
        db.scalars(
            select(AiSystem)
            .where(AiSystem.scope_id == scope_id, AiSystem.status == "active")
            .order_by(AiSystem.seq)
        ).unique()
    )
    deployed = [s for s in systems if s.lifecycle == "deployed"]
    approved = [s for s in systems if s.assessment is not None and s.assessment.status == "approved"]
    missing = [s.code for s in deployed if s not in approved]
    stale = [
        s.code
        for s in approved
        if s.assessment.approved_at is None or (today - s.assessment.approved_at.date()).days > FRESH_DAYS
    ]
    no_owner = [s.code for s in systems if s.owner_id is None]
    unraised = [
        s.code
        for s in systems
        if s.assessment is not None
        and any(i.likelihood * i.impact >= HIGH_SCORE and i.risk_id is None for i in s.assessment.impacts)
    ]

    if not systems:
        none = CheckResult(False, "No AI systems recorded yet.")
        return dict.fromkeys(("ai_register", "aiia_all", "aiia_fresh", "ai_owner", "ai_risks"), none)

    results = {
        "ai_register": CheckResult(True, f"{_plural(len(systems), 'AI system')} recorded in the register."),
        "ai_owner": CheckResult(
            not no_owner, f"No owner: {_names(no_owner)}." if no_owner else "Every AI system has an owner."
        ),
        "ai_risks": CheckResult(
            not unraised,
            f"High impacts not yet in the risk register: {_names(unraised)}."
            if unraised
            else "Every high impact is in the risk register.",
        ),
    }
    if not deployed:
        results["aiia_all"] = CheckResult(True, "No deployed AI systems need an impact assessment yet.")
    elif missing:
        results["aiia_all"] = CheckResult(False, f"No approved impact assessment: {_names(missing)}.")
    else:
        results["aiia_all"] = CheckResult(True, "Every deployed AI system has an approved impact assessment.")
    if not approved:
        results["aiia_fresh"] = CheckResult(False, "No approved impact assessments yet.")
    elif stale:
        results["aiia_fresh"] = CheckResult(False, f"Assessments older than 12 months: {_names(stale)}.")
    else:
        results["aiia_fresh"] = CheckResult(True, "Every approved assessment is less than 12 months old.")
    return results
