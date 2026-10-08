import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from assayr.db import get_session
from assayr.identity.deps import require
from assayr.identity.models import User
from assayr.identity.rbac import Perm

router = APIRouter(tags=["people"])


class PersonOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    roles: list[str]


@router.get("/people", response_model=list[PersonOut])
def list_people(
    _grant=Depends(require(Perm.CONTROLS_READ)), db: Session = Depends(get_session)
) -> list[PersonOut]:
    """Active users, for owner and assignee pickers. Anyone who can read controls may see who works on them."""
    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name))
    return [
        PersonOut(
            id=u.id, full_name=u.full_name, email=u.email, roles=sorted({a.role for a in u.role_assignments})
        )
        for u in users
    ]
