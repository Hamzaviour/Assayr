"""Data subject requests: logged by staff, tracked against a due date, closed with an outcome."""

import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, has_perm
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.catalogue.schemas import OwnerOut
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.models import ProcessingActivity, SubjectRequest

router = APIRouter(prefix="/privacy/requests", tags=["privacy"])
NOT_FOUND = "Request not found."
RequestType = Literal[
    "access", "correction", "erasure", "objection", "restriction", "withdraw_consent", "other"
]
Channel = Literal["email", "phone", "letter", "in_person", "other"]
Outcome = Literal["fulfilled", "partially", "refused", "withdrawn"]


class Step(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    done: bool = False


class RequestIn(BaseModel):
    type: RequestType
    requester_name: str = Field(min_length=1, max_length=200)
    requester_contact: str | None = Field(None, max_length=300)
    channel: Channel = "email"
    received_on: date
    due_on: date | None = None
    identity_verified: bool = False
    identity_method: str | None = Field(None, max_length=300)
    assignee_id: uuid.UUID | None = None
    activity_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class RequestUpdateIn(BaseModel):
    type: RequestType | None = None
    requester_name: str | None = Field(None, min_length=1, max_length=200)
    requester_contact: str | None = Field(None, max_length=300)
    channel: Channel | None = None
    due_on: date | None = None
    identity_verified: bool | None = None
    identity_method: str | None = Field(None, max_length=300)
    assignee_id: uuid.UUID | None = None
    activity_ids: list[uuid.UUID] | None = Field(None, max_length=50)
    steps: list[Step] | None = Field(None, max_length=50)
    response: str | None = Field(None, max_length=10000)


class CloseIn(BaseModel):
    outcome: Outcome
    refusal_reason: str | None = Field(None, max_length=5000)
    response: str | None = Field(None, max_length=10000)


class ActivityRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class RequestOut(BaseModel):
    id: uuid.UUID
    code: str
    type: str
    requester_name: str
    requester_contact: str | None
    channel: str
    received_on: date
    due_on: date
    days_left: int | None
    overdue: bool
    identity_verified: bool
    identity_method: str | None
    assignee: OwnerOut | None
    activities: list[ActivityRef]
    steps: list[Step]
    response: str | None
    status: str
    outcome: str | None
    refusal_reason: str | None
    closed_on: date | None


def request_out(db: Session, r: SubjectRequest, today: date) -> RequestOut:
    ids = [uuid.UUID(x) for x in r.activity_ids or []]
    activities = (
        db.scalars(select(ProcessingActivity).where(ProcessingActivity.id.in_(ids))).unique() if ids else []
    )
    open_ = r.status != "closed"
    return RequestOut(
        id=r.id,
        code=r.code,
        type=r.type,
        requester_name=r.requester_name,
        requester_contact=r.requester_contact,
        channel=r.channel,
        received_on=r.received_on,
        due_on=r.due_on,
        days_left=(r.due_on - today).days if open_ else None,
        overdue=open_ and r.due_on < today,
        identity_verified=r.identity_verified,
        identity_method=r.identity_method,
        assignee=OwnerOut(id=r.assignee.id, full_name=r.assignee.full_name) if r.assignee else None,
        activities=sorted(
            (ActivityRef(id=a.id, code=a.code, name=a.name) for a in activities), key=lambda a: a.code
        ),
        steps=[Step(**s) for s in r.steps or []],
        response=r.response,
        status=r.status,
        outcome=r.outcome,
        refusal_reason=r.refusal_reason,
        closed_on=r.closed_on,
    )


def _sensitive(user: User, scope_id: uuid.UUID) -> None:
    if not has_perm(user, scope_id, Perm.PRIVACY_SENSITIVE):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the privacy officer or ISMS manager can see data subject requests.",
        )


def _check_activities(db: Session, scope_id: uuid.UUID, ids: list[uuid.UUID]) -> list[str]:
    unique = list(dict.fromkeys(ids))
    found = db.scalar(
        select(func.count())
        .select_from(ProcessingActivity)
        .where(ProcessingActivity.scope_id == scope_id, ProcessingActivity.id.in_(unique))
    )
    if found != len(unique):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Link processing activities from this organisation only."
        )
    return [str(x) for x in unique]


