"""Data privacy: the record of processing activities and the personal-data (PII) inventory."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from assayr.assets.models import Asset
from assayr.audit.service import record
from assayr.catalogue.access import check_active_user, has_perm
from assayr.catalogue.router import FORBIDDEN, _like, resolve_scope
from assayr.catalogue.schemas import OwnerOut
from assayr.db import get_session
from assayr.exports import add_sheet, xlsx_response
from assayr.identity.deps import actor_for, current_user, get_clock, require
from assayr.identity.models import User
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.categories import PII_CATEGORIES, SENSITIVE, level_label, normalise_pii
from assayr.privacy.models import ProcessingActivity, SubjectRequest
from assayr.privacy.schemas import (
    ActivityIn,
    ActivityOut,
    ActivityRef,
    ActivityUpdateIn,
    AssetLinksIn,
    InventoryRow,
    LinkedAssetOut,
    LinkedProcessorOut,
    PrivacySummary,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])
NOT_FOUND = "Processing activity not found."
FIELDS = (
    "name",
    "purpose",
    "data_subjects",
    "data_categories",
    "lawful_basis",
    "recipients",
    "cross_border",
    "transfer_countries",
    "retention",
    "security_measures",
    "status",
    "review_due",
)
REQUIRED = {"name", "data_subjects", "data_categories", "lawful_basis", "cross_border", "status"}
BASIS_LABEL = {
    "consent": "Consent",
    "contract": "Contract",
    "legal_obligation": "Legal obligation",
    "vital_interest": "Vital interest",
    "public_interest": "Public interest",
    "legitimate_interest": "Legitimate interest",
}


def _criticality(a: Asset) -> int:
    return max(a.confidentiality, a.integrity, a.availability)


def _person(user: User | None) -> OwnerOut | None:
    return OwnerOut(id=user.id, full_name=user.full_name) if user else None


def _overdue(a: ProcessingActivity, today: date) -> bool:
    return a.status == "active" and a.review_due is not None and a.review_due < today


def activity_out(a: ProcessingActivity, today: date, can_edit: bool) -> ActivityOut:
    categories = list(a.data_categories or [])
    return ActivityOut(
        id=a.id,
        code=a.code,
        name=a.name,
        purpose=a.purpose,
        data_subjects=list(a.data_subjects or []),
        data_categories=categories,
        lawful_basis=a.lawful_basis,
        recipients=a.recipients,
        cross_border=a.cross_border,
        transfer_countries=a.transfer_countries,
        retention=a.retention,
        security_measures=a.security_measures,
        owner=_person(a.owner),
        status=a.status,
        review_due=a.review_due,
        sensitive=bool(SENSITIVE & set(categories)),
        review_overdue=_overdue(a, today),
        assets=[
            LinkedAssetOut(id=x.id, code=x.code, name=x.name, criticality_label=level_label(_criticality(x)))
            for x in a.assets
        ],
        processors=[LinkedProcessorOut(id=p.id, name=p.name, dpa_signed=p.dpa_signed) for p in a.processors],
        can_edit=can_edit,
    )


def _today(request: Request) -> date:
    return get_clock(request)().date()


def _get(db: Session, grant: Grant, activity_id: uuid.UUID) -> ProcessingActivity:
    a = db.get(ProcessingActivity, activity_id)
    if a is None or not grant.allows(a.scope_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return a


def _manager(user: User, scope_id: uuid.UUID) -> bool:
    return has_perm(user, scope_id, Perm.PRIVACY_MANAGE)


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
    q: str | None = Query(None, max_length=100),
    status_: str | None = Query(None, alias="status", max_length=20),
) -> list[ActivityOut]:
    scope = resolve_scope(db, scope_id, grant)
    stmt = select(ProcessingActivity).where(ProcessingActivity.scope_id == scope.id)
    if status_:
        stmt = stmt.where(ProcessingActivity.status == status_)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(
            or_(
                func.lower(ProcessingActivity.name).like(like, escape="\\"),
                func.lower(ProcessingActivity.code).like(like, escape="\\"),
            )
        )
    can_edit = _manager(user, scope.id)
    today = _today(request)
    return [
        activity_out(a, today, can_edit) for a in db.scalars(stmt.order_by(ProcessingActivity.seq)).unique()
    ]


@router.post("/activities", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    body: ActivityIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> ActivityOut:
    scope = resolve_scope(db, scope_id, grant)
    if not _manager(user, scope.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    check_active_user(db, body.owner_id)
    seq = (
        db.scalar(select(func.max(ProcessingActivity.seq)).where(ProcessingActivity.scope_id == scope.id))
        or 0
    ) + 1
    a = ProcessingActivity(scope_id=scope.id, code=f"PA-{seq:03d}", seq=seq, **body.model_dump())
    db.add(a)
    db.flush()
    record(
        db, actor_for(request, user), "privacy.create", "processing_activity", a.code, diff={"name": a.name}
    )
    db.commit()
    db.refresh(a)
    return activity_out(a, _today(request), True)


@router.get("/activities/{activity_id}", response_model=ActivityOut)
def get_activity(
    activity_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> ActivityOut:
    a = _get(db, grant, activity_id)
    return activity_out(a, _today(request), _manager(user, a.scope_id))


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: uuid.UUID,
    body: ActivityUpdateIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> ActivityOut:
    a = _get(db, grant, activity_id)
    if not _manager(user, a.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    fields = body.model_fields_set
    diff: dict[str, list] = {}
    if "owner_id" in fields and body.owner_id != a.owner_id:
        check_active_user(db, body.owner_id)
        diff["owner_id"] = [
            str(a.owner_id) if a.owner_id else None,
            str(body.owner_id) if body.owner_id else None,
        ]
        a.owner_id = body.owner_id
    for name in FIELDS:
        if name not in fields:
            continue
        value = getattr(body, name)
        if value is None and name in REQUIRED:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"{name.replace('_', ' ').capitalize()} can not be empty.",
            )
        if value != getattr(a, name):
            old = getattr(a, name)
            diff[name] = [
                old if not isinstance(old, date) else str(old),
                value if not isinstance(value, date) else str(value),
            ]
            setattr(a, name, value)
    if diff:
        record(db, actor_for(request, user), "privacy.update", "processing_activity", a.code, diff=diff)
        db.commit()
    db.refresh(a)
    return activity_out(a, _today(request), True)


@router.put("/activities/{activity_id}/assets", response_model=ActivityOut)
def set_activity_assets(
    activity_id: uuid.UUID,
    body: AssetLinksIn,
    request: Request,
    user: User = Depends(current_user),
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
) -> ActivityOut:
    """Where this activity's data lives. Linked assets are marked as holding its categories of personal data."""
    a = _get(db, grant, activity_id)
    if not _manager(user, a.scope_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN)
    ids = list(dict.fromkeys(body.asset_ids))
    assets = list(db.scalars(select(Asset).where(Asset.scope_id == a.scope_id, Asset.id.in_(ids))).unique())
    if len(assets) != len(ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Link assets from this organisation's register only."
        )
    marked = []
    for asset in assets:
        merged = list(dict.fromkeys([*(asset.pii_categories or []), *(a.data_categories or [])]))
        holds, categories, sensitive, volume = normalise_pii(
            True, merged, asset.pii_sensitive, asset.pii_volume
        )
        if (holds, categories, sensitive) != (
            asset.holds_pii,
            list(asset.pii_categories or []),
            asset.pii_sensitive,
        ):
            marked.append(asset.code)
        asset.holds_pii, asset.pii_categories, asset.pii_sensitive, asset.pii_volume = (
            holds,
            categories,
            sensitive,
            volume,
        )
    before = sorted(x.code for x in a.assets)
    a.assets = sorted(assets, key=lambda x: x.seq)
    record(
        db,
        actor_for(request, user),
        "privacy.assets",
        "processing_activity",
        a.code,
        diff={"assets": [before, sorted(x.code for x in assets)], "marked_pii": marked},
    )
    db.commit()
    db.refresh(a)
    return activity_out(a, _today(request), True)


