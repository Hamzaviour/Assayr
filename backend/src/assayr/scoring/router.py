import uuid
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import edit_rights
from assayr.catalogue.models import Control, iso_controls
from assayr.catalogue.router import _get_control, control_detail, resolve_scope
from assayr.catalogue.schemas import ControlDetailOut
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.scoring.models import Attestation, ScoreSnapshot
from assayr.scoring.service import attestation_days, recompute_control, scope_has_evidence, weighted_readiness

router = APIRouter(tags=["scoring"])
TREND_DAYS = 90


class AttestIn(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)


class TrendPoint(BaseModel):
    date: date
    readiness: float


class ReadinessOut(BaseModel):
    scope_id: uuid.UUID
    readiness: float | None
    status_counts: dict[str, int]
    by_theme: dict[str, float | None]
    trend: list[TrendPoint]


@router.get("/readiness", response_model=ReadinessOut)
def readiness(
    request: Request,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ReadinessOut:
    scope = resolve_scope(db, scope_id, grant)
    controls = list(db.scalars(select(Control).where(Control.scope_id == scope.id, iso_controls())))
    has_evidence = scope_has_evidence(db, scope.id)
    themes: dict[str, list[Control]] = {}
    for control in controls:
        themes.setdefault(control.theme or "Other", []).append(control)
    since = get_clock(request)() - timedelta(days=TREND_DAYS)
    snapshots = db.scalars(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.scope_id == scope.id, ScoreSnapshot.taken_at >= since)
        .order_by(ScoreSnapshot.taken_at)
    )
    return ReadinessOut(
        scope_id=scope.id,
        readiness=weighted_readiness(controls) if has_evidence else None,
        status_counts=dict(Counter(c.status for c in controls)),
        by_theme={
            theme: weighted_readiness(group) if has_evidence else None for theme, group in themes.items()
        },
        trend=[TrendPoint(date=s.taken_at.date(), readiness=s.readiness) for s in snapshots],
    )


@router.post("/controls/{code}/attest", response_model=ControlDetailOut)
def attest(
    code: str,
    body: AttestIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    control = _get_control(db, scope, code)
    if not (edit_rights(user, scope.id, control.owner_id).all or control.owner_id == user.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the control owner or an ISMS manager can attest."
        )
    settings = request.app.state.settings
    now = get_clock(request)()
    valid_until = now + timedelta(days=attestation_days(control))
    db.add(
        Attestation(
            control_id=control.id,
            user_id=user.id,
            statement=body.statement.strip(),
            attested_at=now,
            valid_until=valid_until,
        )
    )
    db.flush()
    record(
        db,
        actor_for(request, user),
        "control.attest",
        "control",
        control.code,
        diff={"valid_until": [None, valid_until.isoformat()]},
    )
    recompute_control(db, control, now, settings, trigger="Owner attested")
    db.commit()
    return control_detail(db, control, settings, now)
