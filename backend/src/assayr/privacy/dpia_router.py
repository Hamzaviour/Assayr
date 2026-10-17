"""DPIA for a processing activity: screening, assessment, privacy risks, review and approval."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, has_perm
from assayr.catalogue.router import FORBIDDEN
from assayr.catalogue.schemas import OwnerOut
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.categories import level_label
from assayr.privacy.dpia import SCREENING, dpia_recommended, score_level
from assayr.privacy.models import Dpia, DpiaRisk, ProcessingActivity
from assayr.risk.models import Risk
from assayr.risk.service import next_risk_code

router = APIRouter(prefix="/privacy/activities/{activity_id}/dpia", tags=["privacy"])
Rating = Field(ge=1, le=5)


def _screening(value: dict[str, bool] | None) -> dict[str, bool] | None:
    unknown = [k for k in (value or {}) if k not in SCREENING]
    if unknown:
        raise ValueError(f"Unknown screening questions: {', '.join(unknown)}.")
    return value


class DpiaIn(BaseModel):
    screening: dict[str, bool] | None = None
    description: str | None = Field(None, max_length=10000)
    necessity: str | None = Field(None, max_length=10000)
    consultation: str | None = Field(None, max_length=10000)
    conclusion: str | None = Field(None, max_length=10000)
    review_due: date | None = None

    _s = field_validator("screening")(_screening)


class RiskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    likelihood: int = Rating
    impact: int = Rating
    measures: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    residual_likelihood: int | None = Field(None, ge=1, le=5)
    residual_impact: int | None = Field(None, ge=1, le=5)


class RiskUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    likelihood: int | None = Field(None, ge=1, le=5)
    impact: int | None = Field(None, ge=1, le=5)
    measures: str | None = Field(None, max_length=5000)
    owner_id: uuid.UUID | None = None
    residual_likelihood: int | None = Field(None, ge=1, le=5)
    residual_impact: int | None = Field(None, ge=1, le=5)


class RegisterRiskOut(BaseModel):
    id: uuid.UUID
    code: str


class RiskOut(BaseModel):
    id: uuid.UUID
    title: str
    likelihood: int
    impact: int
    score: int
    level: int
    level_label: str
    measures: str | None
    owner: OwnerOut | None
    residual_likelihood: int | None
    residual_impact: int | None
    residual_score: int | None
    residual_level_label: str | None
    risk: RegisterRiskOut | None


class DpiaOut(BaseModel):
    id: uuid.UUID
    status: str
    screening: dict[str, bool]
    recommended: bool
    description: str | None
    necessity: str | None
    consultation: str | None
    conclusion: str | None
    approved_by: OwnerOut | None
    approved_at: datetime | None
    review_due: date | None
    risks: list[RiskOut]
    can_edit: bool


def _person(u: User | None) -> OwnerOut | None:
    return OwnerOut(id=u.id, full_name=u.full_name) if u else None


def _risk_out(db: Session, r: DpiaRisk) -> RiskOut:
    score = r.likelihood * r.impact
    residual = (
        r.residual_likelihood * r.residual_impact if r.residual_likelihood and r.residual_impact else None
    )
    register = db.get(Risk, r.risk_id) if r.risk_id else None
    return RiskOut(
        id=r.id,
        title=r.title,
        likelihood=r.likelihood,
        impact=r.impact,
        score=score,
        level=score_level(score),
        level_label=level_label(score_level(score)),
        measures=r.measures,
        owner=_person(r.owner),
        residual_likelihood=r.residual_likelihood,
        residual_impact=r.residual_impact,
        residual_score=residual,
        residual_level_label=level_label(score_level(residual)) if residual else None,
        risk=RegisterRiskOut(id=register.id, code=register.code) if register else None,
    )


def dpia_out(db: Session, d: Dpia, can_edit: bool) -> DpiaOut:
    return DpiaOut(
        id=d.id,
        status=d.status,
        screening=dict(d.screening or {}),
        recommended=dpia_recommended(d.screening or {}),
        description=d.description,
        necessity=d.necessity,
        consultation=d.consultation,
        conclusion=d.conclusion,
        approved_by=_person(d.approved_by),
        approved_at=d.approved_at,
        review_due=d.review_due,
        risks=[_risk_out(db, r) for r in d.risks],
        can_edit=can_edit,
    )


def _activity(db: Session, grant: Grant, activity_id: uuid.UUID) -> ProcessingActivity:
    a = db.get(ProcessingActivity, activity_id)
    if a is None or not grant.allows(a.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processing activity not found.")
    return a


def _dpia(db: Session, a: ProcessingActivity) -> Dpia:
    d = db.scalar(select(Dpia).where(Dpia.activity_id == a.id))
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This activity has no DPIA yet.")
    return d


def _editable(user: User, a: ProcessingActivity, d: Dpia | None = None) -> None:
    if not has_perm(user, a.scope_id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if d is not None and d.status == "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "This DPIA is approved. Reopen it to make changes.")


def _risk(d: Dpia, risk_id: uuid.UUID) -> DpiaRisk:
    r = next((x for x in d.risks if x.id == risk_id), None)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk not found in this DPIA.")
    return r


@router.get("", response_model=DpiaOut)
def get_dpia(
    activity_id: uuid.UUID,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> DpiaOut:
    a = _activity(db, grant, activity_id)
    return dpia_out(db, _dpia(db, a), has_perm(user, a.scope_id, Perm.PRIVACY_MANAGE))


@router.put("", response_model=DpiaOut)
def save_dpia(
    activity_id: uuid.UUID,
    body: DpiaIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> DpiaOut:
    """Creates the DPIA on first save; afterwards updates only the fields sent."""
    a = _activity(db, grant, activity_id)
    d = db.scalar(select(Dpia).where(Dpia.activity_id == a.id))
    _editable(user, a, d)
    if d is None:
        d = Dpia(activity_id=a.id, screening={})
        db.add(d)
    for name in body.model_fields_set:
        setattr(d, name, getattr(body, name) if name != "screening" else dict(body.screening or {}))
    db.flush()
    record(
        db,
        actor_for(request, user),
        "privacy.dpia",
        "processing_activity",
        a.code,
        diff={"saved": sorted(body.model_fields_set)},
    )
    db.commit()
    db.refresh(d)
    return dpia_out(db, d, True)


@router.post("/risks", response_model=RiskOut, status_code=status.HTTP_201_CREATED)
def add_risk(
    activity_id: uuid.UUID,
    body: RiskIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> RiskOut:
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    _editable(user, a, d)
    check_active_user(db, body.owner_id)
    r = DpiaRisk(**body.model_dump())
    d.risks.append(r)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "privacy.dpia_risk",
        "processing_activity",
        a.code,
        diff={"added": r.title},
    )
    db.commit()
    db.refresh(r)
    return _risk_out(db, r)


@router.patch("/risks/{risk_id}", response_model=RiskOut)
def update_risk(
    activity_id: uuid.UUID,
    risk_id: uuid.UUID,
    body: RiskUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> RiskOut:
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    _editable(user, a, d)
    r = _risk(d, risk_id)
    for name in body.model_fields_set:
        value = getattr(body, name)
        if value is None and name in {"title", "likelihood", "impact"}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can not be empty."
            )
        if name == "owner_id":
            check_active_user(db, value)
        setattr(r, name, value)
    record(
        db,
        actor_for(request, user),
        "privacy.dpia_risk",
        "processing_activity",
        a.code,
        diff={"updated": r.title},
    )
    db.commit()
    db.refresh(r)
    return _risk_out(db, r)


@router.delete("/risks/{risk_id}", response_model=DpiaOut)
def delete_risk(
    activity_id: uuid.UUID,
    risk_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> DpiaOut:
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    _editable(user, a, d)
    r = _risk(d, risk_id)
    d.risks.remove(r)
    record(
        db,
        actor_for(request, user),
        "privacy.dpia_risk",
        "processing_activity",
        a.code,
        diff={"removed": r.title},
    )
    db.commit()
    db.refresh(d)
    return dpia_out(db, d, True)


@router.post("/risks/{risk_id}/raise", response_model=RiskOut)
def raise_risk(
    activity_id: uuid.UUID,
    risk_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> RiskOut:
    """Adds the privacy risk to the main risk register once; raising it again returns the same register risk."""
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    if not has_perm(user, a.scope_id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    r = _risk(d, risk_id)
    if r.risk_id is None or db.get(Risk, r.risk_id) is None:
        seq, code = next_risk_code(db, a.scope_id)
        register = Risk(
            scope_id=a.scope_id,
            code=code,
            seq=seq,
            title=f"Privacy: {r.title}"[:300],
            description=f"Raised from the DPIA of {a.code} {a.name}.\nMeasures: {r.measures or 'none recorded'}",
            category="Privacy",
            owner_id=r.owner_id or a.owner_id,
        )
        db.add(register)
        db.flush()
        r.risk_id = register.id
        record(
            db,
            actor_for(request, user),
            "risk.create",
            "risk",
            code,
            diff={"from_dpia": a.code, "title": register.title},
        )
        db.commit()
        db.refresh(r)
    return _risk_out(db, r)


def _transition(
    db: Session, request: Request, user: User, a: ProcessingActivity, d: Dpia, new: str
) -> DpiaOut:
    record(
        db,
        actor_for(request, user),
        f"privacy.dpia_{new}",
        "processing_activity",
        a.code,
        diff={"status": [d.status, new]},
    )
    d.status = new
    db.commit()
    db.refresh(d)
    return dpia_out(db, d, True)


@router.post("/submit", response_model=DpiaOut)
def submit_dpia(
    activity_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> DpiaOut:
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    _editable(user, a, d)
    return _transition(db, request, user, a, d, "in_review")


@router.post("/approve", response_model=DpiaOut)
def approve_dpia(
    activity_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> DpiaOut:
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    _editable(user, a, d)
    if not d.risks and not (d.conclusion or "").strip():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Record at least one privacy risk or a conclusion before approving."
        )
    d.approved_by_id = user.id
    d.approved_at = get_clock(request)()
    return _transition(db, request, user, a, d, "approved")


@router.post("/reopen", response_model=DpiaOut)
def reopen_dpia(
    activity_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> DpiaOut:
    a = _activity(db, grant, activity_id)
    d = _dpia(db, a)
    _editable(user, a)
    d.approved_by_id = None
    d.approved_at = None
    return _transition(db, request, user, a, d, "draft")
