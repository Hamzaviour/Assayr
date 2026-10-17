from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from assayr.db import Base, IdMixin, TimestampMixin, UTCDateTime


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)


class Scope(IdMixin, TimestampMixin, Base):
    __tablename__ = "scope"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(default=False)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_account"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    department: Mapped[str | None] = mapped_column(String(100))
    must_change_password: Mapped[bool] = mapped_column(default=False, server_default=false())
    digest_opt_out: Mapped[bool] = mapped_column(default=False, server_default=false())

    role_assignments: Mapped[list[RoleAssignment]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class RoleAssignment(IdMixin, Base):
    __tablename__ = "role_assignment"
    __table_args__ = (
        UniqueConstraint("user_id", "role", "scope_id", name="uq_role_assignment_user_role_scope"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scope.id", ondelete="CASCADE"))

    user: Mapped[User] = relationship(back_populates="role_assignments")


class UserSession(Base):
    """A signed-in browser session. `id` is the SHA-256 of the cookie token, never the token itself."""

    __tablename__ = "user_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
