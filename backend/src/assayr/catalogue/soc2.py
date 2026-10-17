"""SOC 2 control activities: numbered under a criterion (CC6.1.12 under CC6.1); the criterion's status follows them."""

import re
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.catalogue.models import Control, ControlRequirement, EvidenceSlot

_ACTIVITY = re.compile(r"CC(\d{1,2})\.(\d{1,2})\.(\d{1,3})")
# How far along a control is; worst-of roll-up, as NIA uses for its mapped controls.
_RANK = {"not_started": 0, "in_progress": 1, "in_review": 2, "at_risk": 3, "compliant": 4}


def normalise_activity(text: str | None) -> str | None:
    """ " cc 6.1.12 " -> "CC6.1.12"; anything that is not an activity number -> None."""
    compact = "".join(str(text or "").split()).upper()
    match = _ACTIVITY.fullmatch(compact)
    return f"CC{int(match[1])}.{int(match[2])}.{int(match[3])}" if match else None


def criterion_of(code: str) -> str:
    return ".".join(code.split(".")[:2])


def is_activity(control: Control) -> bool:
    return control.framework == "soc2" and control.code.count(".") == 2


def rolled_up(statuses: list[str]) -> str:
    if "non_compliant" in statuses:
        return "non_compliant"
    return min(statuses, key=lambda s: _RANK.get(s, 0))


def activities_of(db: Session, scope_id: uuid.UUID, criterion: str) -> list[Control]:
    return list(
        db.scalars(
            select(Control).where(
                Control.scope_id == scope_id, Control.framework == "soc2", Control.code.like(f"{criterion}.%")
            )
        ).unique()
    )


def criterion_status(db: Session, criterion: Control) -> tuple[str, float | None] | None:
    """The status and score a criterion takes from its applicable activities, or None when it has none."""
    counted = [a for a in activities_of(db, criterion.scope_id, criterion.code) if a.applicable]
    if not counted:
        return None
    scores = [a.score for a in counted if a.score is not None]
    return rolled_up([a.status for a in counted]), (round(sum(scores) / len(scores), 1) if scores else None)


def refresh_criterion(db: Session, scope_id: uuid.UUID, criterion_code: str, now: datetime) -> None:
    from assayr.scoring.models import StatusTransition

    criterion = db.scalar(
        select(Control).where(
            Control.scope_id == scope_id, Control.framework == "soc2", Control.code == criterion_code
        )
    )
    if criterion is None or not criterion.applicable:
        return
    rolled = criterion_status(db, criterion)
    if rolled is None:
        return
    status, score = rolled
    if status != criterion.status:
        db.add(
            StatusTransition(
                control_id=criterion.id,
                from_status=criterion.status,
                to_status=status,
                trigger="SOC 2 control activities changed",
                at=now,
            )
        )
        criterion.status = status
    criterion.score = score
    db.flush()


class ActivityError(ValueError):
    pass


def upsert_activity(
    db: Session, scope_id: uuid.UUID, code: str, description: str, test_procedure: str
) -> tuple[Control, bool]:
    """Creates the activity, or refreshes its text from an imported tracker. Returns (control, created)."""
    title = (description.split(". ")[0] if description else code)[:300] or code
    existing = db.scalar(select(Control).where(Control.scope_id == scope_id, Control.code == code))
    if existing is not None:
        if existing.framework != "soc2":
            raise ActivityError(f"{code} is already used by another control.")
        existing.description = description or existing.description
        existing.test_procedure = test_procedure or existing.test_procedure
        if description:
            existing.title = title
        return existing, False
    return create_activity(db, scope_id, code, title, description or None, test_procedure or None), True


def create_activity(
    db: Session,
    scope_id: uuid.UUID,
    code: str,
    title: str,
    description: str | None,
    test_procedure: str | None,
) -> Control:
    criterion = db.scalar(
        select(Control).where(
            Control.scope_id == scope_id, Control.framework == "soc2", Control.code == criterion_of(code)
        )
    )
    if criterion is None:
        raise ActivityError(f"No SOC 2 criterion {criterion_of(code)} for this activity.")
    number = int(code.rsplit(".", 1)[1])
    activity = Control(
        id=uuid.uuid4(),
        scope_id=scope_id,
        framework="soc2",
        code=code,
        title=title,
        theme=criterion.theme,
        description=description,
        test_procedure=test_procedure,
        review_frequency="Annual",
        sort_order=criterion.sort_order + number,
    )
    activity.slots.append(
        EvidenceSlot(
            id=uuid.uuid4(),
            name="Evidence for the test of this control",
            evidence_type="document",
            required=True,
            freshness_days=365,
            rules=[],
            required_concepts=[],
            sort_order=1,
        )
    )
    db.add(activity)
    db.flush()
    for requirement in criterion.requirements:
        db.add(ControlRequirement(control_id=activity.id, requirement_id=requirement.id))
    db.flush()
    db.refresh(activity)
    return activity
