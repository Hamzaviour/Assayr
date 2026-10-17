"""AI systems register: list, create, view, edit, retire or delete."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from assayr.ai.models import AiSystem
from assayr.ai.schemas import AiSystemIn, AiSystemOut, AiSystemUpdateIn
from assayr.assets.models import Asset
from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, has_perm
from assayr.catalogue.router import FORBIDDEN, resolve_scope
from assayr.catalogue.schemas import OwnerOut
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.categories import level_label, unknown_categories

router = APIRouter(prefix="/ai/systems", tags=["ai"])
NOT_FOUND = "AI system not found."


def can_manage(user: User, scope_id: uuid.UUID) -> bool:
    return has_perm(user, scope_id, Perm.AI_MANAGE)


def system_out(s: AiSystem, can_edit: bool) -> AiSystemOut:
    return AiSystemOut(
        id=s.id,
        code=s.code,
        name=s.name,
        purpose=s.purpose,
        owner=OwnerOut(id=s.owner.id, full_name=s.owner.full_name) if s.owner else None,
        source=s.source,
        provider=s.provider,
        model_type=s.model_type,
        lifecycle=s.lifecycle,
        risk_level=s.risk_level,
        risk_label=level_label(s.risk_level),
        uses_personal_data=s.uses_personal_data,
        pii_categories=list(s.pii_categories or []),
        asset_ids=list(s.asset_ids or []),
        human_oversight=s.human_oversight,
        status=s.status,
        assessment_status=s.assessment.status if s.assessment else None,
        created_at=s.created_at,
        can_edit=can_edit,
    )


def get_system(db: Session, grant: Grant, system_id: uuid.UUID) -> AiSystem:
    s = db.get(AiSystem, system_id)
    if s is None or not grant.allows(s.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return s


def _check_details(
    db: Session, scope_id: uuid.UUID, categories: list[str], asset_ids: list[uuid.UUID]
) -> None:
    unknown = unknown_categories(categories)
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown personal data categories: {', '.join(unknown)}."
        )
    if asset_ids:
        found = set(db.scalars(select(Asset.id).where(Asset.scope_id == scope_id, Asset.id.in_(asset_ids))))
        if len(found) != len(set(asset_ids)):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "One or more linked assets do not exist."
            )


@router.get("", response_model=list[AiSystemOut])
def list_systems(
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[AiSystemOut]:
    scope = resolve_scope(db, scope_id, grant)
    edit = can_manage(user, scope.id)
    rows = db.scalars(select(AiSystem).where(AiSystem.scope_id == scope.id).order_by(AiSystem.seq)).unique()
    return [system_out(s, edit) for s in rows]


@router.post("", response_model=AiSystemOut, status_code=status.HTTP_201_CREATED)
def create_system(
    body: AiSystemIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> AiSystemOut:
    scope = resolve_scope(db, scope_id, grant)
    if not can_manage(user, scope.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    categories = list(dict.fromkeys(body.pii_categories)) if body.uses_personal_data else []
    _check_details(db, scope.id, categories, body.asset_ids)
    seq = (db.scalar(select(func.max(AiSystem.seq)).where(AiSystem.scope_id == scope.id)) or 0) + 1
    s = AiSystem(
        scope_id=scope.id,
        code=f"AIS-{seq:03d}",
        seq=seq,
        **body.model_dump(exclude={"pii_categories", "asset_ids"}),
        pii_categories=categories,
        asset_ids=[str(a) for a in dict.fromkeys(body.asset_ids)],
        status="active",
    )
    db.add(s)
    db.flush()
    record(db, actor_for(request, user), "ai.system_create", "ai_system", s.code, diff={"name": s.name})
    db.commit()
    db.refresh(s)
    return system_out(s, True)


@router.get("/{system_id}", response_model=AiSystemOut)
def get_one(
    system_id: uuid.UUID,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AiSystemOut:
    s = get_system(db, grant, system_id)
    return system_out(s, can_manage(user, s.scope_id))


@router.patch("/{system_id}", response_model=AiSystemOut)
def update_system(
    system_id: uuid.UUID,
    body: AiSystemUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> AiSystemOut:
    s = get_system(db, grant, system_id)
    if not can_manage(user, s.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    for required in ("name", "source", "lifecycle", "risk_level", "uses_personal_data", "status"):
        if required in fields and getattr(body, required) is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{required.replace('_', ' ')} can not be empty."
            )
    if "owner_id" in fields:
        check_active_user(db, body.owner_id)
    uses = body.uses_personal_data if "uses_personal_data" in fields else s.uses_personal_data
    categories = body.pii_categories if "pii_categories" in fields else s.pii_categories
    categories = list(dict.fromkeys(categories or [])) if uses else []
    assets = body.asset_ids if "asset_ids" in fields else [uuid.UUID(a) for a in s.asset_ids or []]
    _check_details(db, s.scope_id, categories, assets or [])
    updates = {name: getattr(body, name) for name in fields if name not in ("pii_categories", "asset_ids")}
    updates["pii_categories"] = categories
    updates["asset_ids"] = [str(a) for a in dict.fromkeys(assets or [])]
    diff: dict[str, list] = {}
    for name, new in updates.items():
        old = getattr(s, name)
        if new != old:
            diff[name] = [None if old is None else str(old), None if new is None else str(new)]
            setattr(s, name, new)
    if diff:
        record(db, actor_for(request, user), "ai.system_update", "ai_system", s.code, diff=diff)
        db.commit()
        db.refresh(s)
    return system_out(s, True)


@router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(
    system_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.CONTROLS_READ)),
    db: Session = Depends(get_session),
) -> Response:
    s = get_system(db, grant, system_id)
    if not can_manage(user, s.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    if s.assessment is not None and s.assessment.status == "approved":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Retire this AI system instead: it has an approved impact assessment."
        )
    record(db, actor_for(request, user), "ai.system_delete", "ai_system", s.code, diff={"name": s.name})
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
