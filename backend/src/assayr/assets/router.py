import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.assets.schemas import AssetIn, AssetOut, AssetUpdateIn, asset_out
from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, has_perm, rights_for
from assayr.catalogue.router import FORBIDDEN, _like, resolve_scope
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm

router = APIRouter(tags=["assets"])
EDITABLE = (
    "name",
    "type",
    "classification",
    "confidentiality",
    "integrity",
    "availability",
    "location",
    "description",
    "lifecycle",
)
REQUIRED = {"name", "type", "classification", "confidentiality", "integrity", "availability", "lifecycle"}


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    q: str | None = Query(None, max_length=100),
    type_: str | None = Query(None, alias="type", max_length=30),
    include_retired: bool = False,
) -> list[AssetOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(Asset).where(Asset.scope_id == scope.id)
    if not include_retired:
        stmt = stmt.where(Asset.lifecycle != "retired")
    if type_:
        stmt = stmt.where(Asset.type == type_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(
                func.lower(Asset.name).like(like, escape="\\"), func.lower(Asset.code).like(like, escape="\\")
            )
        )
    return [asset_out(a) for a in db.scalars(stmt.order_by(Asset.seq)).unique()]


@router.post("/assets", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    body: AssetIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> AssetOut:
    scope = resolve_scope(db, scope_id, grant)
    if not has_perm(user, scope.id, Perm.ASSETS_WRITE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    seq = (db.scalar(select(func.max(Asset.seq)).where(Asset.scope_id == scope.id)) or 0) + 1
    asset = Asset(scope_id=scope.id, code=f"AST-{seq:03d}", seq=seq, **body.model_dump())
    db.add(asset)
    db.flush()
    record(
        db,
        actor_for(request, user),
        "asset.create",
        "asset",
        asset.code,
        diff={"name": asset.name, "type": asset.type},
    )
    db.commit()
    db.refresh(asset)
    return asset_out(asset)


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if asset is None or not grant.allows(asset.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found.")
    rights = rights_for(user, asset.scope_id, asset.owner_id, Perm.ASSETS_WRITE, Perm.ASSETS_WRITE_OWN)
    if not rights.any:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    if "owner_id" in fields and not rights.all:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an ISMS manager can change the owner.")
    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != asset.owner_id:
        check_active_user(db, body.owner_id)
        diff["owner_id"] = [
            str(asset.owner_id) if asset.owner_id else None,
            str(body.owner_id) if body.owner_id else None,
        ]
        asset.owner_id = body.owner_id
    for name in EDITABLE:
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in REQUIRED:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name.capitalize()} can't be empty.")
        if value != getattr(asset, name):
            diff[name] = [getattr(asset, name), value]
            setattr(asset, name, value)
    if diff:
        record(db, actor_for(request, user), "asset.update", "asset", asset.code, diff=diff)
        db.commit()
    db.refresh(asset)
    return asset_out(asset)
