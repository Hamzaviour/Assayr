import uuid
from dataclasses import dataclass

from assayr.identity.models import User
from assayr.identity.rbac import Perm, grant_for


@dataclass(frozen=True)
class EditRights:
    all: bool
    own: bool

    @property
    def any(self) -> bool:
        return self.all or self.own


def edit_rights(user: User, scope_id: uuid.UUID, owner_id: uuid.UUID | None) -> EditRights:
    """`all`: may edit any control in the scope. `own`: may edit this control because they own it."""
    pairs = [(a.role, a.scope_id) for a in user.role_assignments]
    return EditRights(
        all=grant_for(pairs, Perm.CONTROLS_WRITE).allows(scope_id),
        own=grant_for(pairs, Perm.CONTROLS_WRITE_OWN).allows(scope_id) and owner_id == user.id,
    )