def _inventory(db: Session, scope_id: uuid.UUID) -> list[InventoryRow]:
    assets = db.scalars(
        select(Asset).where(Asset.scope_id == scope_id, Asset.holds_pii.is_(True)).order_by(Asset.seq)
    ).unique()
    activities = list(
        db.scalars(select(ProcessingActivity).where(ProcessingActivity.scope_id == scope_id)).unique()
    )
    uses: dict[uuid.UUID, list[ActivityRef]] = {}
    for act in sorted(activities, key=lambda x: x.seq):
        for asset in act.assets:
            uses.setdefault(asset.id, []).append(ActivityRef(code=act.code, name=act.name))
    return [
        InventoryRow(
            id=x.id,
            code=x.code,
            name=x.name,
            type=x.type,
            owner=_person(x.owner),
            pii_categories=list(x.pii_categories or []),
            pii_sensitive=x.pii_sensitive,
            pii_volume=x.pii_volume,
            criticality=_criticality(x),
            criticality_label=level_label(_criticality(x)),
            activities=uses.get(x.id, []),
        )
        for x in assets
    ]


@router.get("/inventory", response_model=list[InventoryRow])
def pii_inventory(
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> list[InventoryRow]:
    return _inventory(db, resolve_scope(db, scope_id, grant).id)


@router.get("/summary", response_model=PrivacySummary)
def privacy_summary(
    request: Request,
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> PrivacySummary:
    scope = resolve_scope(db, scope_id, grant)
    inventory = _inventory(db, scope.id)
    activities = list(
        db.scalars(select(ProcessingActivity).where(ProcessingActivity.scope_id == scope.id)).unique()
    )
    today = _today(request)
    requests = list(db.scalars(select(SubjectRequest).where(SubjectRequest.scope_id == scope.id)))
    return PrivacySummary(
        pii_assets=len(inventory),
        sensitive_assets=sum(1 for r in inventory if r.pii_sensitive),
        activities=len(activities),
        active_activities=sum(1 for a in activities if a.status == "active"),
        cross_border=sum(1 for a in activities if a.cross_border and a.status != "retired"),
        reviews_due=sum(1 for a in activities if _overdue(a, today)),
        requests_open=sum(1 for r in requests if r.status != "closed"),
        requests_overdue=sum(1 for r in requests if r.status != "closed" and r.due_on < today),
    )


@router.get("/export.xlsx")
def privacy_export(
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> Response:
    scope = resolve_scope(db, scope_id, grant)
    label = PII_CATEGORIES.get
    activities = db.scalars(
        select(ProcessingActivity)
        .where(ProcessingActivity.scope_id == scope.id)
        .order_by(ProcessingActivity.seq)
    ).unique()
    workbook = Workbook()
    add_sheet(
        workbook,
        "Processing activities",
        [
            "Code",
            "Name",
            "Purpose",
            "Data subjects",
            "Personal data",
            "Sensitive",
            "Lawful basis",
            "Recipients",
            "Cross-border",
            "Countries",
            "Retention",
            "Security measures",
            "Stored on",
            "Owner",
            "Status",
            "Next review",
        ],
        [
            [
                a.code,
                a.name,
                a.purpose,
                ", ".join(a.data_subjects or []),
                ", ".join(label(c, c) for c in a.data_categories or []),
                "Yes" if SENSITIVE & set(a.data_categories or []) else "No",
                BASIS_LABEL.get(a.lawful_basis, a.lawful_basis),
                a.recipients,
                "Yes" if a.cross_border else "No",
                a.transfer_countries,
                a.retention,
                a.security_measures,
                ", ".join(f"{x.code} {x.name}" for x in a.assets),
                a.owner.full_name if a.owner else None,
                a.status.capitalize(),
                a.review_due,
            ]
            for a in activities
        ],
    )
    add_sheet(
        workbook,
        "PII inventory",
        [
            "Asset",
            "Name",
            "Type",
            "Personal data",
            "Sensitive",
            "Volume",
            "Criticality",
            "Owner",
            "Activities",
        ],
        [
            [
                r.code,
                r.name,
                r.type,
                ", ".join(label(c, c) for c in r.pii_categories),
                "Yes" if r.pii_sensitive else "No",
                r.pii_volume,
                r.criticality_label,
                r.owner.full_name if r.owner else None,
                ", ".join(x.code for x in r.activities),
            ]
            for r in _inventory(db, scope.id)
        ],
    )
    return xlsx_response(workbook, "data-privacy.xlsx")
