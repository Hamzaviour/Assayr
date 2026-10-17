"""Personal data breach register with notification deadlines."""

import math
import uuid
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.breaches import notification_overdue, pending_notifications
from assayr.privacy.categories import unknown_categories
from assayr.privacy.models import Breach, ProcessingActivity
from assayr.risk.models import Risk
from assayr.risk.service import next_risk_code

router = APIRouter(prefix="/privacy/breaches", tags=["privacy"])
NOT_FOUND = "Breach not found."
Severity = Literal["low", "medium", "high", "critical"]
Notify = Literal["required", "not_required", "undecided"]
BreachStatus = Literal["open", "contained", "closed"]
SEVERITY_LEVEL = {"low": 2, "medium": 3, "high": 4, "critical": 5}


def _known(value: list[str] | None) -> list[str] | None:
    bad = unknown_categories(value or [])
    if bad:
        raise ValueError(f"Unknown personal-data categories: {', '.join(bad)}.")
    return value


class BreachIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    discovered_at: datetime
    occurred_at: datetime | None = None
    description: str | None = Field(None, max_length=10000)
    data_categories: list[str] = Field(default_factory=list, max_length=20)
    people_affected: int | None = Field(None, ge=0)
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    activity_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    severity: Severity = "medium"
    containment: str | None = Field(None, max_length=10000)
    regulator_notify: Notify = "undecided"
    people_notify: Notify = "undecided"

    _c = field_validator("data_categories")(_known)


class BreachUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    occurred_at: datetime | None = None
    description: str | None = Field(None, max_length=10000)
    data_categories: list[str] | None = Field(None, max_length=20)
    people_affected: int | None = Field(None, ge=0)
    asset_ids: list[uuid.UUID] | None = Field(None, max_length=100)
    activity_ids: list[uuid.UUID] | None = Field(None, max_length=100)
    severity: Severity | None = None
    containment: str | None = Field(None, max_length=10000)
    regulator_notify: Notify | None = None
    regulator_notified_at: datetime | None = None
    people_notify: Notify | None = None
    people_notified_at: datetime | None = None
    lessons: str | None = Field(None, max_length=10000)
    status: BreachStatus | None = None

    _c = field_validator("data_categories")(_known)


class Ref(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class BreachOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    discovered_at: datetime
    occurred_at: datetime | None
    description: str | None
    data_categories: list[str]
    people_affected: int | None
    assets: list[Ref]
    activities: list[Ref]
    severity: str
    severity_level: int
    containment: str | None
    regulator_notify: str
    regulator_notified_at: datetime | None
    people_notify: str
    people_notified_at: datetime | None
    notify_deadline: datetime
    pending_notifications: list[str]
    hours_left: int | None
    notification_overdue: bool
    lessons: str | None
    status: str
    risk: Ref | None


def breach_out(db: Session, b: Breach, now: datetime) -> BreachOut:
    asset_ids = [uuid.UUID(x) for x in b.asset_ids or []]
    activity_ids = [uuid.UUID(x) for x in b.activity_ids or []]
    assets = db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).unique() if asset_ids else []
    activities = (
        db.scalars(select(ProcessingActivity).where(ProcessingActivity.id.in_(activity_ids))).unique()
        if activity_ids
        else []
    )
    pending = pending_notifications(b)
    risk = db.get(Risk, b.risk_id) if b.risk_id else None
    return BreachOut(
        id=b.id,
        code=b.code,
        title=b.title,
        discovered_at=b.discovered_at,
        occurred_at=b.occurred_at,
        description=b.description,
        data_categories=list(b.data_categories or []),
        people_affected=b.people_affected,
        assets=sorted((Ref(id=a.id, code=a.code, name=a.name) for a in assets), key=lambda r: r.code),
        activities=sorted((Ref(id=a.id, code=a.code, name=a.name) for a in activities), key=lambda r: r.code),
        severity=b.severity,
        severity_level=SEVERITY_LEVEL[b.severity],
        containment=b.containment,
        regulator_notify=b.regulator_notify,
        regulator_notified_at=b.regulator_notified_at,
        people_notify=b.people_notify,
        people_notified_at=b.people_notified_at,
        notify_deadline=b.notify_deadline,
        pending_notifications=pending,
        hours_left=math.floor((b.notify_deadline - now).total_seconds() / 3600) if pending else None,
        notification_overdue=notification_overdue(b, now),
        lessons=b.lessons,
        status=b.status,
        risk=Ref(id=risk.id, code=risk.code, name=risk.title) if risk else None,
    )


