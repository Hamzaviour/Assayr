import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from assayr.audit.service import record
from assayr.db import get_session
from assayr.identity.deps import actor_for, current_user, require
from assayr.identity.models import RoleAssignment, Scope, User, UserSession
from assayr.identity.rbac import Perm, Role
from assayr.identity.schemas import RoleGrantIn, UserCreateIn, UserOut, UserUpdateIn
from assayr.identity.security import WeakPasswordError, hash_password, normalize_email

router = APIRouter(prefix="/users", tags=["users"])


def _desired_roles(db: Session, grants: list[RoleGrantIn]) -> set[tuple[str, uuid.UUID | None]]:
    desired = {(g.role.value, g.scope_id) for g in grants}
    for _role, scope_id in desired:
        if scope_id is not None and db.get(Scope, scope_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown scope.")
    return desired


@router.get("", response_model=list[UserOut])
def list_users(
    _grant=Depends(require(Perm.USERS_MANAGE)), db: Session = Depends(get_session)
) -> list[UserOut]:
    return [UserOut.from_user(u) for u in db.scalars(select(User).order_by(User.email))]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateIn,
    request: Request,
    actor: User = Depends(current_user),
    _grant=Depends(require(Perm.USERS_MANAGE)),
    db: Session = Depends(get_session),
) -> UserOut:
    email = normalize_email(body.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    try:
        password_hash = hash_password(body.password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    roles = _desired_roles(db, body.roles)
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        password_hash=password_hash,
        role_assignments=[RoleAssignment(role=r, scope_id=s) for r, s in sorted(roles, key=str)],
    )
    db.add(user)
    db.flush()
    record(
        db,
        actor_for(request, actor),
        "user.create",
        "user",
        str(user.id),
        diff={"email": [None, email], "roles": [None, sorted(r for r, _ in roles)]},
    )
    db.commit()
    return UserOut.from_user(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdateIn,
    request: Request,
    actor: User = Depends(current_user),
    _grant=Depends(require(Perm.USERS_MANAGE)),
    db: Session = Depends(get_session),
) -> UserOut:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    diff: dict[str, list] = {}
    if body.full_name is not None and body.full_name.strip() != target.full_name:
        diff["full_name"] = [target.full_name, body.full_name.strip()]
        target.full_name = body.full_name.strip()
    if body.is_active is not None and body.is_active != target.is_active:
        if target.id == actor.id and body.is_active is False:
            raise HTTPException(status.HTTP_409_CONFLICT, "You can't deactivate your own account.")
        diff["is_active"] = [target.is_active, body.is_active]
        target.is_active = body.is_active
        if not body.is_active:
            db.execute(delete(UserSession).where(UserSession.user_id == target.id))
    if body.roles is not None:
        desired = _desired_roles(db, body.roles)
        current = {(a.role, a.scope_id) for a in target.role_assignments}
        if target.id == actor.id and (Role.PLATFORM_ADMIN.value, None) in current - desired:
            raise HTTPException(status.HTTP_409_CONFLICT, "You can't remove your own administrator role.")
        if desired != current:
            diff["roles"] = [sorted(r for r, _ in current), sorted(r for r, _ in desired)]
            target.role_assignments = [
                a for a in target.role_assignments if (a.role, a.scope_id) in desired
            ] + [RoleAssignment(role=r, scope_id=s) for r, s in sorted(desired - current, key=str)]
    if diff:
        record(db, actor_for(request, actor), "user.update", "user", str(target.id), diff=diff)
    db.commit()
    return UserOut.from_user(target)
