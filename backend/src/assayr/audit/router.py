import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.audit.models import AuditLog
from assayr.audit.service import verify_chain
from assayr.db import get_session
from assayr.identity.deps import require
from assayr.identity.rbac import Perm

router = APIRouter(prefix="/audit-log", tags=["audit"])


class AuditEntryOut(BaseModel):
    seq: int
    at: datetime
    actor_id: uuid.UUID | None
    actor_email: str | None
    ip: str | None
    action: str
    entity_type: str
    entity_id: str | None
    diff: dict[str, Any] | None
    reason: str | None
    request_id: str | None
    hash: str


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    next_before_seq: int | None


class ChainOut(BaseModel):
    ok: bool
    checked: int
    first_bad_seq: int | None


@router.get("", response_model=AuditPage)
def list_entries(
    _grant=Depends(require(Perm.AUDIT_LOG_READ)),
    db: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=500),
    before_seq: int | None = Query(None, ge=1),
    entity_type: str | None = Query(None, max_length=60),
    entity_id: str | None = Query(None, max_length=80),
) -> AuditPage:
    stmt = select(AuditLog).order_by(AuditLog.seq.desc())
    if before_seq is not None:
        stmt = stmt.where(AuditLog.seq < before_seq)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = list(db.scalars(stmt.limit(limit + 1)))
    items = rows[:limit]
    return AuditPage(
        items=[AuditEntryOut.model_validate(r, from_attributes=True) for r in items],
        next_before_seq=items[-1].seq if len(rows) > limit else None,
    )


@router.get("/verify", response_model=ChainOut)
def verify(_grant=Depends(require(Perm.AUDIT_LOG_READ)), db: Session = Depends(get_session)) -> ChainOut:
    result = verify_chain(db)
    return ChainOut(ok=result.ok, checked=result.checked, first_bad_seq=result.first_bad_seq)
