import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import edit_rights
from assayr.catalogue.models import Control, Framework, Requirement, iso_controls
from assayr.catalogue.schemas import (
    ControlDetailOut,
    ControlPage,
    ControlStatsOut,
    ControlUpdateIn,
    FrameworkOut,
    detail_out,
    summary_out,
)
from assayr.config import Settings
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import Scope, User
from assayr.identity.rbac import Grant, Perm
from assayr.scoring.service import latest_attestation, slot_views

router = APIRouter(tags=["catalogue"])
FORBIDDEN = "You don't have permission to do this."


def resolve_scope(db: Session, scope_id: uuid.UUID | None, grant: Grant) -> Scope:
    if scope_id is None:
        scope = db.scalar(select(Scope).where(Scope.is_default.is_(True)))
        if scope is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No ISMS scope exists yet. Run `assayr seed`.")
    else:
        scope = db.get(Scope, scope_id)
        if scope is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Scope not found.")
    if not grant.allows(scope.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    return scope


def _like(term: str) -> str:
    escaped = term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _get_control(db: Session, scope: Scope, code: str) -> Control:
    control = db.scalar(select(Control).where(Control.scope_id == scope.id, Control.code == code))
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Control not found.")
    return control


def control_detail(db: Session, control: Control, settings: Settings, now: datetime) -> ControlDetailOut:
    attestation = latest_attestation(db, control)
    attested_by = db.get(User, attestation.user_id) if attestation and attestation.user_id else None
    return detail_out(
        control,
        slot_views(db, control, now.date(), settings),
        attestation,
        attested_by.full_name if attested_by else None,
    )


@router.get("/frameworks", response_model=list[FrameworkOut])
def list_frameworks(_grant=Depends(require(Perm.CONTROLS_READ)), db: Session = Depends(get_session)):
    counts = dict(
        db.execute(select(Requirement.framework_id, func.count()).group_by(Requirement.framework_id)).all()
    )
    return [
        FrameworkOut(
            id=f.id, code=f.code, name=f.name, version=f.version, requirement_count=counts.get(f.id, 0)
        )
        for f in db.scalars(select(Framework).order_by(Framework.code))
    ]


@router.get("/controls", response_model=ControlPage)
def list_controls(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    theme: str | None = Query(None, max_length=40),
    status_: str | None = Query(None, alias="status", max_length=30),
    q: str | None = Query(None, max_length=100),
    owner: str | None = Query(None, max_length=40),
    limit: int = Query(50, ge=1, le=200),
    cursor: int | None = Query(None, ge=0),
) -> ControlPage:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Control).where(Control.scope_id == scope.id, iso_controls())
    if theme:
        stmt = stmt.where(Control.theme == theme)
    if status_:
        stmt = stmt.where(Control.status == status_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(
                func.lower(Control.title).like(like, escape="\\"),
                func.lower(Control.code).like(like, escape="\\"),
            )
        )
    if owner == "me":
        stmt = stmt.where(Control.owner_id == user.id)
    elif owner == "none":
        stmt = stmt.where(Control.owner_id.is_(None))
    elif owner:
        try:
            stmt = stmt.where(Control.owner_id == uuid.UUID(owner))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "owner must be 'me', 'none' or a user id."
            ) from exc
    if cursor is not None:
        stmt = stmt.where(Control.sort_order > cursor)
    rows = list(db.scalars(stmt.order_by(Control.sort_order).limit(limit + 1)).unique())
    items = rows[:limit]
    return ControlPage(
        items=[summary_out(c) for c in items], next_cursor=items[-1].sort_order if len(rows) > limit else None
    )


@router.get("/controls/summary", response_model=ControlStatsOut)
def controls_summary(
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlStatsOut:
    scope = resolve_scope(db, scope_id, grant)
    base = select(func.count()).select_from(Control).where(Control.scope_id == scope.id, iso_controls())
    by_status = dict(
        db.execute(
            select(Control.status, func.count())
            .where(Control.scope_id == scope.id, iso_controls())
            .group_by(Control.status)
        ).all()
    )
    by_theme = dict(
        db.execute(
            select(Control.theme, func.count())
            .where(Control.scope_id == scope.id, iso_controls())
            .group_by(Control.theme)
        ).all()
    )
    return ControlStatsOut(
        scope_id=scope.id,
        total=db.scalar(base),
        by_status=by_status,
        by_theme={k or "Other": v for k, v in by_theme.items()},
    )


@router.get("/controls/{code}", response_model=ControlDetailOut)
def get_control(
    code: str,
    request: Request,
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    control = _get_control(db, resolve_scope(db, scope_id, grant), code)
    return control_detail(db, control, request.app.state.settings, get_clock(request)())


@router.patch("/controls/{code}", response_model=ControlDetailOut)
def update_control(
    code: str,
    body: ControlUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    read_grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    scope = resolve_scope(db, scope_id, read_grant)
    control = _get_control(db, scope, code)
    rights = edit_rights(user, scope.id, control.owner_id)
    if not rights.any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    if "owner_id" in fields and not rights.all:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change the owner.")

    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != control.owner_id:
        if body.owner_id is not None:
            new_owner = db.get(User, body.owner_id)
            if new_owner is None or not new_owner.is_active:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Owner must be an active user.")
        diff["owner_id"] = [
            str(control.owner_id) if control.owner_id else None,
            str(body.owner_id) if body.owner_id else None,
        ]
        control.owner_id = body.owner_id
    if body.implementation_status is not None and body.implementation_status != control.implementation_status:
        diff["implementation_status"] = [control.implementation_status, body.implementation_status]
        control.implementation_status = body.implementation_status
    if "implementation_text" in fields and body.implementation_text != control.implementation_text:
        diff["implementation_text"] = [control.implementation_text, body.implementation_text]
        control.implementation_text = body.implementation_text
    if diff:
        record(db, actor_for(request, user), "control.update", "control", control.code, diff=diff)
        db.commit()
        db.refresh(control)
    return control_detail(db, control, request.app.state.settings, get_clock(request)())
