"""PDPPL obligations with their evidence and status."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from assayr.catalogue.router import resolve_scope
from assayr.db import get_session
from assayr.identity.deps import get_clock, require
from assayr.identity.rbac import Grant, Perm
from assayr.privacy.pdppl import DATA, evaluate

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/pdppl")
def pdppl_obligations(
    request: Request,
    grant: Grant = Depends(require(Perm.ASSETS_READ)),
    db: Session = Depends(get_session),
    scope_id: uuid.UUID | None = None,
) -> dict:
    scope = resolve_scope(db, scope_id, grant)
    rows = evaluate(db, scope.id, get_clock(request)())
    return {
        "name": DATA["name"],
        "title": DATA["title"],
        "notice": DATA["notice"],
        "topics": DATA["topics"],
        "total": len(rows),
        "compliant": sum(1 for r in rows if r["status"] == "compliant"),
        "obligations": rows,
    }
