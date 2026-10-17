import uuid

from pydantic import BaseModel, Field

from assayr.identity.models import User
from assayr.identity.rbac import Role, permissions_for

EMAIL_PATTERN = r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$"


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class RoleGrantIn(BaseModel):
    role: Role
    scope_id: uuid.UUID | None = None


class RoleGrantOut(BaseModel):
    role: str
    scope_id: uuid.UUID | None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    department: str | None = None
    must_change_password: bool = False
    digest_opt_out: bool = False
    roles: list[RoleGrantOut]
    permissions: list[str]

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        pairs = [(a.role, a.scope_id) for a in user.role_assignments]
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            department=user.department,
            must_change_password=user.must_change_password,
            digest_opt_out=user.digest_opt_out,
            roles=[RoleGrantOut(role=r, scope_id=s) for r, s in pairs],
            permissions=permissions_for(pairs),
        )


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UserCreateIn(BaseModel):
    email: str = Field(max_length=320, pattern=EMAIL_PATTERN)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(max_length=256)
    roles: list[RoleGrantIn] = []


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    roles: list[RoleGrantIn] | None = None