def _sensitive(user: User, scope_id: uuid.UUID) -> None:
    if not has_perm(user, scope_id, Perm.PRIVACY_SENSITIVE):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the privacy officer or ISMS manager can see breach records."
        )


def _manage(user: User, scope_id: uuid.UUID) -> None:
    _sensitive(user, scope_id)
    if not has_perm(user, scope_id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)


def _ids(db: Session, model, scope_id: uuid.UUID, ids: list[uuid.UUID], what: str) -> list[str]:
    unique = list(dict.fromkeys(ids))
    found = db.scalar(
        select(func.count()).select_from(model).where(model.scope_id == scope_id, model.id.in_(unique))
    )
    if found != len(unique):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Link {what} from this organisation only."
        )
    return [str(x) for x in unique]


def _get(db: Session, user: User, grant: Grant, breach_id: uuid.UUID) -> Breach:
    b = db.get(Breach, breach_id)
    if b is None or not grant.allows(b.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    _sensitive(user, b.scope_id)
    return b


@router.get("", response_model=list[BreachOut])
def list_breaches(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[BreachOut]:
    scope = resolve_scope(db, scope_id, grant)
    _sensitive(user, scope.id)
    now = get_clock(request)()
    rows = db.scalars(select(Breach).where(Breach.scope_id == scope.id).order_by(Breach.seq.desc())).unique()
    return [breach_out(db, b, now) for b in rows]


@router.post("", response_model=BreachOut, status_code=status.HTTP_201_CREATED)
def create_breach(
    body: BreachIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> BreachOut:
    scope = resolve_scope(db, scope_id, grant)
    _manage(user, scope.id)
    seq = (db.scalar(select(func.max(Breach.seq)).where(Breach.scope_id == scope.id)) or 0) + 1
    hours = request.app.state.settings.privacy_breach_hours
    b = Breach(
        scope_id=scope.id,
        code=f"PDB-{seq:03d}",
        seq=seq,
        **body.model_dump(exclude={"asset_ids", "activity_ids"}),
        asset_ids=_ids(db, Asset, scope.id, body.asset_ids, "assets"),
        activity_ids=_ids(db, ProcessingActivity, scope.id, body.activity_ids, "processing activities"),
        notify_deadline=body.discovered_at + timedelta(hours=hours),
    )
    db.add(b)
    db.flush()
    record(db, actor_for(request, user), "privacy.breach", "breach", b.code, diff={"severity": b.severity})
    db.commit()
    db.refresh(b)
    return breach_out(db, b, get_clock(request)())


@router.get("/{breach_id}", response_model=BreachOut)
def get_breach(
    breach_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> BreachOut:
    return breach_out(db, _get(db, user, grant, breach_id), get_clock(request)())


@router.patch("/{breach_id}", response_model=BreachOut)
def update_breach(
    breach_id: uuid.UUID,
    body: BreachUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> BreachOut:
    b = _get(db, user, grant, breach_id)
    _manage(user, b.scope_id)
    fields = body.model_fields_set
    for name in fields:
        value = getattr(body, name)
        if value is None and name in {
            "title",
            "severity",
            "regulator_notify",
            "people_notify",
            "status",
            "data_categories",
        }:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{name.replace('_', ' ').capitalize()} can not be empty.",
            )
        if name == "asset_ids":
            value = _ids(db, Asset, b.scope_id, value or [], "assets")
        if name == "activity_ids":
            value = _ids(db, ProcessingActivity, b.scope_id, value or [], "processing activities")
        setattr(b, name, value)
    record(db, actor_for(request, user), "privacy.breach", "breach", b.code, diff={"updated": sorted(fields)})
    db.commit()
    db.refresh(b)
    return breach_out(db, b, get_clock(request)())


@router.post("/{breach_id}/raise-risk", response_model=BreachOut)
def raise_breach_risk(
    breach_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> BreachOut:
    """Adds the breach to the risk register once; raising it again returns the same risk."""
    b = _get(db, user, grant, breach_id)
    _manage(user, b.scope_id)
    if b.risk_id is None or db.get(Risk, b.risk_id) is None:
        seq, code = next_risk_code(db, b.scope_id)
        risk = Risk(
            scope_id=b.scope_id,
            code=code,
            seq=seq,
            title=f"Breach {b.code}: {b.title}"[:300],
            description=b.description,
            category="Privacy breach",
        )
        db.add(risk)
        db.flush()
        b.risk_id = risk.id
        record(db, actor_for(request, user), "risk.create", "risk", code, diff={"from_breach": b.code})
        db.commit()
        db.refresh(b)
    return breach_out(db, b, get_clock(request)())
