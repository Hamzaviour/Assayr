"""Add and edit SOC 2 control activities."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, _get_control, control_detail, resolve_scope
from assayr.catalogue.schemas import ControlDetailOut
from assayr.catalogue.soc2 import (
    ActivityError,
    create_activity,
    is_activity,
    normalise_activity,
    refresh_criterion,
)
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm

router = APIRouter(tags=["soc2"])


class ActivityIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    test_procedure: str | None = Field(None, max_length=5000)


class ActivityUpdateIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    test_procedure: str | None = Field(None, max_length=5000)


def _can_write(user: User, scope_id: uuid.UUID) -> None:
    if not has_perm(user, scope_id, Perm.CONTROLS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)


@router.post("/soc2/activities", response_model=ControlDetailOut, status_code=status.HTTP_201_CREATED)
def add_activity(
    body: ActivityIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    _can_write(user, scope.id)
    code = normalise_activity(body.code)
    if code is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use a SOC 2 control number like CC6.1.2.")
    if db.scalar(select(Control.id).where(Control.scope_id == scope.id, Control.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{code} already exists.")
    try:
        activity = create_activity(
            db, scope.id, code, body.title.strip(), body.description, body.test_procedure
        )
    except ActivityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    now = get_clock(request)()
    refresh_criterion(db, scope.id, code.rsplit(".", 1)[0], now)
    record(
        db, actor_for(request, user), "soc2.activity_create", "control", code, diff={"title": activity.title}
    )
    db.commit()
    db.refresh(activity)
    return control_detail(db, activity, request.app.state.settings, now)


@router.patch("/soc2/activities/{code}", response_model=ControlDetailOut)
def update_activity(
    code: str,
    body: ActivityUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ControlDetailOut:
    scope = resolve_scope(db, scope_id, grant)
    activity = _get_control(db, scope, code)
    if not is_activity(activity):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOC 2 control activity not found.")
    _can_write(user, scope.id)
    fields = body.model_fields_set
    if "title" in fields and body.title is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The title can not be empty.")
    diff: dict[str, list] = {}
    for name in ("title", "description", "test_procedure"):
        new = getattr(body, name)
        if name in fields and new != getattr(activity, name):
            diff[name] = [getattr(activity, name), new]
            setattr(activity, name, new)
    if diff:
        record(db, actor_for(request, user), "soc2.activity_update", "control", activity.code, diff=diff)
        db.commit()
        db.refresh(activity)
    return control_detail(db, activity, request.app.state.settings, get_clock(request)())
