"""NIA controls: list, detail, mapping to ISO controls, applicability."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control, ControlRequirement
from assayr.catalogue.router import resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.nia.service import NiaControlView, nia_views, set_applicability

router = APIRouter(prefix="/nia", tags=["nia"])


class MappedOut(BaseModel):
    code: str
    title: str
    status: str


class NiaRowOut(BaseModel):
    ref: str
    domain: str
    domain_name: str
    title: str
    status: str
    score: float | None
    applicable: bool
    mandatory: bool
    mapped: list[MappedOut]


class NiaDetailOut(NiaRowOut):
    summary: str | None
    text: str | None
    exclusion_reason: str | None
    can_edit: bool


class LinkIn(BaseModel):
    code: str = Field(max_length=20)
    coverage: Literal["full", "partial"] = "full"


class MappingIn(BaseModel):
    links: list[LinkIn] = Field(max_length=40)


class ApplicabilityIn(BaseModel):
    applicable: bool
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _reason_when_excluded(self):
        if not self.applicable and not (self.reason or "").strip():
            raise ValueError("Give a reason why this NIA control does not apply.")
        return self


def _row(v: NiaControlView) -> dict:
    return {
        "ref": v.ref,
        "domain": v.domain,
        "domain_name": v.domain_name,
        "title": v.title,
        "status": v.status,
        "score": v.score,
        "applicable": v.applicable,
        "mandatory": v.mandatory,
        "mapped": [{"code": c.code, "title": c.title, "status": c.status} for c in v.mapped],
    }


def _view(db: Session, scope_id: uuid.UUID, ref: str) -> NiaControlView:
    view = next((v for v in nia_views(db, scope_id) if v.ref == ref), None)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No NIA control {ref}.")
    return view


def _detail(db: Session, user: User, scope_id: uuid.UUID, ref: str) -> NiaDetailOut:
    v = _view(db, scope_id, ref)
    req = v.requirement
    attributes = req.attributes or {}
    imported = attributes.get("text_source") == "imported"
    exclusion = attributes.get("exclusions", {}).get(str(scope_id))
    parent_summary = _domain_summary(db, req.parent_id)
    return NiaDetailOut(
        **_row(v),
        summary=parent_summary,
        text=req.guidance if imported else None,
        exclusion_reason=exclusion["reason"] if exclusion else None,
        can_edit=has_perm(user, scope_id, Perm.CONTROLS_WRITE),
    )


def _domain_summary(db: Session, parent_id: uuid.UUID | None) -> str | None:
    from assayr.catalogue.models import Requirement

    parent = db.get(Requirement, parent_id) if parent_id else None
    return parent.guidance if parent else None


def _require_manager(user: User, scope_id: uuid.UUID) -> None:
    if not has_perm(user, scope_id, Perm.CONTROLS_WRITE):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change NIA mappings and applicability."
        )


@router.get("/controls", response_model=list[NiaRowOut])
def list_nia_controls(
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    domain: str | None = Query(None, max_length=2),
) -> list[dict]:
    scope = resolve_scope(db, scope_id, grant)
    return [_row(v) for v in nia_views(db, scope.id) if domain is None or v.domain == domain]


@router.get("/controls/{ref}", response_model=NiaDetailOut)
def get_nia_control(
    ref: str,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> NiaDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    return _detail(db, user, scope.id, ref)


@router.put("/controls/{ref}/mapping", response_model=NiaDetailOut)
def set_nia_mapping(
    ref: str,
    body: MappingIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> NiaDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    _require_manager(user, scope.id)
    v = _view(db, scope.id, ref)
    codes = [link.code for link in body.links]
    controls = {
        c.code: c
        for c in db.scalars(select(Control).where(Control.scope_id == scope.id, Control.code.in_(codes)))
    }
    unknown = [code for code in codes if code not in controls]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown control(s): {', '.join(unknown)}."
        )
    before = sorted(c.code for c in v.mapped)
    scope_control_ids = select(Control.id).where(Control.scope_id == scope.id)
    db.execute(
        delete(ControlRequirement).where(
            ControlRequirement.requirement_id == v.requirement.id,
            ControlRequirement.control_id.in_(scope_control_ids),
        )
    )
    db.add_all(
        ControlRequirement(
            control_id=controls[link.code].id, requirement_id=v.requirement.id, coverage=link.coverage
        )
        for link in body.links
    )
    db.flush()
    record(
        db,
        actor_for(request, user),
        "nia.mapping",
        "nia_control",
        ref,
        diff={"mapped": [before, sorted(codes)]},
    )
    db.commit()
    return _detail(db, user, scope.id, ref)


@router.post("/controls/{ref}/applicability", response_model=NiaDetailOut)
def set_nia_applicability(
    ref: str,
    body: ApplicabilityIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> NiaDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    _require_manager(user, scope.id)
    v = _view(db, scope.id, ref)
    set_applicability(db, scope.id, ref, applicable=body.applicable, reason=body.reason, by=user.email)
    record(
        db,
        actor_for(request, user),
        "nia.applicability",
        "nia_control",
        ref,
        diff={"applicable": [v.applicable, body.applicable], "reason": [None, body.reason]},
    )
    db.commit()
    return _detail(db, user, scope.id, ref)
