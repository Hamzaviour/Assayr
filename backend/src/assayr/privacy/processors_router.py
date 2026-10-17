"""Processors and vendors that handle personal data, and which processing activities use them."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.categories import level_label, unknown_categories
from assayr.privacy.models import ProcessingActivity, Processor
from assayr.privacy.router import activity_out
from assayr.privacy.schemas import ActivityOut

router = APIRouter(prefix="/privacy", tags=["privacy"])
NOT_FOUND = "Processor not found."
SecurityResult = Literal["satisfactory", "concerns", "unsatisfactory"]


def _known(value: list[str] | None) -> list[str] | None:
    bad = unknown_categories(value or [])
    if bad:
        raise ValueError(f"Unknown personal-data categories: {', '.join(bad)}.")
    return value


class ProcessorIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    service: str | None = Field(None, max_length=300)
    country: str | None = Field(None, max_length=100)
    data_categories: list[str] = Field(default_factory=list, max_length=20)
    dpa_signed: bool = False
    dpa_date: date | None = None
    dpa_document_id: uuid.UUID | None = None
    subprocessors: str | None = Field(None, max_length=5000)
    security_review_on: date | None = None
    security_result: SecurityResult | None = None
    risk_level: int = Field(3, ge=1, le=5)
    status: Literal["active", "ended"] = "active"

    _c = field_validator("data_categories")(_known)


class ProcessorUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    service: str | None = Field(None, max_length=300)
    country: str | None = Field(None, max_length=100)
    data_categories: list[str] | None = Field(None, max_length=20)
    dpa_signed: bool | None = None
    dpa_date: date | None = None
    dpa_document_id: uuid.UUID | None = None
    subprocessors: str | None = Field(None, max_length=5000)
    security_review_on: date | None = None
    security_result: SecurityResult | None = None
    risk_level: int | None = Field(None, ge=1, le=5)
    status: Literal["active", "ended"] | None = None

    _c = field_validator("data_categories")(_known)


class ActivityRefOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class ProcessorOut(BaseModel):
    id: uuid.UUID
    name: str
    service: str | None
    country: str | None
    data_categories: list[str]
    dpa_signed: bool
    dpa_date: date | None
    dpa_document_id: uuid.UUID | None
    subprocessors: str | None
    security_review_on: date | None
    security_result: str | None
    risk_level: int
    risk_level_label: str
    status: str
    activities: list[ActivityRefOut]
    can_edit: bool


class ProcessorLinksIn(BaseModel):
    processor_ids: list[uuid.UUID] = Field(max_length=200)


FIELDS = tuple(ProcessorUpdateIn.model_fields)
REQUIRED = {"name", "data_categories", "dpa_signed", "risk_level", "status"}


def processor_out(p: Processor, can_edit: bool) -> ProcessorOut:
    return ProcessorOut(
        id=p.id,
        name=p.name,
        service=p.service,
        country=p.country,
        data_categories=list(p.data_categories or []),
        dpa_signed=p.dpa_signed,
        dpa_date=p.dpa_date,
        dpa_document_id=p.dpa_document_id,
        subprocessors=p.subprocessors,
        security_review_on=p.security_review_on,
        security_result=p.security_result,
        risk_level=p.risk_level,
        risk_level_label=level_label(p.risk_level),
        status=p.status,
        activities=[ActivityRefOut(id=a.id, code=a.code, name=a.name) for a in p.activities],
        can_edit=can_edit,
    )


def _get(db: Session, grant: Grant, processor_id: uuid.UUID) -> Processor:
    p = db.get(Processor, processor_id)
    if p is None or not grant.allows(p.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return p


def _manage(user: User, scope_id: uuid.UUID) -> None:
    if not has_perm(user, scope_id, Perm.PRIVACY_MANAGE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)


@router.get("/processors", response_model=list[ProcessorOut])
def list_processors(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[ProcessorOut]:
    scope = resolve_scope(db, scope_id, grant)
    can_edit = has_perm(user, scope.id, Perm.PRIVACY_MANAGE)
    rows = db.scalars(
        select(Processor).where(Processor.scope_id == scope.id).order_by(Processor.name)
    ).unique()
    return [processor_out(p, can_edit) for p in rows]


@router.post("/processors", response_model=ProcessorOut, status_code=status.HTTP_201_CREATED)
def create_processor(
    body: ProcessorIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ProcessorOut:
    scope = resolve_scope(db, scope_id, grant)
    _manage(user, scope.id)
    p = Processor(scope_id=scope.id, **body.model_dump())
    db.add(p)
    db.flush()
    record(
        db, actor_for(request, user), "privacy.processor", "processor", str(p.id), diff={"created": p.name}
    )
    db.commit()
    db.refresh(p)
    return processor_out(p, True)


@router.get("/processors/{processor_id}", response_model=ProcessorOut)
def get_processor(
    processor_id: uuid.UUID,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> ProcessorOut:
    p = _get(db, grant, processor_id)
    return processor_out(p, has_perm(user, p.scope_id, Perm.PRIVACY_MANAGE))


@router.patch("/processors/{processor_id}", response_model=ProcessorOut)
def update_processor(
    processor_id: uuid.UUID,
    body: ProcessorUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> ProcessorOut:
    p = _get(db, grant, processor_id)
    _manage(user, p.scope_id)
    diff: dict[str, list] = {}
    for name in FIELDS:
        if name not in body.model_fields_set:
            continue
        value = getattr(body, name)
        if value is None and name in REQUIRED:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{name.replace('_', ' ').capitalize()} can not be empty.",
            )
        if value != getattr(p, name):
            diff[name] = [str(getattr(p, name)), str(value)]
            setattr(p, name, value)
    if diff:
        record(db, actor_for(request, user), "privacy.processor", "processor", str(p.id), diff=diff)
        db.commit()
    db.refresh(p)
    return processor_out(p, True)


@router.put("/activities/{activity_id}/processors", response_model=ActivityOut)
def set_activity_processors(
    activity_id: uuid.UUID,
    body: ProcessorLinksIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> ActivityOut:
    a = db.get(ProcessingActivity, activity_id)
    if a is None or not grant.allows(a.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Processing activity not found.")
    _manage(user, a.scope_id)
    ids = list(dict.fromkeys(body.processor_ids))
    found = list(
        db.scalars(select(Processor).where(Processor.scope_id == a.scope_id, Processor.id.in_(ids))).unique()
    )
    if len(found) != len(ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose processors from this organisation's register."
        )
    before = sorted(x.name for x in a.processors)
    a.processors = found
    record(
        db,
        actor_for(request, user),
        "privacy.processors",
        "processing_activity",
        a.code,
        diff={"processors": [before, sorted(x.name for x in found)]},
    )
    db.commit()
    db.refresh(a)
    return activity_out(a, get_clock(request)().date(), True)