def _get(db: Session, user: User, grant: Grant, request_id: uuid.UUID) -> SubjectRequest:
    r = db.get(SubjectRequest, request_id)
    if r is None or not grant.allows(r.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    _sensitive(user, r.scope_id)
    return r


def _today(request: Request) -> date:
    return get_clock(request)().date()


@router.get("", response_model=list[RequestOut])
def list_requests(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[RequestOut]:
    scope = resolve_scope(db, scope_id, grant)
    _sensitive(user, scope.id)
    rows = db.scalars(
        select(SubjectRequest).where(SubjectRequest.scope_id == scope.id).order_by(SubjectRequest.seq)
    )
    today = _today(request)
    return [request_out(db, r, today) for r in rows.unique()]


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    body: RequestIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> RequestOut:
    scope = resolve_scope(db, scope_id, grant)
    _sensitive(user, scope.id)
    if not has_perm(user, scope.id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.assignee_id, "Assignee")
    activity_ids = _check_activities(db, scope.id, body.activity_ids)
    seq = (
        db.scalar(select(func.max(SubjectRequest.seq)).where(SubjectRequest.scope_id == scope.id)) or 0
    ) + 1
    days = request.app.state.settings.privacy_dsr_days
    r = SubjectRequest(
        scope_id=scope.id,
        code=f"DSR-{seq:03d}",
        seq=seq,
        **body.model_dump(exclude={"activity_ids", "due_on"}),
        due_on=body.due_on or body.received_on + timedelta(days=days),
        activity_ids=activity_ids,
        steps=[],
    )
    db.add(r)
    db.flush()
    record(db, actor_for(request, user), "privacy.request", "subject_request", r.code, diff={"type": r.type})
    db.commit()
    db.refresh(r)
    return request_out(db, r, _today(request))


@router.get("/{request_id}", response_model=RequestOut)
def get_request(
    request_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> RequestOut:
    return request_out(db, _get(db, user, grant, request_id), _today(request))


@router.patch("/{request_id}", response_model=RequestOut)
def update_request(
    request_id: uuid.UUID,
    body: RequestUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> RequestOut:
    r = _get(db, user, grant, request_id)
    if not has_perm(user, r.scope_id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if r.status == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This request is closed.")
    fields = body.model_fields_set
    for name in fields:
        value = getattr(body, name)
        if value is None and name in {
            "type",
            "requester_name",
            "channel",
            "due_on",
            "identity_verified",
            "steps",
            "activity_ids",
        }:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{name.replace('_', ' ').capitalize()} can not be empty.",
            )
        if name == "assignee_id":
            check_active_user(db, value, "Assignee")
        if name == "activity_ids":
            value = _check_activities(db, r.scope_id, value)
        if name == "steps":
            value = [s.model_dump() for s in value]
        setattr(r, name, value)
    if r.status == "open":
        r.status = "in_progress"
    record(
        db,
        actor_for(request, user),
        "privacy.request",
        "subject_request",
        r.code,
        diff={"updated": sorted(fields)},
    )
    db.commit()
    db.refresh(r)
    return request_out(db, r, _today(request))


@router.post("/{request_id}/close", response_model=RequestOut)
def close_request(
    request_id: uuid.UUID,
    body: CloseIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> RequestOut:
    r = _get(db, user, grant, request_id)
    if not has_perm(user, r.scope_id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if body.outcome == "refused" and not (body.refusal_reason or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give the reason the request was refused.")
    r.status, r.outcome, r.refusal_reason = "closed", body.outcome, body.refusal_reason
    if body.response is not None:
        r.response = body.response
    r.closed_on = _today(request)
    record(
        db,
        actor_for(request, user),
        "privacy.request_closed",
        "subject_request",
        r.code,
        diff={"outcome": body.outcome},
    )
    db.commit()
    db.refresh(r)
    return request_out(db, r, _today(request))
