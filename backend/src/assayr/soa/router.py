import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.catalogue.access import has_perm
from assayr.catalogue.models import Control
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.scoring.service import recompute_control
from assayr.soa.schemas import SoaItemsIn, SoaOut
from assayr.soa.service import active_risk_links, soa_view

router = APIRouter(tags=["statement of applicability"])


@router.get("/soa", response_model=SoaOut)
def get_soa(
    request: Request,
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaOut:
    scope = resolve_scope(db, scope_id, grant)
    return soa_view(db, scope.id, request.app.state.settings, get_clock(request)().date())


@router.patch("/soa/items", response_model=SoaOut)
def update_soa_items(
    body: SoaItemsIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.SOA_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> SoaOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.SOA_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    codes = list(dict.fromkeys(body.codes))
    controls = {
        c.code: c
        for c in db.scalars(
            select(Control).where(Control.scope_id == scope.id, Control.code.in_(codes))
        ).unique()
    }
    for code in codes:
        if code not in controls:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Control {code} not found.")
    fields = body.model_fields_set
    if "applicable" in fields and body.applicable is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Applicable can't be empty.")
    if body.applicable is False:
        links = active_risk_links(db, scope.id)
        for code in codes:
            reason = (
                body.exclusion_reason if "exclusion_reason" in fields else controls[code].exclusion_reason
            )
            if not (reason or "").strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, "Give a reason for excluding a control."
                )
            risks = links.get(controls[code].id)
            if risks:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{code} mitigates {', '.join(risks)}. Unlink it from those risks or change their treatment first.",
                )
    settings = request.app.state.settings
    now = get_clock(request)()
    for code in codes:
        control = controls[code]
        diff: dict[str, list] = {}
        if "applicable" in fields and body.applicable != control.applicable:
            diff["applicable"] = [control.applicable, body.applicable]
            control.applicable = body.applicable
        if "sources" in fields:
            new_sources = sorted(set(body.sources or []))
            if new_sources != sorted(control.soa_sources or []):
                diff["sources"] = [sorted(control.soa_sources or []), new_sources]
                control.soa_sources = new_sources
        for name, attr in (("justification", "soa_justification"), ("exclusion_reason", "exclusion_reason")):
            if name in fields:
                value = (getattr(body, name) or "").strip() or None
                if value != getattr(control, attr):
                    diff[name] = [getattr(control, attr), value]
                    setattr(control, attr, value)
        if not diff:
            continue
        record(db, actor_for(request, user), "soa.update", "control", code, diff=diff)
        if "applicable" in diff:
            trigger = (
                "Included in the Statement of Applicability"
                if control.applicable
                else "Excluded in the Statement of Applicability"
            )
            recompute_control(db, control, now, settings, trigger=trigger)
    db.commit()
    return soa_view(db, scope.id, settings, now.date())
