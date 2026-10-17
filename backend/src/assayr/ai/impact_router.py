"""AI system impact assessments: sections, impacts, submit/approve/reopen and raising impacts as risks."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from assayr.ai.models import SECTION_LABELS, SECTIONS, AiImpact, AiImpactAssessment, AiSystem
from assayr.ai.router import can_manage, get_system
from assayr.ai.schemas import AssessmentIn, AssessmentOut, ImpactIn, ImpactOut, ImpactUpdateIn
from assayr.audit.service import record
from assayr.catalogue.access import check_active_user
from assayr.catalogue.router import FORBIDDEN
from assayr.catalogue.schemas import OwnerOut
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.dpia import score_level
from assayr.risk.models import Risk
from assayr.risk.service import next_risk_code

router = APIRouter(prefix="/ai/systems/{system_id}/assessment", tags=["ai"])
HIGH_SCORE = 15


def _person(u: User | None) -> OwnerOut | None:
    return OwnerOut(id=u.id, full_name=u.full_name) if u else None


def missing_sections(a: AiImpactAssessment) -> list[str]:
    return [SECTION_LABELS[name] for name in SECTIONS if not (getattr(a, name) or "").strip()]


def _impact_out(db: Session, i: AiImpact) -> ImpactOut:
    score = i.likelihood * i.impact
    register = db.get(Risk, i.risk_id) if i.risk_id else None
    return ImpactOut(
        id=i.id,
        area=i.area,
        description=i.description,
        likelihood=i.likelihood,
        impact=i.impact,
        score=score,
        level=score_level(score),
        mitigation=i.mitigation,
        owner=_person(i.owner),
        risk_id=register.id if register else None,
        risk_code=register.code if register else None,
    )


def assessment_out(db: Session, a: AiImpactAssessment, can_edit: bool) -> AssessmentOut:
    return AssessmentOut(
        id=a.id,
        status=a.status,
        **{name: getattr(a, name) for name in SECTIONS},
        approved_by=_person(a.approved_by),
        approved_at=a.approved_at,
        review_due=a.review_due,
        impacts=[_impact_out(db, i) for i in a.impacts],
        missing=missing_sections(a),
        can_edit=can_edit,
    )


def _assessment(s: AiSystem) -> AiImpactAssessment:
    if s.assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This AI system has no impact assessment yet.")
    return s.assessment


def _manager(user: User, s: AiSystem) -> None:
    if not can_manage(user, s.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)


def _editable(user: User, s: AiSystem, a: AiImpactAssessment | None = None) -> None:
    _manager(user, s)
    if a is not None and a.status == "approved":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This assessment is approved. Reopen it to make changes."
        )


def _impact(a: AiImpactAssessment, impact_id: uuid.UUID) -> AiImpact:
    found = next((i for i in a.impacts if i.id == impact_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Impact not found in this assessment.")
    return found


@router.get("", response_model=AssessmentOut)
def get_assessment(
    system_id: uuid.UUID,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AssessmentOut:
    s = get_system(db, grant, system_id)
    return assessment_out(db, _assessment(s), can_manage(user, s.scope_id))


@router.put("", response_model=AssessmentOut)
def save_assessment(
    system_id: uuid.UUID,
    body: AssessmentIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AssessmentOut:
    """Creates the assessment on first save; later saves update only the sections sent."""
    s = get_system(db, grant, system_id)
    _editable(user, s, s.assessment)
    a = s.assessment
    created = a is None
    if a is None:
        a = AiImpactAssessment(ai_system_id=s.id, status="draft")
        s.assessment = a
    changed = []
    for name in body.model_fields_set:
        if getattr(body, name) != getattr(a, name):
            setattr(a, name, getattr(body, name))
            changed.append(name)
    if created or changed:
        record(
            db,
            actor_for(request, user),
            "ai.aiia_create" if created else "ai.aiia_update",
            "ai_system",
            s.code,
            diff={"sections": changed},
        )
        db.commit()
        db.refresh(a)
    return assessment_out(db, a, True)


@router.post("/impacts", response_model=ImpactOut, status_code=status.HTTP_201_CREATED)
def add_impact(
    system_id: uuid.UUID,
    body: ImpactIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ImpactOut:
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _editable(user, s, a)
    check_active_user(db, body.owner_id)
    i = AiImpact(**body.model_dump())
    a.impacts.append(i)
    db.flush()
    record(db, actor_for(request, user), "ai.aiia_impact", "ai_system", s.code, diff={"added": i.description})
    db.commit()
    db.refresh(i)
    return _impact_out(db, i)


@router.patch("/impacts/{impact_id}", response_model=ImpactOut)
def update_impact(
    system_id: uuid.UUID,
    impact_id: uuid.UUID,
    body: ImpactUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ImpactOut:
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _editable(user, s, a)
    i = _impact(a, impact_id)
    fields = body.model_fields_set
    for name in ("area", "description", "likelihood", "impact"):
        if name in fields and getattr(body, name) is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can not be empty."
            )
    if "owner_id" in fields:
        check_active_user(db, body.owner_id)
    diff = {}
    for name in fields:
        if getattr(body, name) != getattr(i, name):
            diff[name] = [str(getattr(i, name)), str(getattr(body, name))]
            setattr(i, name, getattr(body, name))
    if diff:
        record(db, actor_for(request, user), "ai.aiia_impact", "ai_system", s.code, diff=diff)
        db.commit()
        db.refresh(i)
    return _impact_out(db, i)


@router.delete("/impacts/{impact_id}", response_model=AssessmentOut)
def delete_impact(
    system_id: uuid.UUID,
    impact_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AssessmentOut:
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _editable(user, s, a)
    i = _impact(a, impact_id)
    a.impacts.remove(i)
    record(
        db, actor_for(request, user), "ai.aiia_impact", "ai_system", s.code, diff={"removed": i.description}
    )
    db.commit()
    db.refresh(a)
    return assessment_out(db, a, True)


@router.post("/impacts/{impact_id}/raise", response_model=ImpactOut)
def raise_impact(
    system_id: uuid.UUID,
    impact_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> ImpactOut:
    """Adds the impact to the main risk register once; raising it again returns the same register risk."""
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _manager(user, s)
    i = _impact(a, impact_id)
    if i.risk_id is None or db.get(Risk, i.risk_id) is None:
        seq, code = next_risk_code(db, s.scope_id)
        register = Risk(
            scope_id=s.scope_id,
            code=code,
            seq=seq,
            title=f"AI: {i.description}"[:300],
            description=f"Raised from the AI impact assessment of {s.code} {s.name}.\n"
            f"Mitigation: {i.mitigation or 'none recorded'}",
            category="AI",
            owner_id=i.owner_id or s.owner_id,
        )
        db.add(register)
        db.flush()
        i.risk_id = register.id
        record(
            db,
            actor_for(request, user),
            "risk.create",
            "risk",
            code,
            diff={"from_aiia": s.code, "title": register.title},
        )
        db.commit()
        db.refresh(i)
    return _impact_out(db, i)


def _transition(
    db: Session, request: Request, user: User, s: AiSystem, a: AiImpactAssessment, new: str
) -> AssessmentOut:
    record(
        db, actor_for(request, user), f"ai.aiia_{new}", "ai_system", s.code, diff={"status": [a.status, new]}
    )
    a.status = new
    db.commit()
    db.refresh(a)
    return assessment_out(db, a, True)


@router.post("/submit", response_model=AssessmentOut)
def submit_assessment(
    system_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AssessmentOut:
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _editable(user, s, a)
    if a.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "This assessment is already in review.")
    missing = missing_sections(a)
    if missing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Fill in: {', '.join(missing)}.")
    if not a.impacts:
        raise HTTPException(status.HTTP_409_CONFLICT, "Record at least one impact before submitting.")
    return _transition(db, request, user, s, a, "in_review")


@router.post("/approve", response_model=AssessmentOut)
def approve_assessment(
    system_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AssessmentOut:
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _editable(user, s, a)
    if a.status != "in_review":
        raise HTTPException(status.HTTP_409_CONFLICT, "Submit the assessment for review before approving it.")
    now = get_clock(request)()
    a.approved_by_id = user.id
    a.approved_at = now
    a.review_due = now.date() + timedelta(days=365)
    return _transition(db, request, user, s, a, "approved")


@router.post("/reopen", response_model=AssessmentOut)
def reopen_assessment(
    system_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AssessmentOut:
    s = get_system(db, grant, system_id)
    a = _assessment(s)
    _manager(user, s)
    if a.status == "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "This assessment is already a draft.")
    a.approved_by_id = None
    a.approved_at = None
    a.review_due = None
    return _transition(db, request, user, s, a, "draft")
