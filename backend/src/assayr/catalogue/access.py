import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from assayr.identity.models import User
from assayr.identity.rbac import Perm, grant_for


@dataclass(frozen=True)
class EditRights:
    all: bool
    own: bool

    @property
    def any(self) -> bool:
        return self.all or self.own


def _pairs(user: User) -> list[tuple[str, uuid.UUID | None]]:
    return [(a.role, a.scope_id) for a in user.role_assignments]


def has_perm(user: User, scope_id: uuid.UUID, perm: Perm) -> bool:
    return grant_for(_pairs(user), perm).allows(scope_id)


def rights_for(
    user: User, scope_id: uuid.UUID, owner_id: uuid.UUID | None, all_perm: Perm, own_perm: Perm
) -> EditRights:
    """`all`: may edit any record of this kind in the scope. `own`: may edit this one because they own it."""
    return EditRights(
        all=has_perm(user, scope_id, all_perm),
        own=owner_id is not None and owner_id == user.id and has_perm(user, scope_id, own_perm),
    )


def edit_rights(user: User, scope_id: uuid.UUID, owner_id: uuid.UUID | None) -> EditRights:
    return rights_for(user, scope_id, owner_id, Perm.CONTROLS_WRITE, Perm.CONTROLS_WRITE_OWN)


def check_active_user(db: Session, user_id: uuid.UUID | None, label: str = "Owner") -> None:
    """Owners and assignees must be people who can still sign in."""
    if user_id is None:
        return
    person = db.get(User, user_id)
    if person is None or not person.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{label} must be an active user.")
